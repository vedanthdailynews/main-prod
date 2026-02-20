#!/usr/bin/env python
"""Refetch news articles with real images."""
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
print('Deleting old articles...')
NewsArticle.objects.all().delete()
print('Deleted all articles')

# Fetch with improved image extraction
print('\nFetching news with real article images (this may take a few moments)...')
print('This fetches from actual article pages to get quality images.\n')

continents = [
    ('AS', 'Asia'),
    ('GL', 'Global'),
    ('EU', 'Europe'),
]

total_fetched = 0
for code, name in continents:
    print(f'Fetching {name}...', end=' ')
    result = GoogleNewsService.fetch_news_for_continent(code)
    print(f'{result} articles')
    total_fetched += result

print(f'\n✓ Total fetched: {total_fetched} articles')

# Check image stats
total = NewsArticle.objects.count()
with_images = NewsArticle.objects.exclude(image_url='').count()
without_images = total - with_images

print(f'\nImage Statistics:')
print(f'  - Total articles: {total}')
print(f'  - With images: {with_images} ({round(with_images/total*100) if total > 0 else 0}%)')
print(f'  - Without images: {without_images}')
print('\nDone! Refresh your browser to see articles with real images.')
