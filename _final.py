import time, importlib
import extract, chunks as cm, embeddings
txt,_ = extract.read_pdf_text(r"C:\Users\imaja\Downloads\MLBOOK.pdf")
ch = cm.chunk_text(txt)
print("chunks:", len(ch))
t=time.time(); emb = embeddings.embed_texts(ch); dt=time.time()-t
print("NEW embed_texts (parallel): %.1fs (%.1f chunks/s) | dim=%d" % (dt, len(ch)/dt, len(emb[0])))
