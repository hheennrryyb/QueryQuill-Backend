from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Document, VectorDatabase
import os
from .vector_db_utils import create_vector_database, query_vector_database
import faiss
import pickle

from django.contrib.auth.decorators import login_required

from django.contrib.auth import authenticate, login

from django.conf import settings


@csrf_exempt
@login_required
def upload_document(request):
    if request.method == 'POST':
        files = request.FILES.getlist('documents')
        if files:
            for file in files:
                Document.objects.create(user=request.user, file=file)
            return JsonResponse({'message': 'Documents uploaded successfully'}, status=200)
        else:
            return JsonResponse({'error': 'No files were uploaded'}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@login_required
def process_documents(request):
    if request.method == 'POST':
        documents = Document.objects.filter(user=request.user, processed=False)
        if not documents:
            return JsonResponse({'message': 'No unprocessed documents found'}, status=200)
        
        user_folder = f'user_{request.user.id}'
        folder_path = os.path.join(settings.MEDIA_ROOT, 'documents', user_folder)
        os.makedirs(folder_path, exist_ok=True)
        
        for doc in documents:
            file_name = os.path.basename(doc.file.name)
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, 'wb') as f:
                f.write(doc.file.read())
            doc.processed = True
            doc.save()
        
        try:
            index, chunks = create_vector_database(folder_path)
            
            index_path = os.path.join(folder_path, 'faiss_index')
            chunks_path = os.path.join(folder_path, 'chunks.pkl')
            
            faiss.write_index(index, index_path)
            with open(chunks_path, 'wb') as f:
                pickle.dump(chunks, f)
            
            relative_index_path = os.path.relpath(index_path, settings.MEDIA_ROOT)
            relative_chunks_path = os.path.relpath(chunks_path, settings.MEDIA_ROOT)
            
            VectorDatabase.objects.create(
                user=request.user,
                index_file=relative_index_path,
                chunks_file=relative_chunks_path
            )
            
            return JsonResponse({'message': 'Documents processed and vector database created successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred while processing documents: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

    if request.method == 'POST':
        user = request.user
        documents = Document.objects.filter(user=user, processed=False)
        if documents:
            folder_path = os.path.join('media', 'documents', str(user.id))
            os.makedirs(folder_path, exist_ok=True)
            for doc in documents:
                file_path = os.path.join(folder_path, doc.file.name.split('/')[-1])
                with open(file_path, 'wb') as f:
                    f.write(doc.file.read())
                doc.processed = True
                doc.save()
            
            index, chunks = create_vector_database(folder_path)
            
            index_path = os.path.join(folder_path, 'faiss_index')
            chunks_path = os.path.join(folder_path, 'chunks.pkl')
            
            faiss.write_index(index, index_path)
            with open(chunks_path, 'wb') as f:
                pickle.dump(chunks, f)
            
            VectorDatabase.objects.create(
                user=user,
                index_file=index_path,
                chunks_file=chunks_path
            )
            
            return JsonResponse({'message': 'Documents processed and vector database created'})
        else:
            return JsonResponse({'message': 'No documents to process'})

@csrf_exempt
@login_required
def query_documents(request):
    if request.method == 'POST':
        query = request.POST.get('query')
        if not query:
            return JsonResponse({'error': 'No query provided'}, status=400)
        
        try:
            vector_db = VectorDatabase.objects.filter(user=request.user).latest('created_at')
        except VectorDatabase.DoesNotExist:
            return JsonResponse({
                'error': 'No vector database found for this user. Please upload and process documents first.'
            }, status=404)
        
        try:
            index_path = os.path.join(settings.MEDIA_ROOT, vector_db.index_file.name)
            chunks_path = os.path.join(settings.MEDIA_ROOT, vector_db.chunks_file.name)
            
            if not os.path.exists(index_path) or not os.path.exists(chunks_path):
                return JsonResponse({
                    'error': 'Vector database files not found. Please reprocess your documents.'
                }, status=404)
            
            index = faiss.read_index(index_path)
            with open(chunks_path, 'rb') as f:
                chunks = pickle.load(f)
            
            results = query_vector_database(query, index, chunks)
            return JsonResponse({'results': [r.page_content for r in results]})
        except Exception as e:
            return JsonResponse({
                'error': f'An error occurred while querying the vector database: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'message': 'Login successful'}, status=200)
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status=401)
    elif request.method == 'GET':
        return JsonResponse({'message': 'Please send a POST request with username and password'}, status=200)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)