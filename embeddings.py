import json
import numpy as np
import matplotlib.pyplot as plt

from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA

# -----------------------------
# Load Knowledge Base
# -----------------------------
texts = []
labels = []

with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        texts.append(obj["text"])

        # Label from first word
        labels.append(obj["text"].split()[0])

print(f"Loaded {len(texts)} chunks")

# -----------------------------
# Load Embedding Model
# -----------------------------
print("Loading model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Generating embeddings...")
embeddings = model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=True
)

print("Embedding shape:", embeddings.shape)

# -----------------------------
# Save embeddings
# -----------------------------
np.save("embeddings.npy", embeddings)
print("Saved embeddings.npy")

# -----------------------------
# PCA (2D)
# -----------------------------
pca = PCA(n_components=2)
points = pca.fit_transform(embeddings)

# -----------------------------
# Plot
# -----------------------------
plt.figure(figsize=(8,6))

unique_labels = list(set(labels))

colors = [
    "red",
    "blue",
    "green",
    "orange",
    "purple",
    "brown",
    "pink",
    "cyan",
]

for i, label in enumerate(unique_labels):

    xs = []
    ys = []

    for j in range(len(points)):
        if labels[j] == label:
            xs.append(points[j][0])
            ys.append(points[j][1])

    plt.scatter(
        xs,
        ys,
        color=colors[i % len(colors)],
        label=label,
        s=80
    )

plt.title("Knowledge Base Embeddings (PCA)")
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.legend()

plt.savefig("embeddings_2d.png", dpi=300)
plt.show()

print("Saved embeddings_2d.png")
print("Done!")