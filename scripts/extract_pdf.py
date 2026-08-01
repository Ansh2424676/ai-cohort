import pdfplumber
import os

# PDF file path
pdf_file = "data/benefits.pdf"

# Output folder
os.makedirs("raw_text", exist_ok=True)

output_file = "raw_text/benefits.txt"

text = ""

with pdfplumber.open(pdf_file) as pdf:
    for page in pdf.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

with open(output_file, "w", encoding="utf-8") as file:
    file.write(text)

print("PDF text extracted successfully!")