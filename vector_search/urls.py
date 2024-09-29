from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('', views.BaseView.as_view(), name='base'),
    # Document Management
    path('upload/', views.UploadDocumentView.as_view(), name='upload_document'),
    path('upload_text_document/', views.SaveTextDocumentView.as_view(), name='save_text_document'),
    path('create_project/', views.CreateProjectView.as_view(), name='create_project'),
    path('process/', views.ProcessDocumentsView.as_view(), name='process_documents'),
    path('query/', views.QueryDocumentsView.as_view(), name='query_documents'),
    path('scrape_url/', views.ScrapeUrlView.as_view(), name='scrape_url'),
    path('document_preview/', views.DocumentPreviewView.as_view(), name='document_preview'),
    path('delete_document/', views.DeleteDocumentView.as_view(), name='delete_document'),
    path('delete_project/', views.DeleteProjectView.as_view(), name='delete_project'),
    path('task_status/', views.TaskStatusView.as_view(), name='task_status'),

    # Project Management
    path('projects/', views.ProjectExplorerView.as_view(), name='project_explorer'),
    path('project_detail/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),

    # User Accounts
    path('login/', views.UserLoginView.as_view(), name='user_login'),
    path('logout/', views.UserLogoutView.as_view(), name='user_logout'),
    path('create_user/', views.UserSignUpView.as_view(), name='user_signup'),

    # JWT token endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    #Demo mode
    path('demo/', views.DemoModeView.as_view(), name='demo_mode'),
]