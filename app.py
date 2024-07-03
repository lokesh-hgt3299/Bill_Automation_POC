from fastapi import FastAPI, Request, Response, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import JSONResponse
from EmailClient import EmailClient
from typing import Any, Dict, List
from datetime import datetime
import json

from tasks import process_email, process_resource_and_files
from services.mongodb import client
from utils.variables import domaine

app = FastAPI()
email_client = EmailClient()
db = client["email_client"]


# This class wraps methods for handling background tasks in FastAPI.
class Bg_Tasks:
    @staticmethod
    def resource(resource):
        response, status = email_client.get_mail(resource)
        if status == 200:
            process_email(email=response)

    @staticmethod
    def subscription_renewal(subscriptionId):
        response, status = email_client.update_subscription(subscriptionId)
        if status == 200:
            db["renewals"].insert_many([response])
        else:
            print(response, status)


@app.get("/")
def list_subscription():
    response, status = email_client.get_all_subs()
    result = len(response["value"]) if isinstance(response["value"], list) else response
    return JSONResponse(content=result, status_code=status)


@app.get("/create_subscription")
def create_subscription():
    response, status = email_client.create_subscription()
    if status == 201:
        db["subscriptions"].insert_many([response])
    if "_id" in response:
        # * Due to inserting to DB it add a _id to the res
        response["_id"] = str(response["_id"])
    return JSONResponse(content=response, status_code=status)


@app.get("/delete_all_subscription")
def delete_all_subscription():
    response, status = email_client.get_all_subs()
    if status == 200:
        subscriptionIds = [i["id"] for i in response["value"]]
        if len(subscriptionIds) > 0:
            email_client.delete_all_subscription(subscriptionIds)
            db["subscriptions"].drop()
            db["renewals"].drop()
    return JSONResponse(content=response, status_code=status)


""" To ensure that Microsoft receives a 200 status code within 10 seconds, 
    we've implemented a solution using FastAPI background tasks. 
    Initially, we promptly return the 200 status code and then proceed with the necessary task asynchronously.
    This approach prevents the occurrence of duplicate emails 
    caused by Microsoft repeatedly calling the endpoint until it receives the expected response within the specified time frame (10 sec). """


@app.post("/notification/")
def handle_notification(
    request: Request,
    background_tasks: BackgroundTasks,
    data: Dict[Any, Any] | None = None,
):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return Response(
            content=validation_token, status_code=200, media_type="text/plain"
        )
    else:
        # The resource is nothing but a endpoint 'resource':"users/info@sendhours.com/mailFolders('inbox')/messages"
        resource = data["value"][0]["resource"]
        background_tasks.add_task(Bg_Tasks.resource, resource)
    return JSONResponse(content="", status_code=200, media_type="text/plain")


@app.post("/lifecycleNotification/")
def handle_lifecycleNotification(
    request: Request,
    background_tasks: BackgroundTasks,
    data: Dict[Any, Any] | None = None,
):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return Response(
            content=validation_token, status_code=200, media_type="text/plain"
        )
    else:
        subscriptionId = data["value"][0]["subscriptionId"]
        background_tasks.add_task(Bg_Tasks.subscription_renewal, subscriptionId)
    return JSONResponse(content="", status_code=200, media_type="text/plain")


# *-- This endpoint is used for testing or manually adding an email to the queue if the Microsoft webhook method fails.
@app.get("/emails")
def get_emails():
    emails: list = email_client.get_mails_manually()
    received_mails = []
    for email in emails:
        received_mails.append({"mail": email["from"]["emailAddress"]["address"]})
        process_email.delay(email=email)

    return received_mails


# Todo: we need to test this endpoint. Currently, it hasn't been tested.
@app.post("/upload/")
def upload(
    uploadFields: str = Form(...),
    files: List[UploadFile] = File(...),
):
    details = json.loads(uploadFields)

    client = details["client"]
    corp = details["property"]

    _from = details["uploader"]
    body = details["memo"]

    to_mail = f"{client}.{corp}@{domaine}"

    receivedDateTime = datetime.now()

    attachments = attachments = [
        {"filename": file.filename, "content_bytes": file.read()} for file in files
    ]

    process_resource_and_files(
        {
            "receivedDateTime": receivedDateTime,
            "attachments": attachments,
            "_from": _from,
            "to_mail": to_mail,
            "client": client,
            "corp": corp,
            "type": "upload",
            "body": body,
        }
    )

    return "Uploaded..."
