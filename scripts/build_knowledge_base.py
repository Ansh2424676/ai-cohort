import os
import json
import uuid
from datetime import datetime

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter

print("Libraries Imported Successfully")
# Create text splitter
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

# Store all knowledge chunks
knowledge_base = []
# -----------------------------
# Read plans.csv
# -----------------------------

plans_file = "data/plans.csv"

if os.path.exists(plans_file):

    df = pd.read_csv(plans_file)

    print(f"Loaded {len(df)} plans")

    for _, row in df.iterrows():

        plan_text = ""

        for col in df.columns:
            plan_text += f"{col}: {row[col]} | "

        knowledge_base.append({

            "id": str(uuid.uuid4()),

            "text": plan_text,

            "source_file": "plans.csv",

            "source_type": "structured",

            "plan_type": str(row.get("plan_type", "")),

            "section": "coverage",

            "ingested_at": datetime.now().isoformat()

        })

else:
    print("plans.csv not found")

print("Text Splitter Ready")
# -----------------------------
# Read text files
# -----------------------------

text_files = [
    "benefits.txt",
    "claims_process.txt",
    "enrollment.txt"
]

for file_name in text_files:

    file_path = os.path.join("raw_text", file_name)

    if not os.path.exists(file_path):
        print(f"{file_name} not found")
        continue

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = splitter.split_text(text)

    print(f"{file_name}: {len(chunks)} chunks")

    section = file_name.replace(".txt", "")

    for chunk in chunks:

        knowledge_base.append({

            "id": str(uuid.uuid4()),

            "text": chunk,

            "source_file": file_name,

            "source_type": "unstructured",

            "plan_type": "",

            "section": section,

            "ingested_at": datetime.now().isoformat()

        })
        # -----------------------------
# Save Knowledge Base
# -----------------------------

output_file = "knowledge_base.jsonl"

with open(output_file, "w", encoding="utf-8") as f:
    for item in knowledge_base:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print()
print("=" * 40)
print(f"Knowledge Base Saved Successfully!")
print(f"Total Records: {len(knowledge_base)}")
print(f"File Name: {output_file}")
print("=" * 40)