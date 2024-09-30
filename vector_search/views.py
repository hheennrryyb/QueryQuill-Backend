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
from django.contrib.auth.models import User
from celery.result import AsyncResult
import random
import string
from django.core.files import File
import logging
import shutil
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.core.cache import cache


# Set up logger
logger = logging.getLogger('vector_search')

class BaseView(APIView):
    def get(self, request):
        stats = self.get_application_stats()

        data = {
            'message': 'Welcome to the Query Quill Vector Search Backend!',
            'website': 'https://query-quill-8pqht.ondigitalocean.app',
            'version': '1.2.0',
            'status': 'running',
            'application_stats': stats,
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'debug_mode': settings.DEBUG,
            'media_root': settings.MEDIA_ROOT,
        }

        return JsonResponse(data)

    def get_application_stats(self):
        # Use caching to avoid frequent database queries
        cache_key = 'application_stats'
        cached_stats = cache.get(cache_key)

        if cached_stats is None:
            logger.info("Cache miss for application stats, querying database")
            try:
                # Use aggregate to get counts in a single query
                doc_counts = Document.objects.aggregate(
                    total_documents=Count('document_id'),
                    processed_documents=Count('document_id', filter=Q(processed=True))
                )

                stats = {
                    'total_users': User.objects.count(),
                    'total_documents': doc_counts['total_documents'],
                    'processed_documents': doc_counts['processed_documents'],
                    'total_vector_databases': VectorDatabase.objects.count(),
                }

                # Cache the stats for 1 hour
                cache.set(cache_key, stats, 3600)
                logger.info("Application stats cached successfully")
            except Exception as e:
                logger.error(f"Error querying database for stats: {str(e)}")
                stats = {
                    'error': 'Unable to retrieve application statistics'
                }
        else:
            logger.info("Serving cached application stats")
            stats = cached_stats

        return stats

class UploadDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': 'Project ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return Response({'error': 'Vector database not found'}, status=status.HTTP_404_NOT_FOUND)
        
        files = request.FILES.getlist('documents')
        if files:
            for file in files:
                Document.objects.create(user=request.user, file=file, vector_database=vector_db)
            return Response({'message': 'Documents uploaded successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'No files were uploaded'}, status=status.HTTP_400_BAD_REQUEST)


class CreateProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        name = request.data.get('project_name')
        if not name:
            return Response({'error': 'Project name is required'}, status=status.HTTP_400_BAD_REQUEST)
        if VectorDatabase.objects.filter(user=user, name=name).exists():
            return Response({'error': 'Project with this name already exists'}, status=status.HTTP_400_BAD_REQUEST)
        
        new_project = VectorDatabase.objects.create(
            user=user,
            name=name
        )
        
        # Create project folder
        project_folder = os.path.join(settings.MEDIA_ROOT, 'documents', f'user_{user.id}', f'project_{new_project.project_id}')
        os.makedirs(project_folder, exist_ok=True)
        
        project_data = {
            'id': new_project.project_id,
            'name': new_project.name,
            'created_at': new_project.created_at.isoformat(),
            'updated_at': new_project.updated_at.isoformat(),
        }
        
        return Response({'project': project_data}, status=status.HTTP_201_CREATED)

class ProcessDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': 'Project ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return Response({'error': 'Vector database not found'}, status=status.HTTP_404_NOT_FOUND)
        
        from .tasks import process_documents_task
        task = process_documents_task.delay(project_id, request.user.id)
        
        return Response({'message': 'Document processing started', 'task_id': str(task.id)}, status=status.HTTP_202_ACCEPTED)

class QueryDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info("QueryDocumentsView.post method called")
        query = request.data.get('query')
        project_id = request.data.get('project_id')
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
            
            logger.info(f"Index path: {index_path}")
            logger.info(f"Chunks path: {chunks_path}")
            
            if not os.path.exists(index_path) or not os.path.exists(chunks_path):
                return JsonResponse({
                    'error': 'Vector database files not found. Please reprocess your documents.'
                }, status=404)
            
            index = faiss.read_index(index_path)
            logger.info("FAISS index loaded successfully")
            
            try:
                with open(chunks_path, 'rb') as f:
                    chunks = pickle.load(f)
                logger.info(f"Chunks loaded successfully. Type: {type(chunks)}, Length: {len(chunks)}")
            except Exception as e:
                logger.error(f"Error loading chunks: {str(e)}", exc_info=True)
                return JsonResponse({
                    'error': 'Error loading chunks file. Please reprocess your documents.',
                    'details': str(e)
                }, status=500)

            results = query_vector_database(query, index, chunks)
            logger.info(f"Query results obtained. Number of results: {len(results)}")
            
            formatted_results = []
            for r in results:
                try:
                    formatted_results.append({
                        'content': r['chunk'].page_content,
                        'distance': float(r['distance'])
                    })
                except AttributeError as e:
                    logger.error(f"Error formatting result: {str(e)}")
                    logger.error(f"Problematic chunk: {r['chunk']}")
                    continue
            
            return JsonResponse({'results': formatted_results})
        except Exception as e:
            logger.error(f"An error occurred while querying the vector database: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': f'An error occurred while querying the vector database: {str(e)}',
                'details': {
                    'index_path': index_path if 'index_path' in locals() else 'Not set',
                    'chunks_path': chunks_path if 'chunks_path' in locals() else 'Not set',
                    'chunks_type': type(chunks).__name__ if 'chunks' in locals() else 'Not loaded',
                    'results_type': type(results).__name__ if 'results' in locals() else 'Not generated'
                }
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
        if not url or not project_id:
            return Response({"error": "Both URL and project ID are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate URL
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return Response({"error": "Invalid URL"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "Invalid URL"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                return Response({"error": "The URL does not point to an HTML page"}, status=status.HTTP_400_BAD_REQUEST)
        
            html_content = response.text

            try:
                vector_db = VectorDatabase.objects.get(project_id=project_id, user=request.user)
            except VectorDatabase.DoesNotExist:
                return Response({'error': 'Vector database not found'}, status=status.HTTP_404_NOT_FOUND)
            
            if html_content:
                # Create a safe filename from the URL
                parsed_url = urllib.parse.urlparse(url)
                safe_filename = f"{parsed_url.netloc}{parsed_url.path}".replace('/', '_')
                if not safe_filename.endswith('.html'):
                    safe_filename += '.html'

                # Create the Document object
                document = Document(user=request.user, vector_database=vector_db)
                document.file.save(safe_filename, ContentFile(html_content.encode('utf-8')), save=True)

                return Response({'message': 'Document uploaded successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'No content was uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        except requests.RequestException as e:
            return Response({"error": f"Error fetching URL: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

        # Create the Document object
        document = Document(user=request.user, vector_database=vector_db)
        document.file.save(unique_file_name, ContentFile(text_content.encode('utf-8')), save=True)

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


# User Management Views

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

class UserSignUpView(APIView):
    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')

        if not username or not email or not password:
            return Response({
                'error': 'Username, email, and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({
                'error': 'Username already exists'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create the user
        user = User.objects.create_user(username=username, email=email, password=password)

        # Create user's document folder
        user_folder = os.path.join(settings.MEDIA_ROOT, 'documents', f'user_{user.id}')
        os.makedirs(user_folder, exist_ok=True)

        return Response({
            'message': 'User created successfully',
            'user_id': user.id,
            'username': user.username,
            'email': user.email
        }, status=status.HTTP_201_CREATED)


class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        task_id = request.GET.get('task_id')
        if not task_id:
            return JsonResponse({'error': 'Task ID is required'}, status=400)
        
        task_result = AsyncResult(task_id)
        
        # Check if the task result contains an error
        if task_result.failed():
            status = 'FAILURE'
            if isinstance(task_result.result, Exception):
                result = str(task_result.result)  # Convert the error to a string
            else:
                result = "An unknown error occurred"
        elif task_result.successful() and isinstance(task_result.result, dict) and 'error' in task_result.result:
            status = 'FAILURE'
            result = task_result.result['error']
        else:
            status = task_result.status
            result = str(task_result.result) if task_result.result is not None else None

        return JsonResponse({
            'task_id': task_id,
            'status': status,
            'result': result
        })

class DemoModeView(APIView):
    def post(self, request):
        logger.info("Demo mode activation started")

        # Generate random username and password
        username = 'demo_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        logger.debug(f"Generated demo credentials - Username: {username}")

        try:
            # Create a new user
            user = User.objects.create_user(username=username, password=password)
            logger.info(f"Created demo user with ID: {user.id}")

            # Authenticate the user
            authenticated_user = authenticate(username=username, password=password)
            if authenticated_user is None:
                raise Exception("Failed to authenticate newly created user")

            # Generate tokens
            refresh = RefreshToken.for_user(authenticated_user)

            # Create projects and copy documents
            demo_folder = os.path.join(settings.BASE_DIR, 'demo')
            projects = []

            if not os.path.exists(demo_folder):
                logger.error(f"Demo folder not found: {demo_folder}")
                return Response({
                    'error': 'Demo mode is not properly configured. Please contact the administrator.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            for project_folder in os.listdir(demo_folder):
                project_path = os.path.join(demo_folder, project_folder)
                if os.path.isdir(project_path):
                    logger.debug(f"Processing demo project folder: {project_folder}")
                    
                    # Create a new project for each folder
                    new_project = VectorDatabase.objects.create(user=user, name=project_folder)
                    logger.info(f"Created demo project: {project_folder} with ID: {new_project.project_id}")
                    
                    projects.append({
                        'name': project_folder,
                        'id': new_project.project_id
                    })

                    # Create a new directory for this project's files
                    project_media_path = os.path.join(settings.MEDIA_ROOT, 'documents', f'user_{user.id}', f'project_{new_project.project_id}')
                    os.makedirs(project_media_path, exist_ok=True)

                    faiss_index_path = None
                    chunks_path = None

                    # Copy all files from the demo project to the new project directory
                    for item in os.listdir(project_path):
                        s = os.path.join(project_path, item)
                        d = os.path.join(project_media_path, item)
                        if os.path.isfile(s):
                            shutil.copy2(s, d)
                            logger.debug(f"Copied file: {item} to {d}")
                            
                            if item == 'faiss_index':
                                faiss_index_path = os.path.relpath(d, settings.MEDIA_ROOT)
                            elif item == 'chunks.pkl':
                                chunks_path = os.path.relpath(d, settings.MEDIA_ROOT)
                            elif item not in ['chunks.pkl', 'faiss_index']:
                                relative_path = os.path.relpath(d, settings.MEDIA_ROOT)
                                document = Document.objects.create(
                                    user=user,
                                    file=relative_path,
                                    vector_database=new_project,
                                    processed=True
                                )
                                logger.info(f"Created document record: {item} with ID: {document.document_id}")
                        elif os.path.isdir(s):
                            shutil.copytree(s, d)
                            logger.debug(f"Copied directory: {item} to {d}")

                    # Update the VectorDatabase with the correct paths
                    if faiss_index_path and chunks_path:
                        new_project.index_file = faiss_index_path
                        new_project.chunks_file = chunks_path
                        new_project.save()
                        logger.info(f"Updated project {new_project.project_id} with index paths")

            response_data = {
                'message': 'Demo mode activated',
                'username': username,
                'password': password,
                'projects': projects,
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
            logger.info("Demo mode activation completed successfully")
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error during demo mode activation: {str(e)}", exc_info=True)
            return Response({
                'error': 'Demo mode activation failed. Please try again or contact support.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')

        if not project_id:
            return Response({"error": "Project ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = VectorDatabase.objects.get(project_id=project_id, user=request.user)
        except VectorDatabase.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        # Delete associated documents
        documents = Document.objects.filter(vector_database=project)
        for document in documents:
            document.delete()  # This will trigger the delete_file method

        # Delete the project directory
        project_media_path = os.path.join(settings.MEDIA_ROOT, 'documents', f'user_{request.user.id}', f'project_{project.project_id}')
        if os.path.exists(project_media_path):
            shutil.rmtree(project_media_path)

        # Delete the VectorDatabase object
        project.delete()

        return Response({"message": "Project deleted successfully"}, status=status.HTTP_200_OK)