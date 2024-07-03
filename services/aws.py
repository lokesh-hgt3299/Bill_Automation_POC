from dotenv import load_dotenv
import boto3
from pdf2image import convert_from_bytes
import os, io, mimetypes

load_dotenv()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
aws_access_key_id = os.getenv("boto3_aws_access_key_id")
aws_secret_access_key = os.getenv("boto3_aws_secret_access_key")
region_name = os.getenv("boto3_region_name")

s3client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)

textract_client = boto3.client(
    "textract",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)

# * Implemented the function as standalone because we don't require a class for its implementation


def upload_to_s3(content: bytes, key):
    contentType, _ = mimetypes.guess_type(key)
    buf = io.BytesIO()
    buf.write(content)
    buf.seek(0)
    s3client.upload_fileobj(
        Fileobj=buf,
        Bucket=S3_BUCKET_NAME,
        Key=key,
        ExtraArgs={"ACL": "public-read", "ContentType": contentType},
    )


def get_ocr_text(content: bytes):
    all_text = []
    images = []

    try:
        # --- Note: Ensure that poppler is installed on the system and its path is added to the environment variables
        images = convert_from_bytes(content)
    except Exception as e:
        print("Convert convert pdf to images", e)

    try:
        for index, image in enumerate(images):
            buffer = io.BytesIO()
            image.save(buffer, format="jpeg", subsampling=0, quality=90)
            img_data = buffer.getvalue()
            img_size_mb = len(img_data) / pow(10, 6)

            if img_size_mb >= 10:
                buffer = io.BytesIO()
                image.save(buffer, format="jpeg", subsampling=0, quality=50)
                img_data = buffer.getvalue()

            res = textract_client.detect_document_text(Document={"Bytes": img_data})

            status = res["ResponseMetadata"]["HTTPStatusCode"]

            if status == 200:
                page_text = ""
                for block in res["Blocks"]:
                    if block["BlockType"] == "LINE":
                        page_text += block["Text"]
                all_text.append({"page_number": index + 1, "page_text": page_text})
            else:
                print("OCR response", res)

    except Exception as e:
        print("OCR failed", e)

    return all_text
