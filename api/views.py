"""
API Views for PhotoShare
==========================
Replace the entire contents of api/views.py with this file
"""

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend

from .models import Photo, Comment, Rating, PhotoView
from .serializers import (
    UserSerializer, UserDetailSerializer, UserRegistrationSerializer,
    PhotoListSerializer, PhotoDetailSerializer, PhotoCreateSerializer,
    CommentSerializer, CommentCreateSerializer, RatingSerializer
)

User = get_user_model()


# ============================================
# PERMISSIONS
# ============================================

class IsCreatorUser(permissions.BasePermission):
    """Only allow creator users"""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.role == 'creator'


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Only allow owners to edit"""
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'creator'):
            return obj.creator == request.user
        return False


# ============================================
# AUTHENTICATION VIEWS
# ============================================

class CustomAuthToken(ObtainAuthToken):
    """Custom login view"""
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class UserRegistrationView(viewsets.GenericViewSet):
    """User registration"""
    
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


# ============================================
# USER VIEWSET
# ============================================

class UserViewSet(viewsets.ModelViewSet):
    """User CRUD operations"""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'first_name', 'last_name', 'bio']
    ordering_fields = ['username', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user"""
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)


# ============================================
# PHOTO VIEWSET
# ============================================

class PhotoViewSet(viewsets.ModelViewSet):
    """Photo CRUD operations"""
    
    queryset = Photo.objects.filter(is_published=True).select_related('creator')
    serializer_class = PhotoListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['creator', 'location']
    search_fields = ['title', 'caption', 'location']
    ordering_fields = ['created_at', 'views_count', 'average_rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
         # 1. Start with the base query
        queryset = Photo.objects.all().select_related('creator')
        
        # 2. Apply strict creator filtering IF provided in the URL (?creator=5)
        creator_param = self.request.query_params.get('creator')
        if creator_param:
            # This overrides the "everyone" logic and forces ONLY this creator
            queryset = queryset.filter(creator_id=creator_param, is_published=True)
        else:
            # 3. Default logic if no specific creator is requested
            if self.request.user.is_authenticated and self.request.user.role == 'creator':
                queryset = queryset.filter(
                    Q(is_published=True) | Q(creator=self.request.user)
                )
            else:
                queryset = queryset.filter(is_published=True)
      
        # 4. Handle the exclude parameter
        exclude_param = self.request.query_params.get('exclude')
        if exclude_param:
            queryset = queryset.exclude(id=exclude_param)
            
        return queryset.prefetch_related('people_tagged')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PhotoCreateSerializer
        elif self.action == 'retrieve':
            return PhotoDetailSerializer
        return PhotoListSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsCreatorUser()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def retrieve(self, request, *args, **kwargs):
        """Get photo detail and track view"""
        instance = self.get_object()
        
        # Track view
        PhotoView.objects.create(
            photo=instance,
            user=request.user if request.user.is_authenticated else None,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
        
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def get_client_ip(self, request):
        """Get client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search"""
        query = request.query_params.get('q', '')
        location = request.query_params.get('location', '')
        
        queryset = self.get_queryset()
        
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(caption__icontains=query) |
                Q(creator__username__icontains=query)
            )
        
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get photo comments"""
        photo = self.get_object()
        comments = Comment.objects.filter(
            photo=photo,
            is_deleted=False,
            parent_comment=None
        ).select_related('user').order_by('created_at')
        
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def ratings(self, request, pk=None):
        """Get photo ratings"""
        photo = self.get_object()
        ratings = Rating.objects.filter(photo=photo).select_related('user')
        
        stats = ratings.aggregate(
            average=Avg('score'),
            count=Count('id')
        )
        
        serializer = RatingSerializer(ratings, many=True, context={'request': request})
        return Response({
            'statistics': stats,
            'ratings': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending photos"""
        from datetime import timedelta
        from django.utils import timezone
        
        week_ago = timezone.now() - timedelta(days=7)
        
        queryset = self.get_queryset().annotate(
            recent_views=Count(
                'views',
                filter=Q(views__viewed_at__gte=week_ago)
            )
        ).order_by('-recent_views')[:20]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ============================================
# COMMENT VIEWSET
# ============================================

class CommentViewSet(viewsets.ModelViewSet):
    """Comment CRUD operations"""
    
    queryset = Comment.objects.filter(is_deleted=False).select_related('user', 'photo')
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        return CommentSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        elif self.action == 'create':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def perform_destroy(self, instance):
        """Soft delete"""
        instance.is_deleted = True
        instance.save()
    
    def perform_update(self, serializer):
        """Mark as edited"""
        serializer.save(is_edited=True)


# ============================================
# RATING VIEWSET
# ============================================

class RatingViewSet(viewsets.ModelViewSet):
    """Rating CRUD operations"""
    
    queryset = Rating.objects.all().select_related('user', 'photo')
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        photo_id = self.request.query_params.get('photo')
        user_id = self.request.query_params.get('user')
        
        if photo_id:
            queryset = queryset.filter(photo_id=photo_id)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def rate_photo(self, request):
        """Rate a photo"""
        photo_id = request.data.get('photo')
        score = request.data.get('score')
        
        if not photo_id or not score:
            return Response(
                {'error': 'Photo ID and score are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            photo = Photo.objects.get(id=photo_id)
        except Photo.DoesNotExist:
            return Response(
                {'error': 'Photo not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        rating, created = Rating.objects.update_or_create(
            user=request.user,
            photo=photo,
            defaults={'score': score}
        )
        
        serializer = self.get_serializer(rating)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
