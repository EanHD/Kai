import os
import uuid

from rag.chroma_client import get_chroma_collection

from PyPDF2 import PdfReader

# For new file type support
from bs4 import BeautifulSoup
import docx
import csv

collection = get_chroma_collection()
DOCS_DIR = "docs"

def extract_text_from_file(file_path):
    if file_path.endswith((".txt", ".md")):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    elif file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    elif file_path.endswith((".html", ".htm")):
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            return soup.get_text()
    elif file_path.endswith(".csv"):
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            return "\n".join([", ".join(row) for row in reader])
    else:
        return None  # unsupported

def sync_documents():
    for fname in os.listdir(DOCS_DIR):
        fpath = os.path.join(DOCS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        content = extract_text_from_file(fpath)
        if content:
            doc_id = str(uuid.uuid4())
            print(f"→ Adding: {fname}")
            collection.add(
                documents=[content],
                metadatas=[{"filename": fname, "source": "folder_sync"}],
                ids=[doc_id]
            )
        else:
            print(f"⚠️ Skipped unsupported file: {fname}")

if __name__ == "__main__":
    sync_documents()
    print("✅ Sync complete.")