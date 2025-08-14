import os
import uuid
import hashlib
from typing import List

from rag.chroma_client import docs_collection, make_chunk_id

from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import docx
import csv

DOCS_DIR = "docs"
MAX_CHARS = 1200   # ~800–1000 tokens depending on language
OVERLAP = 150


def _chunk(text: str) -> List[str]:
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + MAX_CHARS)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        i = j - OVERLAP
        if i < 0:
            i = 0
        if i >= n:
            break
    return chunks


def extract_text_from_file(file_path):
    if file_path.endswith((".txt", ".md")):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    if file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    if file_path.endswith((".html", ".htm")):
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            return soup.get_text()
    if file_path.endswith(".csv"):
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            return "\n".join([", ".join(row) for row in reader])
    return None  # unsupported


def sync_documents():
    col = docs_collection()
    added = 0
    skipped = 0

    for fname in os.listdir(DOCS_DIR):
        fpath = os.path.join(DOCS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        content = extract_text_from_file(fpath)
        if not content:
            print(f"⚠️  Skipped unsupported or empty file: {fname}")
            continue
        chunks = _chunk(content)
        ids = []
        docs = []
        metas = []
        for idx, chunk in enumerate(chunks):
            cid = make_chunk_id(fname, chunk)
            ids.append(cid)
            docs.append(chunk)
            metas.append({
                "filename": fname,
                "source": "folder_sync",
                "chunk": idx,
            })
        # Check which ids already exist to avoid duplicates
        # Chroma doesn't have a native bulk-exists, so we try to fetch and filter
        existing = set()
        try:
            existing_resp = col.get(ids=ids)
            for eid in existing_resp.get("ids", []):
                existing.add(eid)
        except Exception:
            pass
        new_ids = [i for i in ids if i not in existing]
        if not new_ids:
            skipped += len(ids)
            continue
        new_docs = [doc for i, doc in zip(ids, docs) if i in new_ids]
        new_metas = [m for i, m in zip(ids, metas) if i in new_ids]
        col.add(ids=new_ids, documents=new_docs, metadatas=new_metas)
        added += len(new_ids)
        print(f"→ {fname}: added {len(new_ids)} / {len(ids)} chunks; skipped {len(ids) - len(new_ids)} duplicates")

    print(f"✅ Sync complete. Added {added} new chunks; skipped {skipped} (existing or empty).")


if __name__ == "__main__":
    if not os.path.isdir(DOCS_DIR):
        os.makedirs(DOCS_DIR, exist_ok=True)
    sync_documents()