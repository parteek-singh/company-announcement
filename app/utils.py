import os
import uuid

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STORAGE_DIR = os.path.join(os.path.dirname(BASE_DIR), "storage")

PDF_DIR = os.path.join(STORAGE_DIR, "pdfs")
RAW_DIR = os.path.join(STORAGE_DIR, "raw")
RESULT_DIR = os.path.join(STORAGE_DIR, "results")


def ensure_storage_dirs():
    for path in (PDF_DIR, RAW_DIR, RESULT_DIR):
        os.makedirs(path, exist_ok=True)
    # create templates folder if not exists
    os.makedirs(os.path.join(os.path.dirname(BASE_DIR), "templates"), exist_ok=True)


def generate_doc_id() -> str:
    return uuid.uuid4().hex


def pdf_path(doc_id: str) -> str:
    return os.path.join(PDF_DIR, f"{doc_id}.pdf")


def raw_path(doc_id: str) -> str:
    return os.path.join(RAW_DIR, f"{doc_id}.json")


def result_path(doc_id: str) -> str:
    return os.path.join(RESULT_DIR, f"{doc_id}.json")
