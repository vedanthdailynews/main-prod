"""
Script to organize articles into ePaper pages and sections.
Assigns page numbers, sections, and sizes to articles.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle
from django.utils import timezone
from datetime import datetime


def organize_epaper():
    """Organize articles into ePaper format."""
    
    # Get today's articles
    today = timezone.now().date()
    articles = NewsArticle.objects.filter(published_at__date=today).order_by('-published_at')
    
    if not articles.exists():
        # If no articles today, use most recent articles
        print("No articles from today, using most recent articles...")
        articles = NewsArticle.objects.all().order_by('-published_at')[:50]
    
    print(f"Organizing {articles.count()} articles into ePaper format...")
    
    # Section mapping based on category
    section_mapping = {
        'WORLD': 'WORLD',
        'BUSINESS': 'BUSINESS',
        'TECHNOLOGY': 'BUSINESS',
        'ENTERTAINMENT': 'ENTERTAINMENT',
        'SPORTS': 'SPORTS',
        'SCIENCE': 'WORLD',
        'HEALTH': 'CITY',
        'BUDGET': 'BUSINESS',
    }
    
    # Organize articles by section
    sections = {
        'FRONT_PAGE': [],
        'CITY': [],
        'NATION': [],
        'WORLD': [],
        'BUSINESS': [],
        'SPORTS': [],
        'ENTERTAINMENT': [],
    }
    
    # Sort articles into sections
    for article in articles:
        # Determine section
        if article.category in section_mapping:
            section = section_mapping[article.category]
        else:
            section = 'NATION'
        
        # Featured or high credibility articles go to front page
        if article.is_featured or article.credibility_score >= 85:
            if len(sections['FRONT_PAGE']) < 8:
                sections['FRONT_PAGE'].append(article)
                continue
        
        # Indian news goes to city/nation
        if article.is_indian_news:
            if len(sections['NATION']) < 12:
                sections['NATION'].append(article)
                continue
            elif len(sections['CITY']) < 10:
                sections['CITY'].append(article)
                continue
        
        # Add to appropriate section
        if section in sections:
            sections[section].append(article)
    
    # Assign pages and positions
    page_number = 1
    articles_per_page = 9  # 3x3 grid
    
    section_order = ['FRONT_PAGE', 'NATION', 'CITY', 'WORLD', 'BUSINESS', 'SPORTS', 'ENTERTAINMENT']
    
    updated_count = 0
    
    for section_name in section_order:
        section_articles = sections[section_name]
        
        if not section_articles:
            continue
        
        print(f"\nProcessing {section_name}: {len(section_articles)} articles")
        
        # Process articles in this section
        for idx, article in enumerate(section_articles):
            # Calculate page (new page every 9 articles)
            article_page = page_number + (idx // articles_per_page)
            position = idx % articles_per_page
            
            # Determine size
            if section_name == 'FRONT_PAGE' and idx == 0:
                # Lead story is large
                size = 'LARGE'
            elif position in [0, 1] and article.image_url:
                # Top articles with images are medium
                size = 'MEDIUM'
            elif article.image_url:
                # Articles with images are medium
                size = 'MEDIUM'
            else:
                # Text-only articles are small
                size = 'SMALL'
            
            # Update article
            article.epaper_page = article_page
            article.epaper_section = section_name
            article.epaper_position = position
            article.epaper_size = size
            article.save(update_fields=['epaper_page', 'epaper_section', 'epaper_position', 'epaper_size'])
            
            updated_count += 1
            
            if idx % 10 == 0:
                print(f"  Processed {idx + 1}/{len(section_articles)} articles")
        
        # Update page number for next section
        page_number += (len(section_articles) + articles_per_page - 1) // articles_per_page
    
    print(f"\n✅ Successfully organized {updated_count} articles into {page_number - 1} pages")
    
    # Print summary
    print("\n=== ePaper Organization Summary ===")
    for section_name in section_order:
        count = len(sections[section_name])
        if count > 0:
            print(f"{section_name}: {count} articles")
    
    # Page distribution
    print(f"\nTotal Pages: {page_number - 1}")
    print(f"Average articles per page: {updated_count / (page_number - 1):.1f}")


if __name__ == '__main__':
    organize_epaper()
