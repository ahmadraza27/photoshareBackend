"""
Database Models for PhotoShare
================================
Replace the entire contents of api/models.py with this file
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.text import slugify
import uuid


class User(AbstractUser,PermissionsMixin):
    """Custom User Model with roles"""
    
    ROLE_CHOICES = [
        ('creator', 'Creator'),
        ('consumer', 'Consumer'),
    ]
    
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='consumer'
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )
    
    bio = models.TextField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def is_creator(self):
        return self.role == 'creator'
    
    def is_consumer(self):
        return self.role == 'consumer'



class Photo(models.Model):
    """Photo Model"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='photos',
        limit_choices_to={'role': 'creator'}
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    caption = models.TextField(max_length=2000, blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='')

    people_tagged = models.ManyToManyField(
        User,
        related_name='tagged_in_photos',
        blank=True
    )

    image = models.ImageField(
        upload_to="photos/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp']
            )
        ]
    )

    image_width = models.IntegerField(null=True, blank=True)
    image_height = models.IntegerField(null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)

    views_count = models.IntegerField(default=0)

    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.0
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.creator.username}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Photo.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if self.image:
            self.image_width = self.image.width
            self.image_height = self.image.height
            self.file_size = self.image.size

        super().save(*args, **kwargs)
    def update_average_rating(self):
        """Update average rating from all ratings"""
        from django.db.models import Avg
        result = self.ratings.aggregate(average=Avg('score'))
        self.average_rating = result['average'] or 0.0
        self.save(update_fields=['average_rating'])

class Comment(models.Model):
    """Comment Model"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    photo = models.ForeignKey(
        Photo,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    content = models.TextField(max_length=1000)
    
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['photo', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.photo.title}"


class Rating(models.Model):
    """Rating Model"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    photo = models.ForeignKey(
        Photo,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    
    score = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
        unique_together = ['photo', 'user']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['photo', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} rated {self.photo.title}: {self.score}/5"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.photo.update_average_rating()


class PhotoView(models.Model):
    """Track photo views"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    photo = models.ForeignKey(
        Photo,
        on_delete=models.CASCADE,
        related_name='views'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='photo_views'
    )
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Photo View'
        verbose_name_plural = 'Photo Views'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['photo', '-viewed_at']),
        ]
    
    def __str__(self):
        viewer = self.user.username if self.user else 'Anonymous'
        return f"{viewer} viewed {self.photo.title}"
