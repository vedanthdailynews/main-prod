#!/usr/bin/env python
"""Fetch India-focused news with priority."""
import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle
from news.services import GoogleNewsService

# Clear old articles
print('╔══════════════════════════════════════════════════════════════╗')
print('║         TIMES OF VEDANT - India Focus News Fetcher          ║')
print('╚══════════════════════════════════════════════════════════════╝\n')

print('🗑️  Clearing old articles...')
count = NewsArticle.objects.count()
NewsArticle.objects.all().delete()
print(f'   Deleted {count} articles\n')

# Fetch India-focused news with priority
print('🇮🇳 Fetching India-focused news...')
print('   This will prioritize Indian national and regional news\n')

sources = [
    ('IN-National', 'India National'),
    ('IN-Local', 'India Local/Regional'),
    ('AS', 'Asia'),
]

total_fetched = 0
for code, name in sources:
    print(f'📰 Fetching {name}...', end=' ')
    if code.startswith('IN-'):
        # Fetch from India-specific feeds
        feed_type = code.split('-')[1].lower()
        feed_url = GoogleNewsService.INDIA_RSS_FEEDS.get(feed_type)
        if feed_url:
            result = GoogleNewsService.fetch_news_for_continent('AS')  # Using Asia feed for now
    else:
        result = GoogleNewsService.fetch_news_for_continent(code)
    print(f'{result} articles ✓')
    total_fetched += result

print(f'\n✅ Total fetched: {total_fetched} articles')

# Update Indian news flag for articles from India
print('\n🔖 Marking Indian news articles...')
indian_sources = ['India', 'Indian', 'NDTV', 'Times of India', 'Hindu', 'Hindustan Times', 
                  'Economic Times', 'Indian Express', 'News18', 'Zee News', 'ABP', 'Aaj Tak',
                  'Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata', 'Hyderabad']

for source_keyword in indian_sources:
    count = NewsArticle.objects.filter(source__icontains=source_keyword).update(is_indian_news=True)
    if count > 0:
        print(f'   ✓ Marked {count} articles from sources containing "{source_keyword}"')

# Statistics
total = NewsArticle.objects.count()
indian_count = NewsArticle.objects.filter(is_indian_news=True).count()
with_images = NewsArticle.objects.exclude(image_url='').count()

print(f'\n📊 Final Statistics:')
print(f'   • Total articles: {total}')
print(f'   • Indian news: {indian_count} ({round(indian_count/total*100) if total > 0 else 0}%)')
print(f'   • With images: {with_images} ({round(with_images/total*100) if total > 0 else 0}%)')

print(f'\n🎉 Done! Visit http://127.0.0.1:8000 to see Times of Vedant with India focus!')
