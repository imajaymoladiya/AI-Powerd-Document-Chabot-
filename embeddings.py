import os
import time

from fastembed import TextEmbedding
import chromadb

from logger import get_logger

log = get_logger("embeddings")

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384          # bge-small-en-v1.5 vector size
TOP_K = 4

EMBED_BATCH = 256        # how many chunks to encode per batch
# Big documents: spread encoding across all CPU cores (multiprocessing). Small
# ones stay single-process to avoid the worker start-up overhead.
PARALLEL_THRESHOLD = 200

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        log.info("Loading embedding model %s ...", EMBED_MODEL_NAME)
        _embedder = TextEmbedding(model_name=EMBED_MODEL_NAME)
        log.info("Embedding model ready")
    return _embedder

def embed_texts(texts):
    embedder = get_embedder()
    # Multiprocessing speeds up big batches locally, but loads a model copy per
    # core -> OOM on small (512 MB) hosts. So it is OPT-IN via EMBED_PARALLEL=1.
    use_parallel = os.environ.get("EMBED_PARALLEL") == "1"
    parallel = 0 if (use_parallel and len(texts) >= PARALLEL_THRESHOLD) else None
    log.info("Embedding %d texts (batch=%d, parallel=%s)", len(texts), EMBED_BATCH, parallel)
    start = time.time()
    vectors = [vec.tolist()
               for vec in embedder.embed(texts, batch_size=EMBED_BATCH, parallel=parallel)]
    log.info("Embedded %d texts in %.1fs", len(vectors), time.time() - start)
    return vectors

def embed_one(text):
    embedder = get_embedder()
    return list(embedder.embed([text]))[0].tolist()

def build_vector_store(chunks):
    embeddings = embed_texts(chunks)
    client = chromadb.EphemeralClient()
    try:
        client.delete_collection("document")
    except Exception:
        pass
    collection = client.create_collection(
        name="document", metadata={"hnsw:space": "cosine"}
    )
    ids = ["chunk-%d" % i for i in range(len(chunks))]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings)
    log.info("Stored %d vectors in ChromaDB (cosine)", len(chunks))
    return collection

def retrieve(collection, query, k=TOP_K):
    query_vector = embed_one(query)
    result = collection.query(query_embeddings=[query_vector], n_results=k)
    documents = result["documents"][0]
    distances = result["distances"][0]
    hits = [(doc, 1.0 - dist) for doc, dist in zip(documents, distances)]
    top = hits[0][1] if hits else 0.0
    log.info("Retrieved %d chunks (top cosine %.3f) for query: %.60s",
             len(hits), top, query)
    return hits
