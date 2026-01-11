"""
Serializers for PhotoShare API
================================
Create this file as: api/serializers.py
"""
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Photo, Comment, Rating, PhotoView
from django.conf import settings
User = get_user_model()
from datetime import datetime, timedelta

# ============================================
# USER SERIALIZERS
# ============================================

class UserSerializer(serializers.ModelSerializer):
    """Basic user information"""
    
    photo_count = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'bio',
            'profile_picture', 'created_at', 'photo_count','is_superuser',
        ]
        read_only_fields = ['id', 'created_at','is_superuser',]
    
    def get_photo_count(self, obj):
        return obj.photos.count()


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user information"""
    
    photo_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'bio', 'profile_picture', 'created_at', 'updated_at',
            'photo_count', 'comment_count', 'rating_count','is_superuser'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_superuser']
    
    def get_photo_count(self, obj):
        return obj.photos.filter(is_published=True).count()
    
    def get_comment_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()
    
    def get_rating_count(self, obj):
        return obj.ratings.count()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """User registration"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 
            'role'
        ]
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                "password": "Passwords do not match."
            })
        data.pop('password_confirm')
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role','consumer')
        )
        return user


# ============================================
# PHOTO SERIALIZERS
# ============================================

class PhotoListSerializer(serializers.ModelSerializer):
    """Lightweight photo list"""
    
    creator = UserSerializer(read_only=True)
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    comment_count = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    class Meta:
        model = Photo
        fields = [
            'id', 'title', 'slug', 'caption', 'location',
            'image', 'creator', 'creator_username',
            'views_count', 'average_rating', 'created_at',
            'comment_count', 'rating_count'
        ]
        read_only_fields = ['id', 'slug', 'views_count', 'average_rating', 'created_at']
    
    def get_comment_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()
    
    def get_rating_count(self, obj):
        return obj.ratings.count()

    def get_image(self, obj):
        if not obj.image:
            return None
            
        # Check if it's an Azure Blob URL
        if 'blob.core.windows.net' in obj.image.url:
            # Generate SAS token for temporary access
            from urllib.parse import urlparse
            parsed = urlparse(obj.image.url)
            blob_path = parsed.path.lstrip('/')
            
            # Generate SAS token (valid for 1 hour)
            sas_token = generate_blob_sas(
                account_name=settings.AZURE_ACCOUNT_NAME,
                container_name=settings.AZURE_CONTAINER,
                blob_name=blob_path.split('/', 1)[1] if '/' in blob_path else blob_path,
                account_key=settings.AZURE_ACCOUNT_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            return f"{obj.image.url}?{sas_token}"
        
        return obj.image.url


        # This returns the absolute URL of the image on Cloudinary's CDN
        # return obj.image.url 

class PhotoDetailSerializer(serializers.ModelSerializer):
    """Detailed photo information"""
    
    creator = UserSerializer(read_only=True)
    people_tagged = UserSerializer(many=True, read_only=True)
    comment_count = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    
    image = serializers.SerializerMethodField()
    class Meta:
        model = Photo
        fields = [
            'id', 'title', 'slug', 'caption', 'location',
            'image', 'image_width', 'image_height', 'file_size',
            'creator', 'people_tagged', 'views_count', 'average_rating',
            'created_at', 'updated_at', 'is_published',
            'comment_count', 'rating_count', 'user_rating'
        ]
        read_only_fields = [
            'id', 'slug', 'creator', 'views_count', 'average_rating',
            'created_at', 'updated_at', 'image_width', 'image_height', 'file_size'
        ]
    
    def get_comment_count(self, obj):
        return obj.comments.filter(is_deleted=False).count()
    
    def get_rating_count(self, obj):
        return obj.ratings.count()
    
    def get_user_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                rating = Rating.objects.get(photo=obj, user=request.user)
                return rating.score
            except Rating.DoesNotExist:
                return None
        return None

    def get_image(self, obj):
        if not obj.image:
            return None
            
        # Check if it's an Azure Blob URL
        if 'blob.core.windows.net' in obj.image.url:
            # Generate SAS token for temporary access
            from urllib.parse import urlparse
            parsed = urlparse(obj.image.url)
            blob_path = parsed.path.lstrip('/')
            
            # Generate SAS token (valid for 1 hour)
            sas_token = generate_blob_sas(
                account_name=settings.AZURE_ACCOUNT_NAME,
                container_name=settings.AZURE_CONTAINER,
                blob_name=blob_path.split('/', 1)[1] if '/' in blob_path else blob_path,
                account_key=settings.AZURE_ACCOUNT_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            return f"{obj.image.url}?{sas_token}"
        
        return obj.image.url




        # This returns the absolute URL of the image on Cloudinary's CDN
        # return obj.image.url 

class PhotoCreateSerializer(serializers.ModelSerializer):
    """Create photo"""
    
    people_tagged = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False
    )
    
    class Meta:
        model = Photo
        fields = [
            'title', 'caption', 'location', 'image', 'people_tagged', 'is_published'
        ]
    
    def validate_image(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "Image file size cannot exceed 10MB."
            )
        
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        ext = value.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"File type .{ext} not supported."
            )
        
        return value
    
    def create(self, validated_data):
        people_tagged = validated_data.pop('people_tagged', [])
        creator = self.context['request'].user
        photo = Photo.objects.create(creator=creator, **validated_data)
        if people_tagged:
            photo.people_tagged.set(people_tagged)
        return photo


# ============================================
# COMMENT SERIALIZERS
# ============================================

class CommentSerializer(serializers.ModelSerializer):
    """Comment serializer"""
    
    user = UserSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    reply_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'photo', 'user', 'username', 'content',
            'parent_comment', 'created_at', 'updated_at',
            'is_edited', 'is_deleted', 'reply_count'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'is_edited']
    
    def get_reply_count(self, obj):
        return obj.replies.filter(is_deleted=False).count()


class CommentCreateSerializer(serializers.ModelSerializer):
    """Create comment"""
    
    class Meta:
        model = Comment
        fields = ['photo', 'content', 'parent_comment']
    
    def create(self, validated_data):
        user = self.context['request'].user
        return Comment.objects.create(user=user, **validated_data)


# ============================================
# RATING SERIALIZERS
# ============================================

class RatingSerializer(serializers.ModelSerializer):
    """Rating serializer"""
    
    user = UserSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Rating
        fields = [
            'id', 'photo', 'user', 'username', 'score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_score(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        photo = validated_data['photo']
        score = validated_data['score']
        
        rating, created = Rating.objects.update_or_create(
            user=user,
            photo=photo,
            defaults={'score': score}
        )
        
        return rating
