"""
PDF -> raw text. Keeps this dumb and reliable (pypdf) rather than reaching for a
heavier document-AI pipeline — for a hackathon demo, digitally-generated PDFs
(the sample docs, and most real invoices/POs) extract cleanly with pypdf. If you
need scanned-image support, add OCR (e.g. pytesseract) here as a fallback.
"""
import io

from pypdf import PdfReader


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch by extension. Plain text files are supported directly, useful for
    quickly wiring up synthetic sample data without generating PDFs.
    """
    if filename.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    return file_bytes.decode("utf-8", errors="ignore")