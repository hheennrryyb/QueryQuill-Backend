from celery import shared_task
from .vector_db_utils import create_vector_database
import os
import faiss
import pickle
from django.conf import settings
from .models import Document, VectorDatabase
from vector_search_project.celery import app
import logging
logger = logging.getLogger('vector_search')

@app.task
def process_documents_task(project_id, user_id):
    logger.info(f"Starting process_documents_task for project_id={project_id}, user_id={user_id}")
    try:
        vector_db = VectorDatabase.objects.get(project_id=project_id, user_id=user_id)
        documents = Document.objects.filter(user_id=user_id, processed=False, vector_database=vector_db)
        
        if not documents:
            return {'message': 'No unprocessed documents found for this project'}
        
        user_folder = f'user_{user_id}'
        project_folder = f'project_{project_id}'
        folder_path = os.path.join(settings.MEDIA_ROOT, 'documents', user_folder, project_folder)
        os.makedirs(folder_path, exist_ok=True)
        
        processed_docs = []

        logger.info("folder_path: ", folder_path)
        for doc in documents:
            try:
                doc.processed = True
                doc.save()
                processed_docs.append(doc)
            except Exception as e:
                doc.processed = False
                doc.save()
                raise Exception(f"Error processing document {doc.id}: {str(e)}")
        
        index, chunks = create_vector_database(folder_path)


        if index is None or chunks is None:
            for doc in processed_docs:
                doc.processed = False
                doc.save()
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
        
        logger.info("process_documents_task completed successfully")
        return {"success": True, "message": "Documents processed successfully"}
    except Exception as e:
        logger.exception(f"Error in process_documents_task: {str(e)}")
        for doc in Document.objects.filter(user_id=user_id, vector_database=vector_db):
            doc.processed = False
            doc.save()
        return {"error": f"Failed to process documents: {str(e)}"}

@app.task
def test_task(x, y):
    logger.info(f"Starting test_task with arguments: x={x}, y={y}")
    result = x + y
    logger.info(f"test_task completed. Result: {result}")
    return result