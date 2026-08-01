from docx import Document
import os

# DOCX file path
docx_file = "data/claims_process.docx"

# Output folder
os.makedirs("raw_text", exist_ok=True)

output_file = "raw_text/claims_process.txt"

# Read DOCX
doc = Document(docx_file)

text = ""

for para in doc.paragraphs:
    text += para.text + "\n"

# Save extracted text
with open(output_file, "w", encoding="utf-8") as file:
    file.write(text)

print("DOCX text extracted successfully!")