from dotenv import load_dotenv
import os
from enum import IntEnum

load_dotenv()

mail = os.getenv("mail")
_, domaine = mail.split("@")


main_path = os.getenv("data_path")
sub_path = os.getenv("sub_path")


class Bill_Process_Status(IntEnum):
    TO_BE_POSTED = 0
    POSTED = 1

    DUPLICATE = -2
    MARK_AS_INACTIVE = -4

    EXTRACTION_FAILED = -3
    OCR_FAILED = -6
    INVALID_FILE = -7
