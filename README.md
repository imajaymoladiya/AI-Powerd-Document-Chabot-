# RAG Document Rules & Q&A

A RAG web product (Flask backend + HTML/CSS front-end). Upload a document and it
derives the explicit rules, then answers questions grounded only in the document
using a full Retrieval-Augmented Generation pipeline.

Plain, procedural Python (no classes). The API keys are read from `.env`.

## Files (each step in its own module)

| File | Role | Pipeline step |
|------|------|---------------|
| `extract.py` | Get text from any document; OCR scanned PDFs/images via Sarvam AI | 0. Extract |
| `chunks.py` | Split the document into overlapping, structure-aware chunks | 1. Chunk |
| `embeddings.py` | Embed chunks (`BAAI/bge-small-en-v1.5`), store in ChromaDB, retrieve by cosine similarity | 2. Embed, 3. Store, 4. Retrieve |
| `prompt.txt` | Professional answering instructions (used as the **system** prompt in `llm.py`) | used in step 5 |
| `llm.py` | Send (context + question) to Groq with the system prompt; also derive rules | 5. Generate |
| `app.py` | Flask app: routes `/`, `/build`, `/ask` | orchestration |
| `templates/index.html` | The HTML page | UI |
| `static/style.css`, `static/app.js` | Styling + front-end logic (fetch to the routes) | UI |

## Any document type + OCR (`extract.py`)

- `.txt` / `.md` — read directly
- `.docx` — python-docx
- `.pdf` with selectable text — pypdf
- **scanned / OCR-only PDF** — detected automatically (almost no selectable
  text) and sent to **Sarvam AI Document Intelligence** for OCR
- **images** (`.png/.jpg/.jpeg/.tiff/.bmp/.webp`) — converted to a PDF, then OCR

Sarvam allows max 10 pages per OCR job, so **big PDFs are split into 10-page
batches** and the extracted text is joined back. Requires `SARVAMAI_API_KEY` in
`.env` (optional `SARVAM_LANGUAGE`, default `en-IN`).

## Big documents

- Retrieval (Q&A) already scales — only the top few chunks are sent to the LLM.
- Rule derivation samples evenly **across the whole document** within a safe
  token budget, and Groq calls retry once on a rate-limit hiccup.

```
app.py
  -> chunks.chunk_text            (1) split into chunks
  -> embeddings.build_vector_store(2) embed + (3) store in ChromaDB
  -> embeddings.retrieve          (4) cosine-similarity top-k
  -> llm.answer_question          (5) generate answer with Groq (uses prompt.txt)
  -> llm.derive_rules             show the document's rule set
```

## Why this embedding model

A JD / policy document is short, structured English prose. `bge-small-en-v1.5`
(384-dim) is small, fast on CPU (ONNX — no GPU/torch), and strong at semantic
retrieval / QA for this style of text.

## Setup

```powershell
.\myenv\Scripts\python.exe -m pip install -r requirements.txt
```

`.env`:

```
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
SARVAMAI_API_KEY=your_sarvam_key_here
SARVAM_LANGUAGE=en-IN
```

## Run

```powershell
.\myenv\Scripts\python.exe app.py
```

Open **http://localhost:5000**, upload a document, click **Build RAG index**,
then ask questions. Each answer shows the retrieved chunks with their
cosine-similarity scores, alongside the derived rule set.

> The first run downloads the embedding model (~130 MB) once and caches it.
