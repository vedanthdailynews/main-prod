"""
Django admin configuration for news app.
"""
from django.contrib import admin
from .models import NewsArticle, NewsSource, DailyPaper


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    """Admin interface for NewsArticle model."""
    
    list_display = ['title', 'source', 'continent', 'category', 'published_at', 'view_count', 'is_featured']
    list_filter = ['continent', 'category', 'is_featured', 'published_at', 'source']
    search_fields = ['title', 'description', 'source']
    readonly_fields = ['created_at', 'updated_at', 'view_count']
    list_per_page = 50
    date_hierarchy = 'published_at'
    
    fieldsets = (
        ('Article Information', {
            'fields': ('title', 'description', 'content', 'url', 'source', 'author', 'image_url')
        }),
        ('Categorization', {
            'fields': ('continent', 'category', 'is_featured')
        }),
        ('AI-Generated Content', {
            'fields': ('summary', 'sentiment', 'tags'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('published_at', 'view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    """Admin interface for NewsSource model."""
    
    list_display = ['name', 'continent', 'is_active', 'fetch_count', 'error_count', 'last_fetched']
    list_filter = ['continent', 'is_active']
    search_fields = ['name', 'url']
    readonly_fields = ['last_fetched', 'fetch_count', 'error_count', 'created_at', 'updated_at']


@admin.register(DailyPaper)
class DailyPaperAdmin(admin.ModelAdmin):
    """Admin interface for Daily Paper uploads."""
    
    list_display = ['date', 'edition', 'total_pages', 'file_size', 'is_published', 'uploaded_at']
    list_filter = ['is_published', 'edition', 'date']
    search_fields = ['edition']
    readonly_fields = ['file_size', 'uploaded_at', 'updated_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Paper Information', {
            'fields': ('date', 'edition', 'total_pages', 'is_published')
        }),
        ('PDF File', {
            'fields': ('pdf_file', 'file_size')
        }),
        ('Metadata', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
