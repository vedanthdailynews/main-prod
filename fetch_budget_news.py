"""
Script to fetch Budget 2026 news from Google News RSS feeds.
"""
import os
import sys
import django

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.budget_service import BudgetNewsService
from news.models import NewsArticle

def main():
    """Fetch and display Budget 2026 news statistics."""
    print("=" * 60)
    print("FETCHING BUDGET 2026 NEWS".center(60))
    print("=" * 60)
    print()
    
    # Fetch budget news
    print("📰 Fetching news from Google News RSS feeds...")
    print()
    
    total_created = BudgetNewsService.fetch_all_budget_news()
    
    print()
    print("=" * 60)
    print("BUDGET NEWS STATISTICS".center(60))
    print("=" * 60)
    print()
    
    # Get statistics
    total_budget_articles = NewsArticle.objects.filter(category='BUDGET').count()
    articles_with_images = NewsArticle.objects.filter(
        category='BUDGET'
    ).exclude(image_url='').count()
    
    print(f"✅ New articles fetched: {total_created}")
    print(f"📊 Total Budget 2026 articles: {total_budget_articles}")
    print(f"🖼️  Articles with images: {articles_with_images} ({round(articles_with_images/total_budget_articles*100) if total_budget_articles > 0 else 0}%)")
    print()
    
    # Show recent articles
    print("📰 Latest Budget 2026 Articles:")
    print("-" * 60)
    
    recent_articles = NewsArticle.objects.filter(
        category='BUDGET'
    ).order_by('-published_at')[:5]
    
    for i, article in enumerate(recent_articles, 1):
        print(f"\n{i}. {article.title}")
        print(f"   Source: {article.source.name if article.source else 'Unknown'}")
        print(f"   Published: {article.published_at.strftime('%d %b %Y, %I:%M %p')}")
        if article.description:
            print(f"   Preview: {article.description[:100]}...")
    
    print()
    print("=" * 60)
    print("✅ Budget news fetch completed successfully!".center(60))
    print(f"🌐 View at: http://127.0.0.1:8000/budget/".center(60))
    print("=" * 60)

if __name__ == '__main__':
    main()
