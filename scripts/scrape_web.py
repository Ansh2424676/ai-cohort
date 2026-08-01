import requests
from bs4 import BeautifulSoup
import os

url = "https://example.com"

response = requests.get(url)

soup = BeautifulSoup(response.text, "html.parser")

text = soup.get_text(separator="\n", strip=True)

os.makedirs("raw_text", exist_ok=True)

with open("raw_text/webpage.txt", "w", encoding="utf-8") as file:
    file.write(text)

print("Web page scraped successfully!")