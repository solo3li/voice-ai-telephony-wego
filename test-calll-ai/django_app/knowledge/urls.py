from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    path('documents/', views.list_documents, name='list_documents'),
    path('documents/upload/', views.upload_document, name='upload_document'),
    path('documents/<int:doc_id>/delete/', views.delete_document, name='delete_document'),
    path('internal/rag/', views.api_internal_rag_search, name='api_internal_rag_search'),
]
