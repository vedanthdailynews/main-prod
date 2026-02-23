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
    def resolve_google_news_url(google_url: str) -> str:
        """
        Resolve a Google News redirect URL to the real article URL.
        Returns the real URL, or the original if resolution fails.
        """
        if not google_url or 'news.google.com' not in google_url:
            return google_url
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9',
            }
            resp = requests.get(google_url, headers=headers, timeout=8,
                                allow_redirects=True)
            final = resp.url
            if 'news.google.com' not in final and final.startswith('http'):
                return final
        except Exception:
            pass
        return google_url

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

                    # Resolve Google News redirect → real article URL
                    real_url = GoogleNewsService.resolve_google_news_url(entry.link)

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
                        url=real_url,
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

                    # Resolve Google News redirect → real article URL
                    real_url = GoogleNewsService.resolve_google_news_url(entry.link)

                    article, created = NewsArticle.objects.update_or_create(
                        url=real_url,
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
        India feeds are run FIRST so Indian articles always appear freshest.
        Returns dictionary with keys for continents and categories.
        """
        results = {}

        # ── 0. India-first: fetch directly from Indian publisher RSS feeds ──
        try:
            india_results = IndiaNewsService.fetch_all()
            results.update(india_results)
        except Exception as e:
            logger.error(f"IndiaNewsService.fetch_all() failed: {e}")

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
        """Remove news articles older than specified days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = NewsArticle.objects.filter(published_at__lt=cutoff_date).delete()
        logger.info(f"Deleted {deleted_count} old articles")
        return deleted_count
    
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


# ─────────────────────────────────────────────────────────────────────────────
# India-First News Service
# Fetches directly from major Indian publishers via their own RSS feeds.
# These are REAL article URLs (not Google News redirects) so trafilatura
# can extract full article content when a user opens the detail page.
# ─────────────────────────────────────────────────────────────────────────────
class IndiaNewsService:
    """Fetch news directly from Indian news publisher RSS feeds."""

    # ── National / general India feeds ───────────────────────────────────────
    # Browser-like User-Agent to prevent 403 from publisher sites
    _HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    NATIONAL_FEEDS = [
        # (source_name, feed_url, default_category)
        # The Hindu – verified working
        ('The Hindu',        'https://www.thehindu.com/news/national/feeder/default.rss',         'WORLD'),
        ('The Hindu',        'https://www.thehindu.com/news/feeder/default.rss',                  'WORLD'),
        # Times of India – India top stories
        ('Times of India',   'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms',      'WORLD'),
        # NDTV – no feedburner (shut 2023), use direct feeds
        ('NDTV',             'https://www.ndtv.com/india/rss',                                    'WORLD'),
        ('NDTV',             'https://www.ndtv.com/rss/feeds',                                   'WORLD'),
        # Indian Express
        ('Indian Express',   'https://indianexpress.com/section/india/feed/',                     'WORLD'),
        ('Indian Express',   'https://indianexpress.com/feed/',                                   'WORLD'),
        # Hindustan Times
        ('Hindustan Times',  'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',   'WORLD'),
        # India Today
        ('India Today',      'https://www.indiatoday.in/rss/home',                               'WORLD'),
        # The Wire
        ('The Wire',         'https://thewire.in/feed',                                          'WORLD'),
        # Scroll.in
        ('Scroll.in',        'https://scroll.in/feed',                                           'WORLD'),
        # Mint
        ('Mint',             'https://www.livemint.com/rss/news',                                'WORLD'),
        # Republic World
        ('Republic World',   'https://www.republicworld.com/rss',                                'WORLD'),
    ]

    # ── Category-specific feeds from Indian publishers ────────────────────────
    CATEGORY_FEEDS = [
        # Business / Economy
        ('Economic Times',    'https://economictimes.indiatimes.com/rssfeedstopstories.cms',         'BUSINESS'),
        ('Business Standard', 'https://www.business-standard.com/rss/latest.rss',                   'BUSINESS'),
        ('The Hindu',         'https://www.thehindu.com/business/feeder/default.rss',               'BUSINESS'),
        ('Times of India',    'https://timesofindia.indiatimes.com/rssfeeds/1898055.cms',            'BUSINESS'),
        ('Financial Express', 'https://www.financialexpress.com/feed/',                             'BUSINESS'),
        ('Mint',              'https://www.livemint.com/rss/markets',                               'BUSINESS'),
        # Technology
        ('The Hindu',         'https://www.thehindu.com/sci-tech/technology/feeder/default.rss',    'TECHNOLOGY'),
        ('Times of India',    'https://timesofindia.indiatimes.com/rssfeeds/-2128814593.cms',        'TECHNOLOGY'),
        ('Indian Express',    'https://indianexpress.com/section/technology/feed/',                  'TECHNOLOGY'),
        # Sports
        ('The Hindu',         'https://www.thehindu.com/sport/feeder/default.rss',                  'SPORTS'),
        ('Times of India',    'https://timesofindia.indiatimes.com/rssfeeds/4719161.cms',            'SPORTS'),
        ('Indian Express',    'https://indianexpress.com/section/sports/feed/',                      'SPORTS'),
        # Entertainment / Bollywood
        ('Times of India',    'https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms',         'ENTERTAINMENT'),
        ('Indian Express',    'https://indianexpress.com/section/entertainment/feed/',               'ENTERTAINMENT'),
        # Science / Health
        ('The Hindu',         'https://www.thehindu.com/sci-tech/science/feeder/default.rss',       'SCIENCE'),
        ('The Hindu',         'https://www.thehindu.com/sci-tech/health/feeder/default.rss',        'HEALTH'),
        ('Indian Express',    'https://indianexpress.com/section/health/feed/',                      'HEALTH'),
    ]

    # ── State / regional feeds ────────────────────────────────────────────────
    # Keys are IndianState codes (e.g. 'TN', 'KA')
    STATE_FEEDS = {
        'TN': [  # Tamil Nadu
            ('The Hindu', 'https://www.thehindu.com/news/states/tamil-nadu/feeder/default.rss', 'WORLD'),
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/7098091.cms', 'WORLD'),
        ],
        'KA': [  # Karnataka / Bengaluru
            ('The Hindu', 'https://www.thehindu.com/news/states/karnataka/feeder/default.rss', 'WORLD'),
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/7142025.cms', 'WORLD'),
        ],
        'KL': [  # Kerala
            ('The Hindu', 'https://www.thehindu.com/news/states/kerala/feeder/default.rss', 'WORLD'),
        ],
        'AP': [  # Andhra Pradesh
            ('The Hindu', 'https://www.thehindu.com/news/states/andhra-pradesh/feeder/default.rss', 'WORLD'),
        ],
        'TS': [  # Telangana / Hyderabad
            ('The Hindu', 'https://www.thehindu.com/news/states/telangana/feeder/default.rss', 'WORLD'),
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/7528676.cms', 'WORLD'),
        ],
        'DL': [  # Delhi
            ('Times of India',  'https://timesofindia.indiatimes.com/rssfeeds/2647163.cms', 'WORLD'),
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/delhi-news/rssfeed.xml', 'WORLD'),
        ],
        'MH': [  # Maharashtra / Mumbai
            ('Times of India',  'https://timesofindia.indiatimes.com/rssfeeds/3908999.cms', 'WORLD'),
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/mumbai-news/rssfeed.xml', 'WORLD'),
        ],
        'WB': [  # West Bengal / Kolkata
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/2250067.cms', 'WORLD'),
        ],
        'UP': [  # Uttar Pradesh / Lucknow
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/2916700.cms', 'WORLD'),
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/lucknow-news/rssfeed.xml', 'WORLD'),
        ],
        'GJ': [  # Gujarat
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/3540702.cms', 'WORLD'),
        ],
        'RJ': [  # Rajasthan
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/3947011.cms', 'WORLD'),
        ],
        'PB': [  # Punjab / Chandigarh
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/punjab-news/rssfeed.xml', 'WORLD'),
        ],
        'HR': [  # Haryana
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/haryana-news/rssfeed.xml', 'WORLD'),
        ],
        'MP': [  # Madhya Pradesh
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/7503091.cms', 'WORLD'),
        ],
        'BR': [  # Bihar
            ('Times of India', 'https://timesofindia.indiatimes.com/rssfeeds/7070221.cms', 'WORLD'),
            ('Hindustan Times', 'https://www.hindustantimes.com/feeds/rss/patna-news/rssfeed.xml', 'WORLD'),
        ],
    }

    # ── State detection from article text ────────────────────────────────────
    # Used to auto-tag national feed articles with the right Indian state
    STATE_KEYWORDS = {
        'DL': ['delhi', 'new delhi', 'dilli', 'lutyens delhi', 'delhi ncr'],
        'MH': ['mumbai', 'pune', 'nagpur', 'nashik', 'maharashtra', 'thane', 'aurangabad', 'solapur', 'navi mumbai'],
        'KA': ['bengaluru', 'bangalore', 'mysuru', 'mysore', 'karnataka', 'hubli', 'mangaluru', 'mangalore', 'belagavi'],
        'TN': ['chennai', 'tamil nadu', 'madurai', 'coimbatore', 'salem', 'trichy', 'tirunelveli', 'vellore', 'erode'],
        'TS': ['hyderabad', 'telangana', 'warangal', 'khammam', 'nizamabad', 'secunderabad'],
        'AP': ['andhra pradesh', 'vijayawada', 'visakhapatnam', 'vizag', 'tirupati', 'guntur', 'amaravati', 'rajamahendravaram'],
        'KL': ['kerala', 'kochi', 'thiruvananthapuram', 'kozhikode', 'thrissur', 'calicut', 'kollam', 'kannur'],
        'WB': ['kolkata', 'west bengal', 'howrah', 'siliguri', 'asansol', 'durgapur', 'calcutta'],
        'UP': ['lucknow', 'uttar pradesh', 'varanasi', 'agra', 'prayagraj', 'allahabad', 'kanpur', 'meerut', 'noida', 'ghaziabad', 'gorakhpur', 'aligarh'],
        'RJ': ['jaipur', 'rajasthan', 'jodhpur', 'udaipur', 'ajmer', 'kota', 'bikaner'],
        'GJ': ['gujarat', 'ahmedabad', 'surat', 'vadodara', 'rajkot', 'gandhinagar', 'anand'],
        'PB': ['punjab', 'amritsar', 'ludhiana', 'jalandhar', 'patiala', 'mohali'],
        'HR': ['haryana', 'gurugram', 'gurgaon', 'faridabad', 'rohtak', 'panipat', 'karnal'],
        'BR': ['bihar', 'patna', 'gaya', 'muzaffarpur', 'bhagalpur', 'nalanda', 'bodh gaya'],
        'MP': ['madhya pradesh', 'bhopal', 'indore', 'jabalpur', 'gwalior', 'ujjain'],
        'OD': ['odisha', 'bhubaneswar', 'cuttack', 'rourkela', 'puri', 'brahmapur'],
        'AS': ['assam', 'guwahati', 'dispur', 'silchar', 'dibrugarh', 'jorhat'],
        'JH': ['jharkhand', 'ranchi', 'jamshedpur', 'dhanbad', 'bokaro'],
        'CG': ['chhattisgarh', 'raipur', 'bilaspur', 'durg', 'bhilai'],
        'JK': ['kashmir', 'jammu', 'srinagar', 'pulwama', 'kupwara', 'anantnag', 'j&k', 'j & k'],
        'GA': ['goa', 'panaji', 'margao', 'vasco'],
        'UK': ['uttarakhand', 'dehradun', 'haridwar', 'rishikesh', 'nainital', 'mussoorie'],
        'HP': ['himachal pradesh', 'shimla', 'manali', 'dharamsala', 'kullu'],
    }

    @staticmethod
    def detect_state(title: str, description: str = '') -> str:
        """Return IndianState code if article is clearly about a specific state, else ''."""
        text = (title + ' ' + (description or '')).lower()
        for state_code, keywords in IndiaNewsService.STATE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return state_code
        return ''

    @staticmethod
    def _fetch_feed(source_name: str, feed_url: str, default_category: str,
                    state_code: str = '') -> int:
        """
        Fetch a single RSS feed and save articles to DB.
        Returns number of new articles added.
        'source_name' overrides the feed's own source tag so we always know the publisher.
        """
        logger.info(f"[IndiaNews] Fetching {source_name} → {feed_url}")
        try:
            feed = feedparser.parse(feed_url, request_headers=IndiaNewsService._HEADERS)
            if not feed.entries:
                logger.warning(f"[IndiaNews] No entries from {feed_url}")
                return 0

            articles_added = 0
            # Limit content pre-scraping to keep build time reasonable
            content_scraped_this_feed = 0
            MAX_CONTENT_SCRAPE_PER_FEED = 5
            for entry in feed.entries:
                try:
                    # ── Published date ────────────────────────────────────
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = timezone.make_aware(
                            datetime(*entry.published_parsed[:6])
                        )
                    else:
                        published_at = timezone.now()

                    # Skip articles older than 3 days
                    if (timezone.now() - published_at).days > 3:
                        continue

                    # ── Clean description ─────────────────────────────────
                    raw_desc = entry.get('summary', '') or ''
                    clean_desc = GoogleNewsService.clean_html(raw_desc)

                    # ── Image: feed thumbnail → og scrape → fallback ──────
                    image_url = GoogleNewsService.extract_image_url(entry)
                    if not image_url:
                        image_url = GoogleNewsService.fetch_image_from_url(entry.link)
                    if not image_url:
                        image_url = GoogleNewsService.get_fallback_image(None, title=entry.title)

                    # ── Category: use feed default, override with keyword ──
                    category = (
                        GoogleNewsService.classify_category(entry.title, clean_desc)
                        or default_category
                    )

                    # ── State: explicit (state feed) → keyword detection ──
                    indian_state = state_code or IndiaNewsService.detect_state(
                        entry.title, clean_desc
                    )

                    # ── Translate non-English title/description to English ─
                    save_title = entry.title
                    save_desc = clean_desc
                    orig_title = ''
                    orig_desc = None
                    orig_lang = ''
                    is_translated = False
                    try:
                        from news.translation_service import TranslationService, is_non_english
                        if is_non_english(entry.title) or is_non_english(clean_desc):
                            result = TranslationService.translate_article_inline(
                                entry.title, clean_desc
                            )
                            if result['translated']:
                                orig_title = entry.title
                                orig_desc = clean_desc or None
                                orig_lang = result['lang']
                                save_title = result['title']
                                save_desc = result['description']
                                is_translated = True
                    except Exception as te:
                        logger.warning(f"[IndiaNews] Inline translation error: {te}")

                    article, created = NewsArticle.objects.update_or_create(
                        url=entry.link,
                        defaults={
                            'title':                save_title,
                            'description':          save_desc,
                            'source':               source_name,
                            'image_url':            image_url,
                            'published_at':         published_at,
                            'continent':            Continent.ASIA,
                            'is_indian_news':       True,
                            'category':             category,
                            'indian_state':         indian_state,
                            'original_title':       orig_title,
                            'original_description': orig_desc,
                            'original_language':    orig_lang,
                            'is_translated':        is_translated,
                        }
                    )
                    if created:
                        articles_added += 1
                        # Pre-scrape full content for new articles using real
                        # publisher URLs (done at build/fetch time where network
                        # access is less restricted than production gunicorn).
                        if (not article.content
                                and article.url
                                and 'news.google.com' not in article.url
                                and content_scraped_this_feed < MAX_CONTENT_SCRAPE_PER_FEED):
                            try:
                                import trafilatura
                                downloaded = trafilatura.fetch_url(article.url)
                                if downloaded:
                                    text = trafilatura.extract(
                                        downloaded,
                                        include_comments=False,
                                        include_tables=False,
                                        no_fallback=False,
                                    )
                                    if text and len(text) > 200:
                                        article.content = text
                                        article.save(update_fields=['content'])
                                        content_scraped_this_feed += 1
                            except Exception:
                                pass  # non-fatal, detail view will retry
                except Exception as e:
                    logger.error(f"[IndiaNews] Error processing entry from {source_name}: {e}")
                    continue

            logger.info(f"[IndiaNews] {source_name}: {articles_added} new articles")
            return articles_added

        except Exception as e:
            logger.error(f"[IndiaNews] Failed to fetch {feed_url}: {e}")
            return 0

    @classmethod
    def fetch_national(cls) -> int:
        """Fetch all national / top-level India feeds."""
        total = 0
        for source, url, cat in cls.NATIONAL_FEEDS:
            total += cls._fetch_feed(source, url, cat)
        return total

    @classmethod
    def fetch_categories(cls) -> int:
        """Fetch all category-specific India feeds."""
        total = 0
        for source, url, cat in cls.CATEGORY_FEEDS:
            total += cls._fetch_feed(source, url, cat)
        return total

    @classmethod
    def fetch_states(cls) -> dict:
        """Fetch all state / city-level feeds. Returns {state_code: count}."""
        results = {}
        for state_code, feeds in cls.STATE_FEEDS.items():
            count = 0
            for source, url, cat in feeds:
                count += cls._fetch_feed(source, url, cat, state_code=state_code)
            results[state_code] = count
        return results

    @classmethod
    def fetch_all(cls) -> dict:
        """
        Run all India feeds: national → category → state.
        Returns combined results dict.
        """
        results = {}
        results['india_national'] = cls.fetch_national()
        results['india_categories'] = cls.fetch_categories()
        state_results = cls.fetch_states()
        results.update({f'india_state:{k}': v for k, v in state_results.items()})
        total = sum(results.values())
        logger.info(f"[IndiaNews] Complete. {total} new articles total. {results}")
        return results
