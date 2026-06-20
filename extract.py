"""
extract.py
----------
Step 0 of the pipeline: get plain text out of ANY document the user uploads.

  - .txt / .md            -> read directly
  - .docx                 -> python-docx
  - .pdf (digital text)   -> pypdf
  - .pdf (scanned / OCR)  -> Sarvam AI Document Intelligence (OCR)
  - images (.png/.jpg..)  -> turned into a 1-page PDF, then Sarvam OCR

Big documents are handled too: Sarvam allows max 10 pages per job, so large
PDFs are split into 10-page batches and the extracted text is joined back.

The Sarvam key is read from .env (SARVAMAI_API_KEY).
Used by: app.py
"""

import os
import zipfile

from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
from PIL import Image
import docx
from sarvamai import SarvamAI

from logger import get_logger

log = get_logger("extract")
load_dotenv()
SARVAM_API_KEY = os.getenv("SARVAMAI_API_KEY")
SARVAM_LANGUAGE = os.getenv("SARVAM_LANGUAGE", "en-IN")

SARVAM_MAX_PAGES = 10      # Sarvam limit: pages per OCR job
MIN_CHARS_PER_PAGE = 40    # below this, a PDF page is treated as scanned (needs OCR)


# ---------------------------------------------------------------------------
# Plain readers
# ---------------------------------------------------------------------------
def read_text_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_docx_file(path):
    document = docx.Document(path)
    return "\n".join(para.text for para in document.paragraphs)


def read_pdf_text(path):
    reader = PdfReader(path)
    pages = len(reader.pages)
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(parts), pages


def looks_scanned(text, pages):
    # A digital PDF has plenty of selectable text; a scanned one has almost none.
    if pages <= 0:
        return True
    return len(text.strip()) < MIN_CHARS_PER_PAGE * pages


# ---------------------------------------------------------------------------
# Sarvam AI OCR
# ---------------------------------------------------------------------------
def _sarvam_one_job(pdf_path):
    log.info("Sarvam OCR job starting for %s", os.path.basename(pdf_path))
    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
    job = client.document_intelligence.create_job(
        language=SARVAM_LANGUAGE, output_format="md"
    )
    job.upload_file(pdf_path)
    job.start()
    job.wait_until_complete()
    log.info("Sarvam OCR job complete for %s", os.path.basename(pdf_path))

    zip_path = pdf_path + ".out.zip"
    job.download_output(zip_path)

    # The ZIP holds one markdown file per page plus a JSON; join the markdown.
    parts = []
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(n for n in archive.namelist() if n.lower().endswith(".md"))
        for name in names:
            parts.append(archive.read(name).decode("utf-8", errors="ignore"))
    os.remove(zip_path)
    return "\n\n".join(parts)


def _split_pdf(pdf_path, pages_per_batch=SARVAM_MAX_PAGES):
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    batch_paths = []
    for start in range(0, total, pages_per_batch):
        writer = PdfWriter()
        for i in range(start, min(start + pages_per_batch, total)):
            writer.add_page(reader.pages[i])
        batch_path = "%s.part%d.pdf" % (pdf_path, start)
        with open(batch_path, "wb") as f:
            writer.write(f)
        batch_paths.append(batch_path)
    return batch_paths


def sarvam_ocr_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    pages = len(reader.pages)
    if pages <= SARVAM_MAX_PAGES:
        return _sarvam_one_job(pdf_path)

    # Big document: process in 10-page batches and join the results.
    batches = _split_pdf(pdf_path)
    log.info("OCR splitting %d-page PDF into %d batches", pages, len(batches))
    parts = []
    for i, batch in enumerate(batches, 1):
        log.info("OCR batch %d/%d", i, len(batches))
        parts.append(_sarvam_one_job(batch))
        os.remove(batch)
    return "\n\n".join(parts)


def _image_to_pdf(image_path):
    pdf_path = image_path + ".pdf"
    Image.open(image_path).convert("RGB").save(pdf_path, "PDF")
    return pdf_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def extract_document(path):
    """Return (text, note) where note explains how the text was obtained."""
    name = path.lower()
    log.info("Extracting text from %s", os.path.basename(path))

    if name.endswith((".txt", ".md", ".text")):
        text = read_text_file(path)
        log.info("Extracted plain text (%d chars)", len(text))
        return text, "Read as plain text."

    if name.endswith(".docx"):
        text = read_docx_file(path)
        log.info("Extracted DOCX (%d chars)", len(text))
        return text, "Read with python-docx."

    if name.endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")):
        if not SARVAM_API_KEY:
            log.warning("Image needs OCR but SARVAMAI_API_KEY is missing")
            return "", "Image needs OCR but SARVAMAI_API_KEY is missing."
        text = sarvam_ocr_pdf(_image_to_pdf(path))
        log.info("Extracted image via OCR (%d chars)", len(text))
        return text, "Image OCR via Sarvam AI."

    if name.endswith(".pdf"):
        text, pages = read_pdf_text(path)
        if looks_scanned(text, pages):
            if not SARVAM_API_KEY:
                log.warning("Scanned PDF but SARVAMAI_API_KEY is missing")
                return text, "Scanned PDF but SARVAMAI_API_KEY is missing."
            log.info("PDF looks scanned (%d pages) -> using OCR", pages)
            text = sarvam_ocr_pdf(path)
            log.info("Extracted scanned PDF via OCR (%d chars)", len(text))
            return text, "Scanned PDF -> OCR via Sarvam AI."
        log.info("Digital PDF read with pypdf: %d pages, %d chars", pages, len(text))
        return text, "Digital PDF read with pypdf (%d pages)." % pages

    # Unknown type: best effort as plain text.
    text = read_text_file(path)
    log.info("Extracted unknown type as plain text (%d chars)", len(text))
    return text, "Read as plain text (unknown type)."
