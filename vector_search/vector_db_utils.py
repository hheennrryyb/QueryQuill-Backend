import os
from langchain.document_loaders import PyPDFLoader, UnstructuredHTMLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

def load_documents(folder_path):
    documents = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
        elif filename.endswith('.html'):
            loader = UnstructuredHTMLLoader(file_path)
            documents.extend(loader.load())
    return documents

def chunk_texts(documents, chunk_size=1000, chunk_overlap=200):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = text_splitter.split_documents(documents)
    return chunks

def get_embeddings(chunks, model_name='all-MiniLM-L6-v2'):
    model = SentenceTransformer(model_name)
    embeddings = model.encode([chunk.page_content for chunk in chunks])
    return embeddings

def create_vector_database(folder_path):
    documents = load_documents(folder_path)
    chunks = chunk_texts(documents)
    embeddings = get_embeddings(chunks)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    
    return index, chunks

def query_vector_database(query, index, chunks, k=5):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode([query])
    distances, indices = index.search(query_embedding.astype('float32'), k)
    results = [chunks[i] for i in indices[0]]
    return results