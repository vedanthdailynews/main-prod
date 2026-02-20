"""
Test script to verify news fetching functionality.
Run this to test if Google News fetching works without waiting for Celery.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.services import GoogleNewsService
from news.models import NewsArticle, Continent

def test_news_fetch():
    """Test news fetching from Google News."""
    print("=" * 60)
    print("Vedant Daily News - Testing News Fetch")
    print("=" * 60)
    print()
    
    print("Testing Google News RSS feed fetching...")
    print()
    
    # Test fetching for one continent
    print("Fetching news for Asia...")
    try:
        count = GoogleNewsService.fetch_news_for_continent(Continent.ASIA)
        print(f"✓ Successfully fetched {count} new articles for Asia")
    except Exception as e:
        print(f"✗ Error fetching Asia news: {e}")
    
    print()
    print("-" * 60)
    print()
    
    # Check database
    total_articles = NewsArticle.objects.count()
    print(f"Total articles in database: {total_articles}")
    
    if total_articles > 0:
        print("\nLatest 5 articles:")
        for article in NewsArticle.objects.all()[:5]:
            print(f"  - {article.title[:60]}...")
            print(f"    Source: {article.source} | Continent: {article.get_continent_display()}")
            print()
    
    print("=" * 60)
    print("Test complete!")
    print()
    print("To fetch all continents, run:")
    print("  python manage.py shell")
    print("  >>> from news.services import GoogleNewsService")
    print("  >>> GoogleNewsService.fetch_all_news()")
    print("=" * 60)

if __name__ == '__main__':
    test_news_fetch()
