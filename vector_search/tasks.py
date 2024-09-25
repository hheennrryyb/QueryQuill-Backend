from celery import shared_task
from .vector_db_utils import create_vector_database
import os
import faiss
import pickle
from django.conf import settings
from .models import Document, VectorDatabase
from vector_search_project.celery import app

@app.task
def process_documents_task(project_id, user_id):
    try:
        vector_db = VectorDatabase.objects.get(project_id=project_id, user_id=user_id)
        documents = Document.objects.filter(user_id=user_id, processed=False, vector_database=vector_db)
        
        if not documents:
            return {'message': 'No unprocessed documents found for this project'}
        
        user_folder = f'user_{user_id}'
        project_folder = f'project_{project_id}'
        folder_path = os.path.join(settings.MEDIA_ROOT, 'documents', user_folder, project_folder)
        os.makedirs(folder_path, exist_ok=True)
        
        for doc in documents:
            file_name = os.path.basename(doc.file.name)
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'wb') as f:
                f.write(doc.file.read())
        
        index, chunks = create_vector_database(folder_path)
        
        if index is None or chunks is None:
            return {'error': 'Failed to create vector database. Check the logs for more information.'}
        
        index_path = os.path.join(folder_path, 'faiss_index')
        chunks_path = os.path.join(folder_path, 'chunks.pkl')
        
        faiss.write_index(index, index_path)
        with open(chunks_path, 'wb') as f:
            pickle.dump(chunks, f)
        
        relative_index_path = os.path.relpath(index_path, settings.MEDIA_ROOT)
        relative_chunks_path = os.path.relpath(chunks_path, settings.MEDIA_ROOT)
        
        vector_db.index_file = relative_index_path
        vector_db.chunks_file = relative_chunks_path
        vector_db.save()

        for doc in documents:
            doc.processed = True
            doc.save()

        return {'message': 'Documents processed and vector database updated successfully'}
    except Exception as e:
        return {'error': f'An error occurred while processing documents: {str(e)}'}