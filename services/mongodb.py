from pymongo import MongoClient
from dotenv import load_dotenv
import os
from bson import ObjectId

load_dotenv()
uri = os.getenv("db_uri")
db_name = os.getenv("data_path")
client = MongoClient(uri)
db = client[db_name]

email_table = db["email_table"]
file_table = db["file_table"]
invoice_table = db["invoice_table"]
bills_table = db["bills_table"]

# * Implemented the function as standalone because we don't require a class for its implementation
###! Note:Ensure that a shallow copy of the data is made before every insert operation.


def insert_email(data: dict):
    doc = data.copy()
    return email_table.insert_one(doc).inserted_id


def insert_file(data: dict):
    doc = data.copy()
    return file_table.insert_one(doc).inserted_id


def update_ocr_response(file_table_id, ocr_response):
    file_table.update_one(
        {"_id": ObjectId(file_table_id)}, {"$set": {"ocr_response": ocr_response}}
    )


def insert_bills(data: list):
    docs = data.copy()
    return bills_table.insert_many(docs).inserted_ids


def insert_invoice(data: list):
    docs = data.copy()
    invoice_table.insert_many(docs)
