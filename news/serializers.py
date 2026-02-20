"""
REST API serializers for news app.
"""
from rest_framework import serializers
from news.models import NewsArticle, NewsSource


class NewsArticleSerializer(serializers.ModelSerializer):
    """Serializer for NewsArticle model."""
    
    continent_display = serializers.CharField(source='get_continent_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = NewsArticle
        fields = [
            'id', 'title', 'description', 'content', 'url', 'source',
            'author', 'image_url', 'continent', 'continent_display',
            'category', 'category_display', 'summary', 'sentiment', 'tags',
            'published_at', 'created_at', 'is_featured', 'view_count'
        ]
        read_only_fields = ['id', 'created_at', 'view_count']


class NewsArticleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing news articles."""
    
    continent_display = serializers.CharField(source='get_continent_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = NewsArticle
        fields = [
            'id', 'title', 'description', 'url', 'source', 'image_url',
            'continent', 'continent_display', 'category', 'category_display',
            'sentiment', 'published_at', 'is_featured', 'view_count'
        ]


class NewsSourceSerializer(serializers.ModelSerializer):
    """Serializer for NewsSource model."""
    
    continent_display = serializers.CharField(source='get_continent_display', read_only=True)
    
    class Meta:
        model = NewsSource
        fields = [
            'id', 'name', 'url', 'continent', 'continent_display',
            'is_active', 'last_fetched', 'fetch_count', 'error_count'
        ]
        read_only_fields = ['last_fetched', 'fetch_count', 'error_count']
