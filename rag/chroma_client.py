import chromadb

def get_chroma_collection(name="rag"):
    client = chromadb.Client()
    return client.get_or_create_collection(name=name)