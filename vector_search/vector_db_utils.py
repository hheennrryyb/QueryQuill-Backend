import os
import torch
import faiss
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader, UnstructuredHTMLLoader, TextLoader, DirectoryLoader
import PyPDF2
import numpy as np


logger = logging.getLogger('vector_search')

def load_documents(folder_path):
    logger.info(f"Loading documents from {folder_path}")
    loaders = {
        '.pdf': (PyPDFLoader, {}),
        '.html': (UnstructuredHTMLLoader, {}),
        '.txt': (TextLoader, {'encoding': 'utf8'})
    }
    
    documents = []
    for ext, (loader_class, loader_args) in loaders.items():
        glob_pattern = f'**/*{ext}'
        try:
            loader = DirectoryLoader(folder_path, glob=glob_pattern, loader_cls=loader_class, loader_kwargs=loader_args)
            docs = loader.load()
            documents.extend(docs)
            logger.info(f"Loaded {len(docs)} {ext} documents")
        except Exception as e:
            logger.error(f"Error loading {ext} documents: {str(e)}")
    
    logger.info(f"Total documents loaded: {len(documents)}")
    return documents

def chunk_texts(documents, chunk_size=1000, chunk_overlap=200):
    # logger.info(f"Chunking {len(documents)} documents")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = text_splitter.split_documents(documents)
    # logger.info(f"Created {len(chunks)} chunks")
    return chunks

def get_embeddings(chunks, model_name='all-MiniLM-L6-v2', batch_size=32):
    logger.info(f"Getting embeddings for {len(chunks)} chunks using model {model_name}")
    try:
        model = SentenceTransformer(model_name)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Using device: {device}")
        model = model.to(device)
        
        embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_embeddings = model.encode([chunk.page_content for chunk in batch], 
                                            device=device, 
                                            show_progress_bar=True)
            embeddings.extend(batch_embeddings)
        
        embeddings_array = np.array(embeddings)
        logger.info(f"Created embeddings array of shape {embeddings_array.shape}")
        return embeddings_array
    except Exception as e:
        logger.error(f"Error in get_embeddings: {str(e)}")
        raise

def create_vector_database(folder_path):
    logger.info(f"Starting create_vector_database for folder: {folder_path}")
    try:
        documents = load_documents(folder_path)
        logger.info(f"Loaded {len(documents)} documents")

        if not documents:
            logger.warning("No documents loaded. Returning None.")
            return None, None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            logger.warning("No chunks created. Returning None.")
            return None, None

        model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded SentenceTransformer model")

        embeddings = model.encode([chunk.page_content for chunk in chunks])
        logger.info(f"Created {len(embeddings)} embeddings")

        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)
        logger.info(f"Created FAISS index with {index.ntotal} vectors")

        return index, chunks
    except Exception as e:
        logger.exception(f"Error in create_vector_database: {str(e)}")
        return None, None

def query_vector_database(query, index, chunks, k=5, model_name='all-MiniLM-L6-v2'):
    logger.info(f"Querying vector database with: '{query}'")
    try:
        model = SentenceTransformer(model_name)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = model.to(device)
        
        query_embedding = model.encode([query], device=device)
        distances, indices = index.search(query_embedding.astype('float32'), k)
        
        results = []
        for i, dist in zip(indices[0], distances[0]):
            results.append({
                'chunk': chunks[i],
                'distance': dist
            })
        
        sorted_results = sorted(results, key=lambda x: x['distance'])
        # logger.info(f"Found {len(sorted_results)} results")
        return sorted_results
    except Exception as e:
        logger.error(f"Error in query_vector_database: {str(e)}")
        raise

# Example usage and debugging
# python -m vector_search.vector_db_utils
# if __name__ == "__main__":
#     try:
#         folder_path = "/Users/henry/Desktop/Chat Bot/VectorDB/vector_search_project/media/documents/user_18/project_032ab0aa"
#         documents = load_documents(folder_path)
#         print(documents)
#         index, chunks = create_vector_database(folder_path)
#         logger.info(f"Created index with {index.ntotal} vectors and {len(chunks)} chunks")
        
#         query = "Your test query here"
#         results = query_vector_database(query, index, chunks)
#         print(f"Query results:")
#         for i, result in enumerate(results):
#             print(f"Result {i+1}:")
#             print(f"  Distance: {result['distance']}")
#             print(f"  Content: {result['chunk'].page_content[:100]}...")  # Print first 100 chars
#     except Exception as e:
#         logger.error(f"Error in main execution: {str(e)}")