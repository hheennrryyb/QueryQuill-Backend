from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('upload/', views.UploadDocumentView.as_view(), name='upload_document'),
    path('create_project/', views.CreateProjectView.as_view(), name='create_project'),
    path('process/', views.ProcessDocumentsView.as_view(), name='process_documents'),
    path('query/', views.QueryDocumentsView.as_view(), name='query_documents'),
    path('login/', views.UserLoginView.as_view(), name='user_login'),
    path('logout/', views.UserLogoutView.as_view(), name='user_logout'),
    path('projects/', views.ProjectExplorerView.as_view(), name='project_explorer'),
    path('project_detail/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('scrape_url/', views.ScrapeUrlView.as_view(), name='scrape_url'),

    # JWT token endpoints
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]