import json
import numpy as np
import chromadb

# Connect to ChromaDB
client = chromadb.PersistentClient(path="chroma_data")

collection = client.get_or_create_collection(
    name="coverage_kb"
)

documents = []
metadatas = []
ids = []

# Read knowledge base
with open("knowledge_base.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        obj = json.loads(line)

        documents.append(obj["text"])

        metadatas.append({
            "source_file": obj.get("source_file", ""),
            "source_type": obj.get("source_type", ""),
            "plan_type": obj.get("plan_type", ""),
            "section": obj.get("section", "")
        })

        ids.append(obj.get("id", str(i)))

# Load embeddings
embeddings = np.load("embeddings.npy")

print(f"Loaded {len(documents)} documents")
print(f"Embeddings shape: {embeddings.shape}")
print("\nAdding documents to ChromaDB...")

collection.add(
    ids=ids,
    documents=documents,
    embeddings=embeddings.tolist(),
    metadatas=metadatas
)

print("Documents added successfully!")
print("Collection Count:", collection.count())
print("\nAdding documents to ChromaDB...")