"""
One-time script: fix articles that have an incorrect IPL image.
Run with: python manage.py shell < fix_images.py
  OR:    python fix_images.py  (standalone)
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle
from news.image_service import get_contextual_image

# Find articles with IPL image that are NOT about IPL/cricket
wrong_img_articles = [
    a for a in NewsArticle.objects.filter(image_url__icontains='Indian_Premier')
    if not any(kw in a.title.lower() for kw in ['ipl', 'premier league', 'cricket', 't20'])
]

print(f'Articles with wrong IPL image: {len(wrong_img_articles)}')

for article in wrong_img_articles:
    new_img = get_contextual_image(article.title, '')
    article.image_url = new_img
    article.save(update_fields=['image_url'])
    status = new_img[:75] if new_img else '(cleared — will show placeholder)'
    print(f'  Fixed: {article.title[:65]}')
    print(f'         New: {status}')

print('Done.')
