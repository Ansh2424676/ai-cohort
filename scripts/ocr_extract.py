import pytesseract
from PIL import Image
import os

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load image
image = Image.open("data/enrollment.png")

# OCR
text = pytesseract.image_to_string(image)

# Create output folder
os.makedirs("raw_text", exist_ok=True)

# Save extracted text
with open("raw_text/enrollment.txt", "w", encoding="utf-8") as file:
    file.write(text)

print("OCR completed successfully!")