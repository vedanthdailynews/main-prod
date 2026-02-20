"""
Celery tasks for news fetching and processing.
"""
from celery import shared_task
from django.conf import settings
import logging

from news.services import GoogleNewsService
from news.ai_service import AIService

logger = logging.getLogger(__name__)


@shared_task(name='news.tasks.fetch_all_news')
def fetch_all_news():
    """
    Celery task to fetch news from all continents.
    This task runs every 2 minutes as configured in celeryapp.py
    """
    logger.info("Starting news fetch task...")
    
    try:
        results = GoogleNewsService.fetch_all_news()
        total_articles = sum(results.values())
        
        logger.info(f"News fetch complete. Total new articles: {total_articles}")
        return {
            'success': True,
            'results': results,
            'total_articles': total_articles
        }
    except Exception as e:
        logger.error(f"Error in fetch_all_news task: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='news.tasks.process_article_with_ai')
def process_article_with_ai(article_id: int):
    """
    Process a single article with AI to generate summary, sentiment, and tags.
    
    Args:
        article_id: ID of the NewsArticle to process
    """
    from news.models import NewsArticle
    
    try:
        article = NewsArticle.objects.get(id=article_id)
        
        # Generate AI content
        ai_service = AIService()
        ai_data = ai_service.process_article(article)
        
        # Update article with AI-generated content
        article.summary = ai_data.get('summary')
        article.sentiment = ai_data.get('sentiment')
        article.tags = ai_data.get('tags', [])
        article.save(update_fields=['summary', 'sentiment', 'tags'])
        
        logger.info(f"AI processing complete for article: {article.title}")
        return {'success': True, 'article_id': article_id}
        
    except NewsArticle.DoesNotExist:
        logger.error(f"Article {article_id} not found")
        return {'success': False, 'error': 'Article not found'}
    except Exception as e:
        logger.error(f"Error processing article {article_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='news.tasks.cleanup_old_news')
def cleanup_old_news():
    """
    Remove news articles older than MAX_NEWS_AGE_DAYS.
    """
    try:
        days = settings.MAX_NEWS_AGE_DAYS
        deleted_count = GoogleNewsService.cleanup_old_news(days)
        
        logger.info(f"Cleanup complete. Deleted {deleted_count} articles")
        return {
            'success': True,
            'deleted_count': deleted_count
        }
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='news.tasks.batch_process_articles')
def batch_process_articles(limit: int = 10):
    """
    Process multiple unprocessed articles with AI in batch.
    
    Args:
        limit: Maximum number of articles to process
    """
    from news.models import NewsArticle
    
    try:
        # Get articles without AI-generated content
        articles = NewsArticle.objects.filter(
            summary__isnull=True
        )[:limit]
        
        processed = 0
        for article in articles:
            process_article_with_ai.delay(article.id)
            processed += 1
        
        logger.info(f"Queued {processed} articles for AI processing")
        return {
            'success': True,
            'queued': processed
        }
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        return {
            'success': False,
            'error': str(e)
        }
