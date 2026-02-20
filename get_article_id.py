import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle

article = NewsArticle.objects.first()
if article:
    print(f'Article ID: {article.pk}')
    print(f'Title: {article.title}')
else:
    print('No articles found')
