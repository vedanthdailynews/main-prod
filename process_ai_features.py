"""
Script to process all existing articles with AI tagging and credibility scoring.
This works WITHOUT any API keys - uses rule-based AI!
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle
from news.ai_service import ai_service
from django.db.models import Q

def process_all_articles():
    """Process all articles with AI features."""
    
    # Get all articles that don't have tags or credibility scores
    articles = NewsArticle.objects.filter(
        Q(tags=[]) | Q(credibility_score=0.0)
    )
    
    total = articles.count()
    if total == 0:
        print("No articles need processing. All articles already have AI data!")
        return
    
    print(f"\n{'='*70}")
    print(f"Processing {total} articles with AI features...")
    print(f"{'='*70}\n")
    
    processed = 0
    high_cred = 0
    medium_cred = 0
    low_cred = 0
    
    for i, article in enumerate(articles, 1):
        try:
            # Process article with AI
            ai_result = ai_service.process_article(article)
            
            # Update article fields
            article.tags = ai_result['tags']
            article.credibility_score = ai_result['credibility_score']
            article.sentiment = ai_result['sentiment']
            article.summary = ai_result['summary']
            article.save(update_fields=['tags', 'credibility_score', 'sentiment', 'summary'])
            
            # Count credibility categories
            if ai_result['credibility_score'] >= 80:
                high_cred += 1
                cred_badge = "✅ VERIFIED"
            elif ai_result['credibility_score'] >= 50:
                medium_cred += 1
                cred_badge = "⚠️  UNVERIFIED"
            else:
                low_cred += 1
                cred_badge = "🚫 DISPUTED"
            
            # Print progress
            if i % 10 == 0 or i == total:
                print(f"\nProgress: {i}/{total} articles processed")
            
            # Show details for every article
            print(f"\n{i}. {article.title[:60]}...")
            print(f"   Source: {article.source[:30]}")
            print(f"   Credibility: {cred_badge} ({ai_result['credibility_score']}/100)")
            print(f"   Sentiment: {ai_result['sentiment'].upper()}")
            print(f"   Tags: {', '.join(ai_result['tags'][:5])}")
            
            processed += 1
            
        except Exception as e:
            print(f"\n❌ Error processing article {article.id}: {e}")
            continue
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"✨ PROCESSING COMPLETE!")
    print(f"{'='*70}")
    print(f"\n📊 Summary:")
    print(f"   Total processed: {processed}")
    print(f"   ✅ Verified (80-100): {high_cred} articles")
    print(f"   ⚠️  Unverified (50-79): {medium_cred} articles")
    print(f"   🚫 Disputed (0-49): {low_cred} articles")
    
    # Show tag statistics
    print(f"\n🏷️  Top Tags Generated:")
    from collections import Counter
    all_tags = []
    for article in NewsArticle.objects.exclude(tags=[]):
        all_tags.extend(article.tags)
    
    if all_tags:
        tag_counts = Counter(all_tags).most_common(10)
        for tag, count in tag_counts:
            print(f"   #{tag}: {count} articles")
    
    print(f"\n{'='*70}")
    print("✅ All articles now have:")
    print("   • Smart AI tags for better search")
    print("   • Credibility scores to fight fake news")
    print("   • Sentiment analysis")
    print("   • AI summaries (if description available)")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    process_all_articles()
