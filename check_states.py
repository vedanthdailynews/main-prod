import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle
from django.db.models import Count

# Check states
states = NewsArticle.objects.values('indian_state').annotate(count=Count('id')).order_by('-count')
print(f'\nTotal unique states: {states.count()}\n')
print('All states with news:')
for s in states:
    print(f'{s["indian_state"]}: {s["count"]} articles')
