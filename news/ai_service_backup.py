"""
AI service for processing news articles with OpenAI and Anthropic.
"""
import os
import logging
from typing import Dict, List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered news processing."""
    
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.anthropic_key = settings.ANTHROPIC_API_KEY
        self.provider = 'openai' if self.openai_key else 'anthropic' if self.anthropic_key else None
    
    def process_article(self, article) -> Dict:
        """
        Process article with AI to generate summary, sentiment, and tags.
        
        Args:
            article: NewsArticle instance
            
        Returns:
            Dictionary with summary, sentiment, and tags
        """
        if not self.provider:
            logger.warning("No AI provider configured")
            return self._fallback_processing(article)
        
        try:
            if self.provider == 'openai':
                return self._process_with_openai(article)
            elif self.provider == 'anthropic':
                return self._process_with_anthropic(article)
        except Exception as e:
            logger.error(f"AI processing error: {e}")
            return self._fallback_processing(article)
    
    def _process_with_openai(self, article) -> Dict:
        """Process article using OpenAI API."""
        try:
            import openai
            openai.api_key = self.openai_key
            
            prompt = self._create_prompt(article)
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a news analyst. Analyze the article and provide a concise summary, sentiment (positive/negative/neutral), and 5 relevant tags."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            return self._parse_ai_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"OpenAI processing error: {e}")
            return self._fallback_processing(article)
    
    def _process_with_anthropic(self, article) -> Dict:
        """Process article using Anthropic Claude API."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            prompt = self._create_prompt(article)
            
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=300,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return self._parse_ai_response(message.content[0].text)
            
        except Exception as e:
            logger.error(f"Anthropic processing error: {e}")
            return self._fallback_processing(article)
    
    def _create_prompt(self, article) -> str:
        """Create prompt for AI processing."""
        content = f"""
Title: {article.title}
Description: {article.description or ''}
Source: {article.source}

Analyze this news article and provide:
1. A concise 2-3 sentence summary
2. Sentiment (positive, negative, or neutral)
3. Five relevant tags/keywords

Format your response as:
SUMMARY: [your summary]
SENTIMENT: [positive/negative/neutral]
TAGS: [tag1, tag2, tag3, tag4, tag5]
"""
        return content.strip()
    
    def _parse_ai_response(self, response: str) -> Dict:
        """Parse AI response into structured data."""
        result = {
            'summary': '',
            'sentiment': 'neutral',
            'tags': []
        }
        
        try:
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('SUMMARY:'):
                    result['summary'] = line.replace('SUMMARY:', '').strip()
                elif line.startswith('SENTIMENT:'):
                    sentiment = line.replace('SENTIMENT:', '').strip().lower()
                    if sentiment in ['positive', 'negative', 'neutral']:
                        result['sentiment'] = sentiment
                elif line.startswith('TAGS:'):
                    tags_str = line.replace('TAGS:', '').strip()
                    result['tags'] = [tag.strip() for tag in tags_str.split(',')]
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
        
        return result
    
    def _fallback_processing(self, article) -> Dict:
        """Fallback processing when AI is not available."""
        # Simple rule-based processing
        summary = article.description[:200] + '...' if article.description else article.title
        
        # Simple sentiment based on keywords
        text = (article.title + ' ' + (article.description or '')).lower()
        positive_words = ['success', 'win', 'growth', 'improve', 'gain', 'rise']
        negative_words = ['fail', 'loss', 'decline', 'crisis', 'fall', 'crash']
        
        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)
        
        if pos_count > neg_count:
            sentiment = 'positive'
        elif neg_count > pos_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'summary': summary,
            'sentiment': sentiment,
            'tags': []
        }
