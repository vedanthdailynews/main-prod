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
    
    # ── Keyword maps for auto-classification ──────────────────────────────
    # Keys are lowercase substrings; first match wins (most-specific first).
    _CATEGORY_KEYWORDS = [
        # ── BUDGET (must come before BUSINESS) ──────────────────────────
        ('BUDGET', [
            'union budget', 'budget 2026', 'budget session', 'budget speech',
            'finance minister budget', 'tax slab', 'income tax slab',
            'customs duty', 'railway budget', 'fiscal deficit target',
            'budget allocation', 'budget estimate', 'interim budget',
        ]),
        # ── SPORTS ───────────────────────────────────────────────────────
        ('SPORTS', [
            'cricket', 'ipl', 'bcci', 'test match', 'odi', 't20',
            'world cup cricket', 'football', 'fifa', 'premier league',
            'la liga', 'bundesliga', 'champions league', 'euro 2024',
            'tennis', 'wimbledon', 'us open tennis', 'french open',
            'australian open', 'badminton', 'pbl', 'golf', 'formula 1',
            'f1 race', 'olympics', 'paralympics', 'commonwealth games',
            'asian games', 'nba', 'nfl', 'hockey', 'kabaddi', 'pro kabaddi',
            'wrestling', 'boxing', 'mma', 'ufc', 'athletics', 'marathon',
            'chess', 'squash', 'archery', 'shooting sport', 'weightlifting',
            'swimmer', 'swimming', 'cyclist', 'cycling sport',
            'virat kohli', 'rohit sharma', 'ms dhoni', 'sachin tendulkar',
            'smriti mandhana', 'neeraj chopra', 'pv sindhu', 'saina nehwal',
            'lionel messi', 'cristiano ronaldo', 'rafael nadal', 'novak djokovic',
            'serena williams', 'lebron james', 'real madrid', 'barcelona fc',
            'manchester united', 'liverpool fc', 'chelsea fc', 'arsenal fc',
            'scored', 'century', 'hat trick', 'wicket', 'innings',
            'tournament', 'championship', 'league table', 'standings',
            'transfer window', 'transfer fee', 'match result', 'final score',
        ]),
        # ── HEALTH ───────────────────────────────────────────────────────
        ('HEALTH', [
            'covid', 'coronavirus', 'omicron', 'vaccine', 'vaccination',
            'booster dose', 'herd immunity', 'pandemic', 'epidemic',
            'outbreak', 'mpox', 'monkeypox', 'dengue', 'malaria', 'typhoid',
            'tuberculosis', 'hiv', 'aids', 'cancer treatment', 'tumor',
            'chemotherapy', 'radiation therapy', 'surgery', 'hospital',
            'icu', 'ventilator', 'doctor', 'physician', 'nurse', 'aiims',
            'health ministry', 'who health', 'cdc', 'drug approval', 'fda',
            'clinical trial', 'medicine', 'antibiotic', 'pharmaceutical',
            'mental health', 'depression', 'anxiety disorder', 'schizophrenia',
            'diabetes', 'insulin', 'blood pressure', 'hypertension',
            'heart disease', 'cardiac arrest', 'stroke', 'kidney disease',
            'nutrition', 'obesity', 'diet plan', 'fitness', 'wellness',
            'yoga health', 'ayurveda', 'homeopathy', 'physiotherapy',
        ]),
        # ── TECHNOLOGY ───────────────────────────────────────────────────
        ('TECHNOLOGY', [
            'artificial intelligence', 'machine learning', 'deep learning',
            'chatgpt', 'openai', 'gemini ai', 'claude ai', 'llm',
            'generative ai', 'neural network', 'large language model',
            'smartphone', 'iphone', 'android phone', 'pixel phone',
            'samsung galaxy', 'oneplus', 'realme', 'vivo phone', 'oppo',
            'microchip', 'semiconductor', 'processor', 'gpu', 'nvidia chip',
            'intel chip', 'amd chip', 'quantum computing', 'supercomputer',
            'cybersecurity', 'data breach', 'ransomware', 'malware', 'hacker',
            'cloud computing', 'aws', 'azure cloud', 'google cloud',
            'software update', 'app launch', 'app store', 'google play',
            'social media', 'twitter', 'facebook', 'instagram', 'youtube',
            'tiktok', 'linkedin', 'whatsapp update', 'telegram update',
            'electric vehicle', 'ev battery', 'autonomous vehicle',
            'drone', 'robotics', 'automation tech', '5g network', '6g',
            'internet of things', 'iot', 'blockchain', 'cryptocurrency',
            'bitcoin', 'ethereum', 'nft', 'web3', 'metaverse',
            'startup funding', 'unicorn startup', 'tech ipo', 'series a',
            'silicon valley', 'silicon', 'tech layoff', 'microsoft layoff',
            'google layoff', 'meta layoff', 'amazon layoff',
        ]),
        # ── SCIENCE ──────────────────────────────────────────────────────
        ('SCIENCE', [
            'isro', 'chandrayaan', 'gaganyaan', 'aditya-l1', 'mangalyaan',
            'nasa', 'spacex', 'space launch', 'rocket launch', 'satellite',
            'black hole', 'james webb telescope', 'hubble', 'exoplanet',
            'solar storm', 'solar flare', 'aurora borealis', 'eclipse',
            'climate change', 'global warming', 'carbon emission',
            'renewable energy', 'solar energy', 'wind energy', 'nuclear energy',
            'research paper', 'scientific study', 'peer review',
            'archaeology', 'fossil', 'dinosaur', 'ancient civilization',
            'dna research', 'genome', 'crispr', 'stem cell',
            'particle physics', 'cern', 'higgs boson', 'quantum', 'physics',
            'chemistry discovery', 'periodic table', 'biology research',
            'biodiversity', 'endangered species', 'wildlife conservation',
            'earthquake research', 'volcano', 'geology',
        ]),
        # ── ENTERTAINMENT ────────────────────────────────────────────────
        ('ENTERTAINMENT', [
            'bollywood', 'hollywood', 'tollywood', 'kollywood', 'mollywood',
            'box office', 'film release', 'movie review', 'ott release',
            'netflix', 'amazon prime video', 'disney+ hotstar', 'jiocinema',
            'sony liv', 'zee5', 'web series', 'tv show', 'reality show',
            'bigg boss', 'kbc', 'dance india dance',
            'oscar', 'grammy', 'bafta', 'cannes', 'filmfare', 'iifa',
            'national film award', 'golden globe',
            'actor', 'actress', 'director film', 'producer film',
            'celebrity', 'star kid', 'music album', 'song release',
            'music video', 'concert tour', 'live performance',
            'shahrukh khan', 'salman khan', 'aamir khan', 'amitabh bachchan',
            'deepika padukone', 'priyanka chopra', 'alia bhatt', 'ranveer singh',
            'taylor swift', 'beyonce', 'drake', 'ed sheeran', 'coldplay',
            'fashion week', 'met gala', 'red carpet',
            'book release', 'literature award', 'booker prize',
        ]),
        # ── BUSINESS ─────────────────────────────────────────────────────
        ('BUSINESS', [
            'sensex', 'nifty', 'bse', 'nse', 'stock market',
            'share price', 'ipo listing', 'market cap', 'bull run',
            'bear market', 'rbi rate', 'repo rate', 'monetary policy',
            'gdp growth', 'inflation rate', 'cpi', 'wpi',
            'trade deficit', 'current account', 'forex reserve',
            'rupee dollar', 'currency exchange', 'fdi', 'fii',
            'merger acquisition', 'takeover', 'demerger',
            'quarterly result', 'earnings report', 'revenue profit',
            'net profit', 'ebitda', 'annual report',
            'startup valuation', 'venture capital', 'private equity',
            'gst collection', 'direct tax', 'customs', 'excise duty',
            'sebi', 'nclt', 'insolvency', 'bankruptcy',
            'reliance earnings', 'tcs result', 'infosys result',
            'real estate', 'housing market', 'property prices',
            'oil price', 'crude oil', 'fuel price', 'petrol diesel',
            'gold price', 'silver price', 'commodity market',
            'agriculture market', 'msp', 'wholesale price',
            'export import', 'trade war', 'tariff', 'wto',
        ]),
        # ── WORLD (last, as it matches broad geopolitical terms) ─────────
        ('WORLD', [
            'war', 'conflict zone', 'ceasefire', 'peace deal',
            'diplomatic crisis', 'sanctions', 'geopolitics',
            'united nations', 'security council', 'nato', 'eu summit',
            'g20 summit', 'g7 summit', 'brics summit', 'sco',
            'president election', 'prime minister', 'general election',
            'coup', 'revolution', 'protest rally', 'civil unrest',
            'refugee', 'migration crisis', 'border dispute',
            'nuclear weapon', 'missile strike', 'airstrike',
            'ukraine russia', 'russia ukraine', 'israel gaza',
            'hamas', 'hezbollah', 'isis', 'taliban', 'al-qaeda',
            'climate summit', 'cop30', 'paris agreement',
            'world bank', 'imf', 'who', 'wto negotiation',
        ]),
    ]

    @staticmethod
    def classify_category(title: str, description: str = '') -> str:
        """
        Auto-detect the best category for an article using keyword matching.
        Returns a Category string value (e.g. 'SPORTS') or '' if no match.
        """
        text = (title + ' ' + description).lower()
        for category, keywords in GoogleNewsService._CATEGORY_KEYWORDS:
            for kw in keywords:
                if kw in text:
                    return category
        return ''

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

                    # 1. Wikipedia entity map + search (person/product/org in title)
                    image_url = get_contextual_image(entry.title, clean_description)

                    # 2. Fall back to image embedded in RSS feed
                    if not image_url:
                        image_url = GoogleNewsService.extract_image_url(entry)

                    # 3. Fall back to scraping the article page
                    if not image_url:
                        image_url = GoogleNewsService.fetch_image_from_url(entry.link)

                    # 4. Last resort: unique per-article Picsum placeholder
                    if not image_url:
                        image_url = GoogleNewsService.get_fallback_image(None, title=entry.title)

                    # Get source name
                    source_name = entry.get('source', {}).get('title', 'Google News')

                    # Mark as Indian news when fetched from India-specific feed
                    is_indian = continent == Continent.ASIA

                    # Auto-classify category from title + description keywords
                    category = GoogleNewsService.classify_category(
                        entry.title, clean_description
                    )

                    # Use update_or_create to avoid UNIQUE constraint errors
                    defaults = {
                        'title': entry.title,
                        'description': clean_description,
                        'source': source_name,
                        'image_url': image_url,
                        'published_at': published_at,
                        'continent': continent,
                        'is_indian_news': is_indian,
                    }
                    if category:
                        defaults['category'] = category

                    article, created = NewsArticle.objects.update_or_create(
                        url=entry.link,
                        defaults=defaults,
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
    def fetch_news_for_category(category: str) -> int:
        """
        Fetch news from a category-specific Google News feed and tag articles directly.
        Returns number of new articles added.
        """
        base = 'https://news.google.com/rss'
        # Prefer India feeds when available, fall back to global
        feed_path = GoogleNewsService.CATEGORY_FEEDS_INDIA.get(
            category,
            GoogleNewsService.CATEGORY_FEEDS.get(category, '')
        )
        if not feed_path:
            return 0

        feed_url = feed_path if feed_path.startswith('http') else base + feed_path
        logger.info(f"Fetching category feed: {category} → {feed_url}")

        try:
            feed = feedparser.parse(feed_url)
            articles_added = 0

            for entry in feed.entries:
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = timezone.make_aware(
                            datetime(*entry.published_parsed[:6])
                        )
                    else:
                        published_at = timezone.now()

                    if (timezone.now() - published_at).days > 3:
                        continue

                    raw_description = entry.get('summary', '')
                    clean_description = GoogleNewsService.clean_html(raw_description)

                    image_url = get_contextual_image(entry.title, clean_description)
                    if not image_url:
                        image_url = GoogleNewsService.extract_image_url(entry)
                    if not image_url:
                        image_url = GoogleNewsService.fetch_image_from_url(entry.link)
                    if not image_url:
                        image_url = GoogleNewsService.get_fallback_image(None, title=entry.title)

                    source_name = entry.get('source', {}).get('title', 'Google News')

                    article, created = NewsArticle.objects.update_or_create(
                        url=entry.link,
                        defaults={
                            'title': entry.title,
                            'description': clean_description,
                            'source': source_name,
                            'image_url': image_url,
                            'published_at': published_at,
                            'continent': Continent.ASIA,
                            'is_indian_news': True,
                            'category': category,  # always set from feed
                        }
                    )
                    if created:
                        articles_added += 1
                except Exception as e:
                    logger.error(f"Error processing category entry ({category}): {e}")
                    continue

            logger.info(f"Category {category}: {articles_added} new articles")
            return articles_added
        except Exception as e:
            logger.error(f"Error fetching category feed {category}: {e}")
            return 0

    @staticmethod
    def fetch_all_news() -> dict:
        """
        Fetch news for all continents AND all category-specific feeds.
        Returns dictionary with keys for continents and categories.
        """
        results = {}

        # 1. Continent-level feeds (sets category via keyword classifier)
        for continent, _ in Continent.choices:
            try:
                count = GoogleNewsService.fetch_news_for_continent(continent)
                results[continent] = count
            except Exception as e:
                logger.error(f"Error fetching news for {continent}: {e}")
                results[continent] = 0

        # 2. Category-specific feeds (sets category from feed directly)
        from news.models import Category
        for cat_value, _ in Category.choices:
            if cat_value == 'WORLD':
                continue  # covered by continent feeds
            try:
                count = GoogleNewsService.fetch_news_for_category(cat_value)
                results[f'cat:{cat_value}'] = count
            except Exception as e:
                logger.error(f"Error fetching category feed {cat_value}: {e}")
                results[f'cat:{cat_value}'] = 0

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
