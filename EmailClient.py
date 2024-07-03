from msal import ConfidentialClientApplication
import os, requests, base64, json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv


class EmailClient:
    def __init__(self):
        load_dotenv()
        self.microsoft_url = "https://graph.microsoft.com/v1.0"

        tenant_id = os.getenv("tenant_id")
        client_id = os.getenv("client_id")
        client_secret = os.getenv("client_secret")

        authority = f"https://login.microsoftonline.com/{tenant_id}"

        # Create a ConfidentialClientApplication instance
        self.app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
        )

        self.mail = os.getenv("mail", "")
        # update this
        self.app_url = " https://679c-103-140-18-66.ngrok-free.app"
        self.notificationUrl = "notification/"
        self.lifecycleNotificationUrl = "lifecycleNotification/"

        self.resource = f"users/{self.mail}/mailfolders/inbox/messages"

        self.EXPIRE_TIME = 1

    def get_token(self):
        # Define scopes for the resources you want to access
        scopes = ["https://graph.microsoft.com/.default"]
        # Acquire a token
        res = self.app.acquire_token_for_client(scopes=scopes)
        return res["access_token"]

    def headers(self, accept: str = "application/json"):
        return {"Authorization": f"Bearer {self.get_token()}", "Accept": accept}

    def get_expiry_dt(self):
        #! Note: Maximum expirationDateTime is under 3 days.
        #! From microsoft documentation 4230 Minutes for mail resource. More than this it gives BadRequest.
        # * Recommended expirationDateTime is one day or 1410 minutes

        currentTime = datetime.now(timezone.utc)
        expireTime = currentTime + timedelta(minutes=self.EXPIRE_TIME)
        return expireTime.astimezone().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def create_subscription(self):
        #! notificationUrl & lifecycleNotificationUrl must respond with 200 OK within 10sec
        #! Note: ONLY ONE SUBSCRIPTION FOR ONE RESOURCE IF HAS MULTIPLE THE "notificationUrl" GETTING MULTIPLE REQUESTS MAY CAUSE DUPLICATES AND INCREASE TRAFFIC
        #! Please Delete previous subscriptions for this resource
        payload = {
            "changeType": "updated",
            "notificationUrl": f"{self.app_url}/{self.notificationUrl}",
            "lifecycleNotificationUrl": f"{self.app_url}/{self.lifecycleNotificationUrl}",
            "resource": f"users/{self.mail}/mailFolders('inbox')/messages",
            "expirationDateTime": self.get_expiry_dt(),
        }
        response = requests.post(
            url=f"{self.microsoft_url}/subscriptions",
            headers=self.headers(accept="application/json"),
            json=payload,
        )

        return response.json(), response.status_code

    def update_subscription(self, subscriptionId):
        payload = {"expirationDateTime": self.get_expiry_dt()}
        response = requests.patch(
            url=f"{self.microsoft_url}/subscriptions/{subscriptionId}",
            headers=self.headers(accept="application/json"),
            json=payload,
        )

        return response.json(), response.status_code

    def get_all_subs(self):
        response = requests.get(
            url=f"{self.microsoft_url}/subscriptions",
            headers=self.headers(accept="application/json"),
        )
        return response.json(), response.status_code

    def delete_subscription(self, subscriptionId):
        response = requests.delete(
            url=f"{self.microsoft_url}/subscriptions/{subscriptionId}",
            headers=self.headers(accept="application/json"),
        )

        print(response.status_code)

    def delete_all_subscription(self, subscriptionIds):
        for id in subscriptionIds:
            self.delete_subscription(id)

    def get_mail(self, resource):
        response = requests.get(
            url=f"{self.microsoft_url}/{resource}",
            headers=self.headers(accept="application/json"),
        )
        return response.json(), response.status_code

    def get_attachments(self, email_id):
        response = requests.get(
            url=f"{self.microsoft_url}/{self.resource}/{email_id}/attachments",
            headers=self.headers(),
        )

        attachments = response.json()["value"]

        attachments_list = []

        for attachment in attachments:
            attachment_name = attachment["name"]

            if "contentBytes" in attachment:
                file_data = base64.b64decode(attachment["contentBytes"])
            else:
                res = requests.get(
                    f"{self.microsoft_url}/{self.resource}/{email_id}/attachments/{attachment['id']}/$value",
                    headers=self.headers(),
                )
                file_data = res.content

            attachments_list.append(
                {
                    "filename": attachment_name,
                    "content_bytes": file_data,
                }
            )

        return attachments_list

    def change_status(self, email_id: str):
        response = requests.patch(
            url=f"{self.microsoft_url}/users/{self.mail}/mailfolders/inbox/messages/{email_id}",
            headers=self.headers(accept="application/json"),
            json={"isRead": True},
        )

        return response.json(), response.status_code

    def get_mails_manually(self):
        url = f"{self.microsoft_url}/users/{self.mail}/mailfolders/inbox/messages"
        params = {
            "$filter": "isRead eq false",
            "$select": "subject, from, toRecipients, receivedDateTime, body, ccRecipients, bodyPreview, hasAttachments",
        }
        response = requests.get(
            url, headers=self.headers(accept="application/json"), params=params
        )

        if response.status_code == 200:
            email_res: dict = response.json()
            emails = email_res.get("value", [])
            return emails
        else:
            print("Error retrieving emails:", response.text)

        return []

    # def get_msg(self):
    #     id = "AAMkADc1YTFiNmNhLWFlMWYtNDQzMC1hYjYzLTk1OTk5N2E5NmM2NwBGAAAAAAC5q2EL4CXsQaJsevVNAiHNBwAGM8_OWo5GRK7TJ0YZXSJzAAAAAAEMAAAGM8_OWo5GRK7TJ0YZXSJzAAQUwHSoAAA="
    #     url = f"{self.microsoft_url}/users/{self.mail}/mailfolders/inbox/messages/{id}"
    #     response = requests.get(url, headers=self.headers(accept="application/json"))
    #     with open("email.json", "w") as f:
    #         f.write(json.dumps(response.json()))
