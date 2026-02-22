"""
Celery configuration for vedant_news project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')

app = Celery('vedant_news')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    # India-first: fetch from The Hindu, TOI, NDTV etc. every 2 minutes
    'fetch-india-news-every-2-minutes': {
        'task': 'news.tasks.fetch_india_news',
        'schedule': 120.0,
    },
    # Full global fetch every 5 minutes (includes India + international)
    'fetch-all-news-every-5-minutes': {
        'task': 'news.tasks.fetch_all_news',
        'schedule': 300.0,
    },
    # Translate non-English articles every 60 seconds (max 300 articles per run)
    # Uses 20 parallel threads — almost-real-time translation
    'translate-articles-every-minute': {
        'task': 'news.tasks.translate_pending_articles',
        'schedule': 60.0,
        'kwargs': {'limit': 300},
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
