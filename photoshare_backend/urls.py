"""
URL Configuration for PhotoShare
==================================
Replace the entire contents of photoshare_backend/urls.py with this file
"""

from django.contrib import admin
from django.urls import path, include,re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView
from api.views import (
    UserViewSet, PhotoViewSet, CommentViewSet, RatingViewSet,
    CustomAuthToken, UserRegistrationView
)

# Create router
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'photos', PhotoViewSet, basename='photo')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'ratings', RatingViewSet, basename='rating')

# URL patterns
urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication endpoints
    path('api/auth/login/', CustomAuthToken.as_view(), name='login'),
    path('api/auth/register/', UserRegistrationView.as_view({'post': 'create'}), name='register'),
    
    # API endpoints
    path('api/', include(router.urls)),
    
    # Browsable API auth
    path('api-auth/', include('rest_framework.urls')),
    re_path(r'^.*', TemplateView.as_view(template_name='index.html')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
