from celery import Celery, chain
import pdfkit

import os
import uuid
from datetime import datetime
from collections import defaultdict

from FileHandler import FileHandler
from EmailClient import EmailClient
from services import aws, mongodb as db
from extraction import gpt_modal
from utils.variables import domaine, main_path, sub_path

email_client = EmailClient()
app = Celery(__name__, broker="amqp://guest:guest@localhost//")


@app.task()
def process_email(email: dict):
    email_id = email["id"]
    body: dict = email.get("body", {})
    body_html: str = body.get("content", "")

    _from = email.get("from")

    receivedDateTime = datetime.strptime(
        email.get("receivedDateTime"), "%Y-%m-%dT%H:%M:%SZ"
    )

    to_mail: str = None

    for entry in email.get("ccRecipients", []) + email.get("toRecipients", []):
        mail: str = entry["emailAddress"]["address"]
        if domaine in mail:
            to_mail = mail
            break

    if to_mail:
        """ Previously, we were saving each email as a TXT file in an S3 bucket. 
            However, this approach is inefficient due to memory usage and delays caused by retrieving S3 objects on the client side. 
            Instead, a more efficient method would be to save the `body_html` directly to the database, 
            eliminating the need for redundant TXT file storage on S3. """
        
        if email["hasAttachments"]:
            attachments: list = email_client.get_attachments(email_id=email_id)
        else:
            """ pdfkit is a wrapper for wkhtmltopdf, allowing you to convert HTML or strings to PDF files. 
                To use pdfkit, you'll first need to install wkhtmltopdf on your system.
                You can download it from this https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox-0.12.6-1.msvc2015-win64.exe.
                After installation,  ensure the executable's path is added to your system's environment variables."""
            
            unique_name = str(uuid.uuid4())
            filename = f"{unique_name}.pdf"
            attachments: list = [
                {
                    "filename": filename,
                    "source_filename": filename,
                    "content_bytes": pdfkit.from_string(body_html),
                }
            ]

        client, corp = os.path.splitext(to_mail.split("@")[0])

        doc = {
            "receivedDateTime": receivedDateTime,
            "attachments": attachments,
            "_from": _from["emailAddress"]["address"],
            "to_mail": to_mail,
            "client": client,
            "corp": corp.replace(".", ""),
            "type": "mail",
            "body": body_html,
            "microsoft_id": email_id,
        }

        process_resource_and_files.delay(doc)


# The function for handling both email and uploaded files.
@app.task()
def process_resource_and_files(doc: dict):
    receivedDateTime: datetime = doc.get("receivedDateTime")
    attachments: list = doc.get("attachments")
    _from: str = doc.get("_from")
    to_mail: str = doc.get("to_mail")
    client: str = doc.get("client")
    corp: str = doc.get("corp")
    doc_type: str = doc.get("type")
    body: str = doc.get("body")
    microsoft_id: str = doc.get("microsoft_id", None)

    file_handler = FileHandler(receivedDateTime)

    # Collect PDF files from attachments.
    pdf_files = file_handler.collectPdfFiles(attachments)

    email_table = {
        "from": _from,
        "to": to_mail,
        "body": body,
        "timestamp": receivedDateTime,
        "client": client,
        "property": corp,
        "type": doc_type,
        "microsoft_id": microsoft_id,
    }

    file_table = email_table.copy()
    file_table["email_table_id"] = db.insert_email(email_table)
    file_table.pop("microsoft_id")

    filepath = f"{main_path}/{sub_path}/{client}/{corp}"

    for p in pdf_files:
        content_bytes = p.content_byte
        file_table["source_filename"] = p.source_filename

        key = f"{filepath}/{p.filename}"
        file_table["s3_key"] = key
        file_table_id = db.insert_file(file_table)
        file_table_id = str(file_table_id)

        upload_to_s3_and_process.apply_async(
            args=[content_bytes, key, file_table_id, corp], task_id=p.filename
        )


@app.task()
def upload_to_s3_and_process(content_bytes, key, file_table_id, corp):
    # Task 1: Upload to s3 and add to db
    aws.upload_to_s3(content=content_bytes, key=key)

    # Chaining the OCR text extraction, entity extraction, preprocess entities
    ocr_chain = chain(
        get_ocr_text.s(content_bytes, file_table_id),
        extract_entities.s(corp),
        process_entities.s(file_table_id=file_table_id),
    )
    ocr_chain.apply_async()


@app.task()
def get_ocr_text(content_bytes, file_table_id):
    # Task 2: get OCR text and update db
    all_text = aws.get_ocr_text(content=content_bytes)
    db.update_ocr_response(file_table_id=file_table_id, ocr_response=all_text)
    return {"file_table_id": file_table_id, "ocr_text": all_text}


@app.task()
def extract_entities(result, corp):
    # Task 3: Send to modal to extract entities if all_text has content
    file_table_id = result["file_table_id"]
    all_text = result["ocr_text"]
    print("OCr--------",len(all_text))
    #Todo create a dummy bill if the
    if len(all_text) > 0:
        entities: list = gpt_modal.extract_entities(
            ocr_text=all_text, property_name=corp
        )
        return {"file_table_id": file_table_id, "entities": entities}
    
    # else: it means ocr is failed
    #Todo else create a dummy bill

@app.task()
def process_entities(result, file_table_id: str):
    # Task 4: Process extracted entities and update to db bill_object and invoice table if entities have content
    # In this task creating bill table and invoice table
    result = defaultdict(dict, result or {})
    entities = result.get("entities")
    # For invoice table just add bill_id and file_table_id
    if entities:
        #Todo create a bills and invoice collections in db
        print(entities)

    # else: it means extraction is failed
    #Todo else create a dummy bill

    return "All tasks completed"
