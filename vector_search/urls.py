from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.user_login, name='user_login'),
    path('upload/', views.upload_document, name='upload_document'),
    path('process/', views.process_documents, name='process_documents'),
    path('query/', views.query_documents, name='query_documents'),
]