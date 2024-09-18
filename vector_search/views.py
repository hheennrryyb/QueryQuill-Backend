from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.middleware.csrf import get_token 
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Document, VectorDatabase
import os
from .vector_db_utils import create_vector_database, query_vector_database
import faiss
import pickle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
import requests
from urllib.parse import urlparse
from django.core.files.base import ContentFile
import urllib.parse
from django.core.files.storage import default_storage
from bs4 import BeautifulSoup
import PyPDF2
import uuid

# import logging


class UploadDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return JsonResponse({'error': 'Project ID is required'}, status=400)
        
        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return JsonResponse({'error': 'Vector database not found'}, status=404)
        
        files = request.FILES.getlist('documents')
        if files:
            for file in files:
                Document.objects.create(user=request.user, file=file, vector_database=vector_db)
            return JsonResponse({'message': 'Documents uploaded successfully'}, status=200)
        else:
            return JsonResponse({'error': 'No files were uploaded'}, status=400)

class CreateProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        name = request.data.get('project_name')
        if not name:
            return JsonResponse({'error': 'Project name is required'}, status=400)
        if VectorDatabase.objects.filter(user=user, name=name).exists():
            return JsonResponse({'error': 'Project with this name already exists'}, status=400)
        
        new_project = VectorDatabase.objects.create(
            user=user,
            name=name
        )
        
        project_data = {
            'id': new_project.project_id,
            'name': new_project.name,
            'created_at': new_project.created_at.isoformat(),
            'updated_at': new_project.updated_at.isoformat(),
        }
        
        return JsonResponse({'project': project_data}, status=201)

class ProcessDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return JsonResponse({'error': 'Project ID is required'}, status=400)
        
        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return JsonResponse({'error': 'Vector database not found'}, status=404)
        
        documents = Document.objects.filter(user=request.user, processed=False, vector_database=vector_db)
        if not documents:
            return JsonResponse({'message': 'No unprocessed documents found for this project'}, status=200)
        
        user_folder = f'user_{request.user.id}'
        project_folder = f'project_{project_id}'
        folder_path = os.path.join(settings.MEDIA_ROOT, 'documents', user_folder, project_folder)
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
            
            vector_db.index_file = relative_index_path
            vector_db.chunks_file = relative_chunks_path
            vector_db.save()
            
            return JsonResponse({'message': 'Documents processed and vector database updated successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred while processing documents: {str(e)}'}, status=500)

class QueryDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query')
        project_id = request.data.get('project_id')
        logging.info(f"Query: {query}")
        logging.info(f"Project ID: {project_id}")
        if not query:
            return JsonResponse({'error': 'No query provided'}, status=400)
        
        if not project_id:
            return JsonResponse({'error': 'No project ID provided'}, status=400)
        
        try:
            vector_db = VectorDatabase.objects.get(user=request.user, project_id=project_id)
        except VectorDatabase.DoesNotExist:
            return JsonResponse({
                'error': 'No vector database found for this user. Please upload and process documents first.'
            }, status=404)
        
        try:
            index_path = os.path.join(settings.MEDIA_ROOT, vector_db.index_file.name)
            chunks_path = os.path.join(settings.MEDIA_ROOT, vector_db.chunks_file.name)
            logging.info(f"Index path: {index_path}")
            logging.info(f"Chunks path: {chunks_path}")
            if not os.path.exists(index_path) or not os.path.exists(chunks_path):
                return JsonResponse({
                    'error': 'Vector database files not found. Please reprocess your documents.'
                }, status=404)
            
            index = faiss.read_index(index_path)
            logging.info(f"Index: {index}")
            with open(chunks_path, 'rb') as f:
                chunks = pickle.load(f)

            results = query_vector_database(query, index, chunks)
            logging.info(f"Results: {results}")
            # Format results to match the expected output
            formatted_results = [
                {
                    'content': r['chunk'].page_content,
                    'distance': float(r['distance'])  # Convert numpy.float32 to Python float
                }
                for r in results
            ]
            logging.info(f"Formatted results: {formatted_results}")
            
            return JsonResponse({'results': formatted_results})
        except Exception as e:
            return JsonResponse({
                'error': f'An error occurred while querying the vector database: {str(e)}'
            }, status=500)

class ProjectExplorerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_projects = VectorDatabase.objects.filter(user=request.user)
        project_data = [
            {
                'id': project.project_id,
                'name': project.name,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
            }
            for project in user_projects
        ]
        return JsonResponse({'projects': project_data}, status=200)


class UserLoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id,
                'username': user.username,
                'email': user.email
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            # Optional: Blacklist all tokens for the user
            # user = request.user
            # tokens = OutstandingToken.objects.filter(user_id=user.id)
            # for token in tokens:
            #     BlacklistedToken.objects.get_or_create(token=token)

            return Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }
        return Response(profile_data, status=status.HTTP_200_OK)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        
        if not project_id:
            return Response({"error": "Project ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get the project
            project = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get all documents associated with this project
        documents = Document.objects.filter(vector_database=project)

        # Prepare the project data
        project_data = {
            'id': project.project_id,
            'name': project.name,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'files': [
                {
                    'id': doc.document_id,
                    'name': doc.file.name,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'processed': doc.processed,
                    'file_path': doc.file.path,
                    'file_size': doc.file.size,
                }
                for doc in documents
            ]
        }

        return Response(project_data, status=status.HTTP_200_OK)

class ScrapeUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = request.data.get('url')
        project_id = request.data.get('project_id')
        if not url:
            return HttpResponse("Please provide a URL", status=400)
        # Validate URL
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return HttpResponse("Invalid URL", status=400)
        except ValueError:
            return HttpResponse("Invalid URL", status=400)
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                return HttpResponse("The URL does not point to an HTML page", status=400)
        
            html_content = response.text

            try:
                vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
            except VectorDatabase.DoesNotExist:
                return JsonResponse({'error': 'Vector database not found'}, status=404)
            
            if html_content:
                # Create a safe filename from the URL
                parsed_url = urllib.parse.urlparse(url)
                safe_filename = f"{parsed_url.netloc}{parsed_url.path}".replace('/', '_')
                if not safe_filename.endswith('.html'):
                    safe_filename += '.html'

                # Create a ContentFile from the HTML content
                content_file = ContentFile(html_content.encode('utf-8'), name=safe_filename)

                # Create the Document object
                Document.objects.create(
                    user=request.user,
                    file=content_file,
                    vector_database=vector_db
                )
                return JsonResponse({'message': 'Document uploaded successfully'}, status=200)
            else:
                return JsonResponse({'error': 'No content was uploaded'}, status=400)
        
        except requests.RequestException as e:
            return HttpResponse(f"Error fetching URL: {str(e)}", status=500)

class DocumentPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        document_id = request.data.get('document_id')
        project_id = request.data.get('project_id')

        if not document_id or not project_id:
            return Response({"error": "Both document_id and project_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
            document = Document.objects.get(document_id=document_id, vector_database=vector_db)
        except (VectorDatabase.DoesNotExist, Document.DoesNotExist):
            return Response({"error": "Document or project not found"}, status=status.HTTP_404_NOT_FOUND)

        file_path = document.file.path
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_name)[1].lower()

        preview_content = ""

        if file_extension == '.pdf':
            preview_content = self.preview_pdf(file_path)
        elif file_extension in ['.html', '.htm']:
            preview_content = self.preview_html(file_path)
        elif file_extension == '.txt':
            preview_content = self.preview_txt(file_path)
        else:
            return Response({"error": "Unsupported file type"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "file_name": file_name,
            "preview_content": preview_content
        }, status=status.HTTP_200_OK)

    def preview_pdf(self, file_path, max_pages=10):
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            preview_content = ""

            for page in range(min(num_pages, max_pages)):
                preview_content += pdf_reader.pages[page].extract_text() + "\n\n"

        return preview_content.strip()

    def preview_html(self, file_path, max_chars=50000):
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'html.parser')
            text = soup.get_text(separator=' ')  # Use space as separator
            text = ' '.join(text.split())  # Remove extra whitespace
            preview_content = text[:max_chars] + "..." if len(text) > max_chars else text

        return preview_content.strip()

    def preview_txt(self, file_path, max_chars=50000):
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read(max_chars)
            preview_content = text + "..." if len(text) == max_chars else text

        return preview_content.strip()

class DeleteDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        document_id = request.data.get('document_id')
        project_id = request.data.get('project_id')

        if not document_id or not project_id:
            return Response({"error": "Both document_id and project_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
            document = Document.objects.get(document_id=document_id, vector_database=vector_db)
        except VectorDatabase.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
        except Document.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

        # Delete the file from storage
        if document.file:
            if os.path.isfile(document.file.path):
                os.remove(document.file.path)

        # Delete the document from the database
        document.delete()

        return Response({"message": "Document deleted successfully"}, status=status.HTTP_200_OK)

class SaveTextDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        text_content = request.data.get('text_content')
        title = request.data.get('title')

        if not all([project_id, text_content]):
            return Response({
                'error': 'Project ID and text content are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return Response({
                'error': 'Vector database not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Generate file name based on title or random UUID
        if title:
            file_name = self.sanitize_filename(title)
        else:
            file_name = f"document_{uuid.uuid4().hex[:8]}"

        # Ensure the file name has a .txt extension
        if not file_name.lower().endswith('.txt'):
            file_name += '.txt'

        # Create a unique file name to avoid conflicts
        unique_file_name = f"{uuid.uuid4().hex}_{file_name}"

        # Create a ContentFile from the text content
        content_file = ContentFile(text_content.encode('utf-8'), name=unique_file_name)

        # Create the Document object
        document = Document.objects.create(
            user=request.user,
            file=content_file,
            vector_database=vector_db
        )

        return Response({
            'message': 'Text document saved successfully',
            'document_id': document.document_id,
            'file_name': unique_file_name
        }, status=status.HTTP_201_CREATED)

    def sanitize_filename(self, filename):
        # Remove or replace characters that are unsafe for filenames
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        return filename.strip()


