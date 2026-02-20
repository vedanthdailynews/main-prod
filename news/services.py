"""
Service for fetching news from Google News RSS feeds.
"""
import feedparser
import requests
import re
from datetime import datetime, timedelta
from django.utils import timezone
from bs4 import BeautifulSoup
import logging

from news.models import NewsArticle, NewsSource, Continent
from news.image_service import get_contextual_image

logger = logging.getLogger(__name__)


class GoogleNewsService:
    """Service to fetch news from Google News."""
    
    # Google News RSS feed URLs by continent/region
    RSS_FEEDS = {
        Continent.GLOBAL: 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',
        Continent.ASIA: 'https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en',
        Continent.EUROPE: 'https://news.google.com/rss?hl=en-GB&gl=GB&ceid=GB:en',
        Continent.NORTH_AMERICA: 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',
        Continent.SOUTH_AMERICA: 'https://news.google.com/rss?hl=en-BR&gl=BR&ceid=BR:en',
        Continent.AFRICA: 'https://news.google.com/rss?hl=en-ZA&gl=ZA&ceid=ZA:en',
        Continent.OCEANIA: 'https://news.google.com/rss?hl=en-AU&gl=AU&ceid=AU:en',
    }
    
    # India-specific RSS feeds
    INDIA_RSS_FEEDS = {
        'national': 'https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en',
        'local': 'https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRGs0TVRZNU1CSUNhVzRvQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en',
    }
    
    # Category-specific feeds for India
    CATEGORY_FEEDS_INDIA = {
        'BUSINESS': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en',
        'TECHNOLOGY': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en',
        'ENTERTAINMENT': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en',
        'SPORTS': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en',
        'SCIENCE': 'https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en',
        'HEALTH': 'https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en',
    }
    
    # Category-specific feeds
    CATEGORY_FEEDS = {
        'WORLD': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'BUSINESS': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'TECHNOLOGY': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'ENTERTAINMENT': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'SPORTS': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'SCIENCE': '/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en',
        'HEALTH': '/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US:en',
    }
    
    @staticmethod
    def clean_html(html_text: str) -> str:
        """
        Remove HTML tags and clean text.
        
        Args:
            html_text: Text with HTML tags
            
        Returns:
            Clean text without HTML tags
        """
        if not html_text:
            return ''
        
        # Parse HTML
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def extract_image_url(entry) -> str:
        """
        Extract image URL from RSS entry.
        
        Args:
            entry: RSS feed entry
            
        Returns:
            Image URL or empty string
        """
        try:
            # Try to get image from media content
            if hasattr(entry, 'media_content') and entry.media_content:
                return entry.media_content[0].get('url', '')
            
            # Try to get image from media thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url', '')
            
            # Try to extract from summary/description HTML
            if 'summary' in entry:
                soup = BeautifulSoup(entry.summary, 'html.parser')
                img_tag = soup.find('img')
                if img_tag and img_tag.get('src'):
                    return img_tag.get('src')
            
            # Try to extract from content
            if hasattr(entry, 'content') and entry.content:
                soup = BeautifulSoup(entry.content[0].value, 'html.parser')
                img_tag = soup.find('img')
                if img_tag and img_tag.get('src'):
                    return img_tag.get('src')
        
        except Exception as e:
            logger.error(f"Error extracting image: {e}")
        
        return ''
    
    @staticmethod
    def fetch_image_from_url(article_url: str) -> str:
        """
        Fetch the main image from an article URL by scraping the page.
        
        Args:
            article_url: URL of the news article
            
        Returns:
            Image URL or empty string
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Follow redirects to get to actual article
            response = requests.get(article_url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try Open Graph image (most reliable)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image.get('content')
                # Skip Google News logos and generic images
                if not any(skip in img_url.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default']):
                    return img_url
            
            # Try Twitter card image
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                img_url = twitter_image.get('content')
                if not any(skip in img_url.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default']):
                    return img_url
            
            # Try schema.org image
            schema_img = soup.find('meta', attrs={'itemprop': 'image'})
            if schema_img and schema_img.get('content'):
                img_url = schema_img.get('content')
                if not any(skip in img_url.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default']):
                    return img_url
            
            # Try link rel image_src
            link_img = soup.find('link', rel='image_src')
            if link_img and link_img.get('href'):
                img_url = link_img.get('href')
                if not any(skip in img_url.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default']):
                    return img_url
            
            # Try to find large images in article content
            article_tag = soup.find('article')
            if article_tag:
                for img in article_tag.find_all('img'):
                    src = img.get('src', '')
                    # Check image dimensions if available
                    width = img.get('width', 0)
                    height = img.get('height', 0)
                    try:
                        if width and height:
                            if int(width) > 400 and int(height) > 200:
                                if not any(skip in src.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default', 'ads', 'banner']):
                                    if src.startswith('//'):
                                        return 'https:' + src
                                    elif src.startswith('/'):
                                        from urllib.parse import urlparse
                                        parsed = urlparse(response.url)
                                        return f"{parsed.scheme}://{parsed.netloc}{src}"
                                    elif src.startswith('http'):
                                        return src
                    except:
                        pass
            
            # Try main content area
            main_content = soup.find(['main', 'div'], class_=re.compile('content|article|story|post', re.I))
            if main_content:
                img = main_content.find('img')
                if img and img.get('src'):
                    src = img.get('src')
                    if not any(skip in src.lower() for skip in ['google', 'logo', 'icon', 'avatar', 'default', 'ads']):
                        if src.startswith('//'):
                            return 'https:' + src
                        elif src.startswith('/'):
                            from urllib.parse import urlparse
                            parsed = urlparse(response.url)
                            return f"{parsed.scheme}://{parsed.netloc}{src}"
                        elif src.startswith('http'):
                            return src
        
        except Exception as e:
            logger.debug(f"Could not fetch image from {article_url}: {e}")
        
        return ''
    
    @staticmethod
    def get_fallback_image(category: str = None, title: str = '') -> str:
        """
        Get a fallback image URL that is unique per article.
        Uses Picsum Photos with a seed derived from the article title so every
        article gets a consistent but visually distinct placeholder image.

        Args:
            category: News category (kept for API compatibility, unused now)
            title:    Article title used as the image seed

        Returns:
            Fallback image URL
        """
        import hashlib
        # Derive a short alphanumeric seed from the title so the same article
        # always gets the same image, but different articles get different ones.
        if title:
            seed = hashlib.md5(title.encode()).hexdigest()[:16]
        else:
            import random
            seed = str(random.randint(1, 9999))
        return f"https://picsum.photos/seed/{seed}/800/450"
    
    @staticmethod
    def fetch_news_for_continent(continent: str) -> int:
        """
        Fetch news for a specific continent.
        
        Args:
            continent: Continent code from Continent choices
            
        Returns:
            Number of new articles added
        """
        if continent not in GoogleNewsService.RSS_FEEDS:
            logger.error(f"Invalid continent: {continent}")
            return 0
        
        feed_url = GoogleNewsService.RSS_FEEDS[continent]
        logger.info(f"Fetching news for {continent} from {feed_url}")
        
        try:
            feed = feedparser.parse(feed_url)
            articles_added = 0
            
            for entry in feed.entries:
                try:
                    # Extract publication date
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = datetime(*entry.published_parsed[:6])
                        published_at = timezone.make_aware(published_at)
                    else:
                        published_at = timezone.now()

                    # Skip articles older than 3 days
                    if (timezone.now() - published_at).days > 3:
                        continue

                    # Clean description text
                    raw_description = entry.get('summary', '')
                    clean_description = GoogleNewsService.clean_html(raw_description)

                    # 1. Try contextual entity image (Modi, BSE, etc.)
                    image_url = get_contextual_image(entry.title, clean_description)

                    # 2. Fall back to image embedded in RSS feed
                    if not image_url:
                        image_url = GoogleNewsService.extract_image_url(entry)

                    # 3. Fall back to scraping the article page
                    if not image_url:
                        image_url = GoogleNewsService.fetch_image_from_url(entry.link)

                    # 4. Last resort: unique per-article placeholder
                    if not image_url:
                        image_url = GoogleNewsService.get_fallback_image(None, title=entry.title)

                    # Get source name
                    source_name = entry.get('source', {}).get('title', 'Google News')

                    # Mark as Indian news when fetched from India-specific feed
                    is_indian = continent == Continent.ASIA

                    # Use update_or_create to avoid UNIQUE constraint errors
                    article, created = NewsArticle.objects.update_or_create(
                        url=entry.link,
                        defaults={
                            'title': entry.title,
                            'description': clean_description,
                            'source': source_name,
                            'image_url': image_url,
                            'published_at': published_at,
                            'continent': continent,
                            'is_indian_news': is_indian,
                        }
                    )
                    
                    if created:
                        articles_added += 1
                        logger.info(f"Added article: {article.title}")
                    
                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    continue
            
            logger.info(f"Added {articles_added} new articles for {continent}")
            return articles_added
            
        except Exception as e:
            logger.error(f"Error fetching news for {continent}: {e}")
            return 0
    
    @staticmethod
    def fetch_all_news() -> dict:
        """
        Fetch news for all continents.
        
        Returns:
            Dictionary with continent as key and number of articles added as value
        """
        results = {}
        
        for continent, _ in Continent.choices:
            try:
                count = GoogleNewsService.fetch_news_for_continent(continent)
                results[continent] = count
            except Exception as e:
                logger.error(f"Error fetching news for {continent}: {e}")
                results[continent] = 0
        
        logger.info(f"Fetch complete. Results: {results}")
        return results
    
    @staticmethod
    def cleanup_old_news(days: int = 7):
        """
        Remove news articles older than specified days.
        
        Args:
            days: Number of days to keep articles
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = NewsArticle.objects.filter(published_at__lt=cutoff_date).delete()
        logger.info(f"Deleted {deleted_count} old articles")
        return deleted_count
