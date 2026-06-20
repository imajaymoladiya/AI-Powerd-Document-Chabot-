import os
import time

from dotenv import load_dotenv
from groq import Groq

from logger import get_logger

log = get_logger("llm")
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")

# Groq free tier limits tokens-per-minute (TPM). Keep any single request well
# under it (~4 chars per token), so we never send a whole large document at once.
MAX_DOC_CHARS = 14000

def _load_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def _chat(user_prompt, system_prompt=None, retries=1):
    client = Groq(api_key=GROQ_API_KEY)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    for attempt in range(retries + 1):
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=0.2,
                messages=messages,
            )
            log.info("Groq call ok (model=%s, prompt=%d chars, %.1fs)",
                     GROQ_MODEL, len(user_prompt), time.time() - start)
            return response.choices[0].message.content.strip()
        except Exception as error:
            message = str(error).lower()
            transient = "rate_limit" in message or "429" in message or "503" in message
            if attempt < retries and transient:
                log.warning("Groq transient error, retrying in 10s: %s", error)
                time.sleep(10)   # wait for the per-minute limit to refill, then retry
                continue
            log.error("Groq call failed: %s", error)
            raise


def sample_text(text, budget):
    """For long text, take a few evenly-spaced windows so the result reflects the
    whole document instead of only its beginning."""
    if len(text) <= budget:
        return text
    windows = 3
    window_len = budget // windows
    step = len(text) // windows
    parts = [text[i * step: i * step + window_len] for i in range(windows)]
    return "\n\n...\n\n".join(parts)


def answer_question(context, question):
    # context is the text to answer from (joined retrieved chunks, or a broad
    # sample of the whole document for summary/overview questions).
    # The professional answering instructions live in prompt.txt (system role);
    # the context + question are supplied as untrusted data (user role).
    log.info("Answering question: %.80s", question)
    system_prompt = _load_prompt()
    user_prompt = (
        "CONTEXT:\n" + context + "\n\nUSER MESSAGE:\n" + question +
        "\n\nReply per your instructions."
    )
    return _chat(user_prompt, system_prompt=system_prompt)

def derive_rules(document_text):
    log.info("Deriving rules from document (%d chars)", len(document_text))
    # Keep the request under the tokens-per-minute limit. For long documents we
    # sample evenly across the whole text instead of only the first part.
    snippet = sample_text(document_text, MAX_DOC_CHARS)
    note = ""
    if len(document_text) > MAX_DOC_CHARS:
        note = (
            "\n\n(Note: the document is long; rules were derived from samples "
            "spanning the whole document to respect the API token limit.)"
        )
    user_prompt = (
        "From the document below, derive every explicit rule / requirement / "
        "condition as a clean, numbered plain-text list. Use only what is "
        "stated in the document.\n\n"
        "=== DOCUMENT START ===\n" + snippet + "\n=== DOCUMENT END ==="
    )
    return _chat(user_prompt) + note
