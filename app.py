"""
app.py
------
Web app served with Flask + an HTML/CSS front-end (no Streamlit).
It connects all the pieces of the RAG pipeline:

    extract.py     -> extract_document    (0. EXTRACT, OCR scanned docs)
    chunks.py      -> chunk_text          (1. CHUNK)
    embeddings.py  -> build_vector_store  (2. EMBED + 3. STORE)
                      retrieve            (4. RETRIEVE - cosine similarity)
    llm.py         -> answer_question     (5. GENERATE with Groq)
                      derive_rules        (show the document's rule set)
    prompt.txt     -> the professional answering prompt (system role in llm.py)

Routes:
    GET  /        -> the HTML page (templates/index.html)
    POST /build   -> upload a document, build the index, return rules
    POST /ask     -> ask a question, return the answer + retrieved chunks

Run:  python app.py   (then open http://localhost:5000)
"""

import os
import time
import tempfile

from flask import Flask, request, jsonify, render_template

from logger import get_logger
from chunks import chunk_text
from embeddings import build_vector_store, retrieve, EMBED_MODEL_NAME, EMBED_DIM
from llm import answer_question, derive_rules, sample_text, GROQ_API_KEY
from extract import extract_document, SARVAM_API_KEY

log = get_logger("app")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # allow big documents (200 MB)
app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up index.html edits without a restart
app.jinja_env.auto_reload = True

# Simple in-memory state for the current document (single-user assessment app).
STATE = {"chunks": [], "collection": None, "rules": "", "note": ""}

# If the whole document fits in this many characters, send all of it as context
# (best quality for short docs like a JD). Bigger docs fall back to retrieval.
WHOLE_DOC_CHARS = 14000
MAX_HISTORY = 8  # how many prior conversation turns to pass to the model

# Requests that need the WHOLE document rather than a few similar chunks:
# summaries/overviews and generative tasks (interview prep, quizzes, etc.).
GLOBAL_HINTS = (
    "summar", "overview", "tl;dr", "tldr", "key points", "main points",
    "what is this document", "about the document", "gist", "describe the document",
    "explain the document", "give an overview",
    "interview", "question and answer", "questions and answer", "q&a", "qna",
    "prepare", "mock", "quiz", "practice question", "talking point",
    "cheat sheet", "study", "list all", "all the",
)


def wants_whole_document(question):
    q = question.lower()
    return any(hint in q for hint in GLOBAL_HINTS)


def build_context(question, k):
    """Small documents (and whole-document tasks like summaries / interview prep)
    use the entire document as context; large documents use top-k retrieval."""
    whole = "\n\n".join(STATE["chunks"])
    if wants_whole_document(question) or len(whole) <= WHOLE_DOC_CHARS:
        return sample_text(whole, WHOLE_DOC_CHARS), [], "whole document"
    hits = retrieve(STATE["collection"], question, k)
    context = "\n\n---\n\n".join(doc for doc, _ in hits)
    return context, hits, "top %d chunks by cosine similarity" % len(hits)


@app.route("/")
def index():
    return render_template(
        "index.html",
        model=EMBED_MODEL_NAME,
        dim=EMBED_DIM,
        ocr=bool(SARVAM_API_KEY),
        groq=bool(GROQ_API_KEY),
    )


@app.route("/build", methods=["POST"])
def build():
    if "document" not in request.files or request.files["document"].filename == "":
        log.warning("/build called with no file")
        return jsonify({"error": "No file uploaded."}), 400

    uploaded = request.files["document"]
    log.info("/build received file: %s", uploaded.filename)
    started = time.time()

    suffix = os.path.splitext(uploaded.filename)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    uploaded.save(tmp.name)
    tmp.close()
    try:
        text, note = extract_document(tmp.name)
    except Exception as error:
        os.remove(tmp.name)
        log.exception("Extraction failed for %s", uploaded.filename)
        return jsonify({"error": "Extraction failed: %s" % error}), 500
    os.remove(tmp.name)

    if not text.strip():
        log.warning("No text extracted from %s (%s)", uploaded.filename, note)
        return jsonify({"error": "Could not read any text. %s" % note}), 400

    chunks = chunk_text(text)
    collection = build_vector_store(chunks)
    try:
        rules = derive_rules(text)
    except Exception as error:
        log.exception("Rule derivation failed")
        rules = "Could not derive rules: %s" % error

    STATE["chunks"] = chunks
    STATE["collection"] = collection
    STATE["rules"] = rules
    STATE["note"] = note

    log.info("/build complete for %s: %d chunks in %.1fs",
             uploaded.filename, len(chunks), time.time() - started)
    # Client-facing: return only the rules (no chunk counts / model / approach).
    return jsonify({"rules": rules})


@app.route("/ask", methods=["POST"])
def ask():
    if STATE["collection"] is None:
        log.warning("/ask called before building an index")
        return jsonify({"error": "Build the index first."}), 400

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    top_k = int(data.get("top_k") or 4)
    history = (data.get("history") or [])[-MAX_HISTORY:]
    if not question:
        return jsonify({"error": "Empty question."}), 400

    started = time.time()
    context, _hits, mode = build_context(question, top_k)
    log.info("/ask question=%r mode=%s history=%d", question, mode, len(history))
    try:
        answer = answer_question(context, question, history=history)
    except Exception as error:
        log.exception("Answer generation failed")
        answer = "Could not generate an answer: %s" % error

    log.info("/ask answered in %.1fs", time.time() - started)
    # Client-facing: return only the answer (no retrieved chunks / similarity).
    return jsonify({"answer": answer})


if __name__ == "__main__":
    log.info("Starting Document Agent on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
