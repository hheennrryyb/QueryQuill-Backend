import os
import torch
import faiss
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader, UnstructuredHTMLLoader, TextLoader, DirectoryLoader
import numpy as np

# Set up logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def load_documents(folder_path):
    loaders = {
        '.pdf': (PyPDFLoader, {}),
        '.html': (UnstructuredHTMLLoader, {}),
        '.txt': (TextLoader, {'encoding': 'utf8'})
    }
    
    for ext, (loader_class, loader_args) in loaders.items():
        glob_pattern = f'**/*{ext}'
        try:
            loader = DirectoryLoader(folder_path, glob=glob_pattern, loader_cls=loader_class, loader_kwargs=loader_args)
            yield from loader.load()
        except Exception as e:
            logging.error(f"Error loading {ext} documents: {str(e)}")

def chunk_texts(documents, chunk_size=1000, chunk_overlap=200):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    for document in documents:
        yield from text_splitter.split_documents([document])

def get_embeddings(chunks, model_name='all-MiniLM-L6-v2', batch_size=32):
    try:
        model = SentenceTransformer(model_name)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logging.info(f"Using device: {device}")
        model = model.to(device)
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_embeddings = model.encode([chunk.page_content for chunk in batch], 
                                            device=device, 
                                            show_progress_bar=True)
            yield from batch_embeddings
    except Exception as e:
        logging.error(f"Error in get_embeddings: {str(e)}")
        raise

def create_vector_database(folder_path):
    try:
        documents = list(load_documents(folder_path))
        
        if not documents:
            logging.warning("No documents were loaded. Check the folder path and file types.")
            return None, None
        
        chunks = list(chunk_texts(documents))
        
        if not chunks:
            logging.warning("No chunks were created. Check the chunking process.")
            return None, None
        
        embeddings = list(get_embeddings(chunks))
        embeddings_array = np.array(embeddings)
        
        if embeddings_array.size == 0:
            logging.warning("No embeddings were created. Check the embedding process.")
            return None, None
        
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        
        if faiss.get_num_gpus() > 0:
            logging.info("Using GPU for FAISS")
            res = faiss.StandardGpuResources()
            index = faiss.index_cpu_to_gpu(res, 0, index)
        else:
            logging.info("Using CPU for FAISS")
        
        index.add(embeddings_array.astype('float32'))
        logging.info(f"Created FAISS index with {index.ntotal} vectors")
        
        return index, chunks
    except Exception as e:
        logging.error(f"Error in create_vector_database: {str(e)}", exc_info=True)
        return None, None

def query_vector_database(query, index, chunks, k=5, model_name='all-MiniLM-L6-v2'):
    logging.info(f"Querying vector database with: '{query}'")
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
        # logging.info(f"Found {len(sorted_results)} results")
        return sorted_results
    except Exception as e:
        logging.error(f"Error in query_vector_database: {str(e)}")
        raise

# # Example usage and debugging
# if __name__ == "__main__":
#     try:
#         folder_path = "path/to/your/documents"
#         index, chunks = create_vector_database(folder_path)
#         print(f"Created index with {index.ntotal} vectors and {len(chunks)} chunks")
        
#         query = "Your test query here"
#         results = query_vector_database(query, index, chunks)
#         print(f"Query results:")
#         for i, result in enumerate(results):
#             print(f"Result {i+1}:")
#             print(f"  Distance: {result['distance']}")
#             print(f"  Content: {result['chunk'].page_content[:100]}...")  # Print first 100 chars
#     except Exception as e:
#         logging.error(f"Error in main execution: {str(e)}")