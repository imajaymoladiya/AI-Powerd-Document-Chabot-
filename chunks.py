import re

from logger import get_logger

log = get_logger("chunks")

CHUNK_WORDS = 120
CHUNK_OVERLAP = 30

def _split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]

def chunk_text(text, chunk_words=CHUNK_WORDS, overlap=CHUNK_OVERLAP):
    text = text.replace("\r\n", "\n")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    units = []
    for para in paragraphs:
        if len(para.split()) <= chunk_words:
            units.append(para)
        else:
            units.extend(_split_sentences(para))

    chunks = []
    current = []
    count = 0
    for unit in units:
        wc = len(unit.split())
        if count + wc > chunk_words and current:
            chunks.append(" ".join(current))
            carry = " ".join(current).split()[-overlap:]
            current = [" ".join(carry)] if carry else []
            count = len(carry)
        current.append(unit)
        count += wc

    if current:
        chunks.append(" ".join(current))
    log.info("Chunked text (%d chars) into %d chunks", len(text), len(chunks))
    return chunks
