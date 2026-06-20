import time, os
from fastembed import TextEmbedding
print("CPU cores:", os.cpu_count())
m = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
docs = ["This is a sample machine learning sentence about gradient descent and loss functions."]*300

for kw in [dict(), dict(batch_size=128), dict(batch_size=256, parallel=0), dict(batch_size=64, parallel=0)]:
    t=time.time(); _=list(m.embed(docs, **kw)); dt=time.time()-t
    print("settings=%s -> %.1fs (%.1f docs/s)" % (kw, dt, len(docs)/dt))
