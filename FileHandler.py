import numpy as np
import cv2
import img2pdf
import patoolib

import os, logging, tempfile, subprocess
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import List, Dict
from datetime import datetime
from utils.helpers import replace_special_characters

from threading import Thread

logging.getLogger("patool").setLevel(logging.WARNING)


class PdfFile:
    def __init__(self, filename: str, source_filename: str, content_byte: bytes):
        self.filename = filename
        self.content_byte = content_byte
        self.source_filename = source_filename


class FileHandler:
    def __init__(self, receivedDateTime: datetime):
        self.timestamp = receivedDateTime.strftime("%Y%m%d%H%M%S")
        self.pdf_files: List[PdfFile] = []
        self.unique_name: str = None
        self.source_filename: str = None
        self.libreoffice_path = r"C:\\Program Files\\LibreOffice\\program\\soffice.exe"
        pass

    def image_to_pdf(self, buffer: bytes):
        #!Allowed extentions for cv2 imread()
        # "*.bmp", "*.dib",
        # "*.jpeg", "*.jpg", "*.jpe",
        # "*.jp2",
        # "*.png",
        # "*.webp",
        # "*.avif",
        # "*.pbm", "*.pgm", "*.ppm", "*.pxm", "*.pnm",
        # "*.pfm",
        # "*.sr", "*.ras",
        # "*.tiff", "*.tif",
        # "*.exr",
        # "*.hdr", "*.pic"
        valid_image: bytes = None
        try:
            nparr = np.frombuffer(buffer, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            height, width = image.shape[:2]
            if height > 300 or width > 300:
                valid_image = buffer
        except Exception as e:
            valid_image = buffer
            print(self.unique_name)
            print("Error in image filter cv2:", e)

        if valid_image:
            try:
                self.pdf_files.append(
                    PdfFile(
                        self.unique_name,
                        self.source_filename,
                        img2pdf.convert(valid_image),
                    )
                )
            except Exception as e:
                print(self.unique_name)
                print("Error while converting image to pdf:", e)

    def doc_to_pdf(self, buffer: bytes, name: str, ext: str):
        #! Note It delete the files after some period.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, f"{name}{ext}")

            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(buffer)

            try:
                command = [
                    self.libreoffice_path,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_dir,
                    temp_file_path,
                ]
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Conversion failed: {e}")

            temp_out_path = os.path.join(temp_dir, f"{name}.pdf")
            if os.path.exists(temp_out_path):
                with open(temp_out_path, "rb") as f:
                    self.pdf_files.append(
                        PdfFile(self.unique_name, self.source_filename, f.read())
                    )

    def handleEmlFile(self, buffer: bytes):
        files = []

        try:
            email_message: EmailMessage = message_from_bytes(
                buffer, policy=policy.default
            )
            attachments = [
                item
                for item in email_message.iter_attachments()
                if item.is_attachment()
            ]

            for attachment in attachments:
                files.append(
                    {
                        "filename": attachment.get_filename(),
                        "content_bytes": attachment.get_payload(decode=True),
                    }
                )
        except Exception as error:
            print("Error while getting handling .Eml file", error)

        self.collectPdfFiles(files)

    def extractArchive(self, buffer: bytes, filename: str):
        #! Note: To use patool, we have to install 7-zip in the system and set the path of 7-zip in environment variables.
        #! Note It delete the files after some period.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, filename)
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(buffer)

            try:
                temp_out_path = os.path.join(temp_dir, "archived files")
                patoolib.extract_archive(archive=temp_file_path, outdir=temp_out_path)
                extracted_files = [
                    {
                        "filename": file,
                        "content_bytes": open(os.path.join(root, file), "rb").read(),
                    }
                    for root, _, files in os.walk(temp_out_path)
                    for file in files
                ]

                self.collectPdfFiles(extracted_files)
            except patoolib.util.PatoolError as e:
                print(f"PatoolError: {e}")

    def collectPdfFiles(self, filelist: List[Dict[str, bytes]]) -> List[PdfFile]:
        # Todo: Track failed fails in the DB
        # We are using threads to concurrently process each file instead of processing them sequentially.
        threads: List[Thread] = []
        for index, file in enumerate(filelist):
            thread = Thread(target=self.process_file, args=(file, index))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        return self.pdf_files

    def process_file(self, file, index):
        filename = file["filename"]
        filedata = file["content_bytes"]
        name, ext = os.path.splitext(filename)

        print("Processing..", filename)

        self.source_filename = filename
        modified_name = replace_special_characters(name)
        self.unique_name = f"{self.timestamp}-{modified_name}-{index+1}.pdf"

        if ext == ".pdf":
            self.pdf_files.append(
                PdfFile(self.unique_name, self.source_filename, filedata)
            )

        elif ext == "":  # Mostly .eml files
            self.handleEmlFile(filedata)

        elif ext in [".zip", ".rar"]:
            self.extractArchive(filedata, filename)

        elif ext in [".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"]:
            self.doc_to_pdf(filedata, name, ext)

        elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            self.image_to_pdf(filedata)
