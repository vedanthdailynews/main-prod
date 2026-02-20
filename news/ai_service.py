"""AI service for processing news articles with smart tagging and credibility scoring."""
import os
import logging
import re
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered news processing."""
    
    # Trusted news sources with high credibility
    TRUSTED_SOURCES = [
        'times of india', 'the hindu', 'indian express', 'hindustan times',
        'reuters', 'pti', 'ani', 'ndtv', 'the wire', 'scroll.in',
        'bbc', 'cnn', 'bloomberg', 'mint', 'business standard',
        'livemint', 'moneycontrol', 'economic times', 'financial express'
    ]
    
    # Suspicious indicators that reduce credibility
    SUSPICIOUS_PATTERNS = [
        r'\bshocking\b', r'\byou won\'t believe\b', r'\bmind[- ]?blowing\b',
        r'\b100%\b', r'\bguaranteed\b', r'\bmiracle\b', r'\bsecret\b',
        r'\bexclusive leak\b', r'\bunconfirmed\b', r'\brumor\b'
    ]
    
    def __init__(self):
        self.openai_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.anthropic_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        self.provider = 'openai' if self.openai_key else 'anthropic' if self.anthropic_key else None
    
    def process_article(self, article) -> Dict:
        """Process article with AI to generate summary, sentiment, tags, and credibility score."""
        result = {
            'summary': '',
            'sentiment': 'neutral',
            'tags': [],
            'credibility_score': 0.0
        }
        
        # Generate tags (works without API)
        result['tags'] = self.generate_tags(article)
        
        # Calculate credibility score (works without API)
        result['credibility_score'] = self.calculate_credibility(article)
        
        # Generate sentiment (basic rule-based if no API)
        result['sentiment'] = self.analyze_sentiment(article)
        
        # Generate summary (requires API or fallback to truncation)
        if self.provider:
            try:
                ai_result = self._process_with_ai(article)
                result.update(ai_result)
            except Exception as e:
                logger.error(f"AI processing error: {e}")
                result['summary'] = self._create_basic_summary(article)
        else:
            result['summary'] = self._create_basic_summary(article)
        
        return result
    
    def generate_tags(self, article) -> List[str]:
        """Generate relevant tags from article content using keyword extraction."""
        text = f"{article.title} {article.description or ''}".lower()
        
        # Predefined important keywords for Indian news
        keyword_categories = {
            # Government & Politics
            'budget': ['budget', 'fiscal', 'taxation', 'finance minister', 'revenue'],
            'modi': ['modi', 'prime minister', 'pm'],
            'government': ['government', 'ministry', 'policy', 'scheme'],
            'election': ['election', 'voting', 'campaign', 'bjp', 'congress', 'aap'],
            
            # Economy & Finance
            'economy': ['economy', 'gdp', 'growth', 'inflation', 'rbi'],
            'tax': ['tax', 'gst', 'income tax', 'customs', 'duty'],
            'rupee': ['rupee', 'currency', 'forex', 'exchange rate'],
            'stock-market': ['nifty', 'sensex', 'stock', 'market', 'bse', 'nse'],
            'banking': ['bank', 'loan', 'credit', 'deposit', 'interest rate'],
            
            # Business & Industry
            'startup': ['startup', 'unicorn', 'venture', 'entrepreneur'],
            'real-estate': ['property', 'real estate', 'housing', 'realty'],
            'automobile': ['car', 'vehicle', 'automobile', 'ev', 'electric vehicle'],
            'tech': ['technology', 'ai', 'software', 'digital', 'internet'],
            
            # Infrastructure
            'infrastructure': ['infrastructure', 'road', 'highway', 'metro', 'railway'],
            'airport': ['airport', 'aviation', 'airline', 'flight'],
            
            # Social Issues
            'education': ['education', 'school', 'university', 'student', 'exam'],
            'healthcare': ['health', 'hospital', 'medical', 'doctor', 'treatment'],
            'employment': ['job', 'employment', 'unemployment', 'salary', 'wage'],
            
            # Law & Justice
            'court': ['supreme court', 'high court', 'judge', 'verdict', 'bail'],
            'crime': ['crime', 'police', 'arrest', 'murder', 'theft'],
            
            # Environment
            'climate': ['climate', 'environment', 'pollution', 'emission'],
            'disaster': ['flood', 'earthquake', 'cyclone', 'disaster', 'emergency'],
            
            # Sports
            'cricket': ['cricket', 'bcci', 'ipl', 'test match', 'odi'],
            'olympics': ['olympic', 'medal', 'athlete', 'sports'],
            
            # Entertainment
            'bollywood': ['bollywood', 'film', 'movie', 'actor', 'actress'],
        }
        
        tags = []
        
        # Check each category
        for tag, keywords in keyword_categories.items():
            for keyword in keywords:
                if keyword in text:
                    tags.append(tag)
                    break  # Only add tag once per category
        
        # Add state-specific tag if present
        if hasattr(article, 'indian_state') and article.indian_state:
            state_name = article.get_indian_state_display().lower().replace(' ', '-')
            tags.append(state_name)
        
        # Add category as tag
        if hasattr(article, 'category') and article.category:
            tags.append(article.category.lower())
        
        # Remove duplicates and limit to 8 tags
        tags = list(set(tags))[:8]
        
        return tags if tags else ['general', 'news']
    
    def calculate_credibility(self, article) -> float:
        """Calculate credibility score (0-100) based on multiple factors."""
        score = 50.0  # Start with neutral score
        
        # Factor 1: Source reputation (+30 points for trusted sources)
        source_lower = article.source.lower()
        is_trusted = any(trusted in source_lower for trusted in self.TRUSTED_SOURCES)
        if is_trusted:
            score += 30
        
        # Factor 2: Check for suspicious patterns in title (-20 points)
        title_lower = article.title.lower()
        suspicious_count = sum(1 for pattern in self.SUSPICIOUS_PATTERNS 
                              if re.search(pattern, title_lower, re.IGNORECASE))
        if suspicious_count > 0:
            score -= (20 * min(suspicious_count, 2))  # Max -40 points
        
        # Factor 3: Description quality (+10 points if good description)
        if article.description and len(article.description) > 100:
            score += 10
        
        # Factor 4: Has image (+5 points - legitimate news usually has images)
        if article.image_url:
            score += 5
        
        # Factor 5: Excessive capitalization (-15 points)
        capitals = sum(1 for c in article.title if c.isupper())
        if capitals > len(article.title) * 0.5:  # More than 50% caps
            score -= 15
        
        # Factor 6: Excessive punctuation (-10 points)
        punctuation_count = len(re.findall(r'[!?]{2,}', article.title))
        if punctuation_count > 0:
            score -= 10
        
        # Factor 7: URL structure (+5 points for https, -10 for suspicious TLD)
        if article.url:
            if article.url.startswith('https://'):
                score += 5
            suspicious_tlds = ['.xyz', '.top', '.click', '.link']
            if any(tld in article.url for tld in suspicious_tlds):
                score -= 10
        
        # Ensure score is between 0-100
        score = max(0.0, min(100.0, score))
        
        return round(score, 1)
    
    def analyze_sentiment(self, article) -> str:
        """Analyze sentiment using rule-based approach."""
        text = f"{article.title} {article.description or ''}".lower()
        
        # Positive keywords
        positive_words = [
            'success', 'win', 'growth', 'gain', 'profit', 'increase', 'improve',
            'achieve', 'milestone', 'record', 'best', 'excellent', 'breakthrough',
            'innovation', 'advance', 'surge', 'boost', 'rise', 'soar'
        ]
        
        # Negative keywords
        negative_words = [
            'loss', 'fail', 'crash', 'drop', 'decline', 'fall', 'collapse',
            'crisis', 'disaster', 'worst', 'violence', 'death', 'kill', 'attack',
            'scam', 'fraud', 'corrupt', 'accident', 'fire', 'shortage'
        ]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count + 1:
            return 'positive'
        elif negative_count > positive_count + 1:
            return 'negative'
        else:
            return 'neutral'
    
    def _create_basic_summary(self, article) -> str:
        """Create basic summary by truncating description."""
        if article.description:
            words = article.description.split()
            if len(words) > 30:
                return ' '.join(words[:30]) + '...'
            return article.description
        return article.title[:150] + '...'
    
    def _process_with_ai(self, article) -> Dict:
        """Process with AI API if available."""
        if self.provider == 'openai':
            return self._process_with_openai(article)
        elif self.provider == 'anthropic':
            return self._process_with_anthropic(article)
        return {}
    
    def _process_with_openai(self, article) -> Dict:
        """Process article using OpenAI API."""
        try:
            import openai
            openai.api_key = self.openai_key
            
            prompt = f"""Analyze this news article:
            
Title: {article.title}
Description: {article.description or ''}

Provide a concise 2-3 sentence summary."""
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a news analyst. Provide clear, concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            return {'summary': response.choices[0].message.content.strip()}
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {e}")
            return {}
    
    def _process_with_anthropic(self, article) -> Dict:
        """Process article using Anthropic Claude API."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            prompt = f"""Analyze this news article:
            
Title: {article.title}
Description: {article.description or ''}

Provide a concise 2-3 sentence summary."""
            
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=150,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return {'summary': message.content[0].text.strip()}
            
        except Exception as e:
            logger.error(f"Anthropic processing error: {e}")
            return {}


# Singleton instance
ai_service = AIService()
