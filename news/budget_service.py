"""
Budget news service for fetching Budget 2026 related news from Google News.
"""
import feedparser
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class BudgetNewsService:
    """Service to fetch Budget 2026 related news from Google News."""
    
    # Budget-related RSS feeds
    BUDGET_RSS_FEEDS = {
        'budget_general': 'https://news.google.com/rss/search?q=Budget+2026+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_income_tax': 'https://news.google.com/rss/search?q=Budget+2026+Income+Tax&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_economy': 'https://news.google.com/rss/search?q=Budget+2026+Economy+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_infrastructure': 'https://news.google.com/rss/search?q=Budget+2026+Infrastructure+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_reforms': 'https://news.google.com/rss/search?q=Budget+2026+Reforms+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_expectations': 'https://news.google.com/rss/search?q=Budget+2026+Expectations+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_market': 'https://news.google.com/rss/search?q=Budget+2026+Stock+Market+India&hl=en-IN&gl=IN&ceid=IN:en',
        'budget_sectors': 'https://news.google.com/rss/search?q=Budget+2026+Sectoral+India&hl=en-IN&gl=IN&ceid=IN:en',
    }
    
    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ''
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text().strip()
    
    @staticmethod
    def get_fallback_image(category: str = 'budget') -> str:
        """Get placeholder image for budget news."""
        # Use Lorem Picsum with budget-related seed
        seed = hash(category) % 1000
        return f'https://picsum.photos/seed/{seed}/800/450'
    
    @staticmethod
    def fetch_budget_news(feed_type: str = 'budget_general') -> List[Dict]:
        """
        Fetch budget news from specified RSS feed.
        
        Args:
            feed_type: Type of budget feed to fetch
            
        Returns:
            List of news article dictionaries
        """
        from news.models import NewsArticle
        
        feed_url = BudgetNewsService.BUDGET_RSS_FEEDS.get(feed_type)
        if not feed_url:
            logger.error(f"Invalid feed type: {feed_type}")
            return []
        
        try:
            logger.info(f"Fetching budget news from {feed_type}")
            feed = feedparser.parse(feed_url)
            
            articles_data = []
            for entry in feed.entries[:15]:  # Limit to 15 articles per feed
                try:
                    # Clean description
                    description = BudgetNewsService.clean_html(
                        entry.get('summary', entry.get('description', ''))
                    )
                    
                    # Import here to avoid circular import
                    from news.models import NewsSource
                    
                    # Get or create source
                    source, _ = NewsSource.objects.get_or_create(
                        name=entry.get('source', {}).get('title', 'Google News'),
                        defaults={'url': 'https://news.google.com', 'is_active': True}
                    )
                    
                    # Get or create article
                    article_data = {
                        'title': entry.get('title', 'Untitled'),
                        'url': entry.get('link', ''),
                        'description': description[:500] if description else '',
                        'published_at': datetime.now(),
                        'source': source,
                        'continent': 'AS',  # India news
                        'category': 'BUDGET',
                        'is_indian_news': True,
                        'image_url': BudgetNewsService.get_fallback_image(feed_type),
                    }
                    
                    # Check if article already exists
                    existing = NewsArticle.objects.filter(url=article_data['url']).first()
                    if not existing:
                        articles_data.append(article_data)
                    
                except Exception as e:
                    logger.error(f"Error processing budget article: {e}")
                    continue
            
            logger.info(f"Fetched {len(articles_data)} new budget articles from {feed_type}")
            return articles_data
            
        except Exception as e:
            logger.error(f"Error fetching budget news: {e}")
            return []
    
    @staticmethod
    def fetch_all_budget_news() -> int:
        """
        Fetch news from all budget feeds and save to database.
        
        Returns:
            Total number of articles created
        """
        from news.models import NewsArticle
        
        total_created = 0
        
        for feed_type in BudgetNewsService.BUDGET_RSS_FEEDS.keys():
            articles_data = BudgetNewsService.fetch_budget_news(feed_type)
            
            for article_data in articles_data:
                try:
                    article, created = NewsArticle.objects.get_or_create(
                        url=article_data['url'],
                        defaults=article_data
                    )
                    if created:
                        total_created += 1
                        logger.info(f"Created budget article: {article.title}")
                except Exception as e:
                    logger.error(f"Error saving budget article: {e}")
                    continue
        
        logger.info(f"Total budget articles created: {total_created}")
        return total_created
