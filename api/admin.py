"""
Enhanced Admin Configuration
=============================
Replace the entire api/admin.py file
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import User, Photo, Comment, Rating, PhotoView


class CustomUserCreationForm(UserCreationForm):
    """Custom form for creating users in admin"""
    
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        initial='consumer',
        help_text='Select Creator to give upload permissions'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'first_name', 'last_name')


class CustomUserChangeForm(UserChangeForm):
    """Custom form for editing users in admin"""
    
    class Meta:
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom user admin with role management
    Only admins can create creator accounts
    """
    
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = ['username', 'email', 'role', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    # Fields when editing existing user
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {
            'fields': ('role', 'bio', 'profile_picture'),
            'description': 'Role: Creator can upload photos, Consumer can view/rate/comment'
        }),
    )
    
    # Fields when creating new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name'),
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_staff', 'is_superuser'),
            'description': '⚠️ IMPORTANT: Only select "Creator" for verified content creators'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Log when admin creates a creator account"""
        if not change and obj.role == 'creator':
            # Log creator account creation
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'Admin {request.user.username} created creator account: {obj.username}')
        super().save_model(request, obj, form, change)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    """Photo admin"""
    
    list_display = ['title', 'creator', 'views_count', 'average_rating', 'is_published', 'created_at']
    list_filter = ['is_published', 'created_at']
    search_fields = ['title', 'caption', 'location', 'creator__username']
    readonly_fields = ['slug', 'views_count', 'average_rating', 'created_at', 'updated_at', 
                       'image_width', 'image_height', 'file_size']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'creator', 'caption', 'location')
        }),
        ('Image', {
            'fields': ('image', 'image_width', 'image_height', 'file_size')
        }),
        ('Statistics', {
            'fields': ('views_count', 'average_rating'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_published', 'people_tagged')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['people_tagged']
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('creator')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Comment admin"""
    
    list_display = ['user', 'photo', 'content_preview', 'is_edited', 'is_deleted', 'created_at']
    list_filter = ['is_edited', 'is_deleted', 'created_at']
    search_fields = ['content', 'user__username', 'photo__title']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'photo')


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """Rating admin"""
    
    list_display = ['user', 'photo', 'score', 'created_at']
    list_filter = ['score', 'created_at']
    search_fields = ['user__username', 'photo__title']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'photo')


@admin.register(PhotoView)
class PhotoViewAdmin(admin.ModelAdmin):
    """Photo view admin"""
    
    list_display = ['photo', 'user', 'ip_address', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['photo__title', 'user__username', 'ip_address']
    readonly_fields = ['viewed_at']
    ordering = ['-viewed_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'photo')


# Customize admin site headers
admin.site.site_header = 'PhotoShare Administration'
admin.site.site_title = 'PhotoShare Admin'
admin.site.index_title = 'Welcome to PhotoShare Administration'
