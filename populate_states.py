"""
Script to populate Indian state data for existing news articles
by analyzing their titles and descriptions for state mentions.
"""
import os
import sys
import django
import re

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')
django.setup()

from news.models import NewsArticle, IndianState

# Map of state names/keywords to state codes
STATE_KEYWORDS = {
    'AP': ['andhra pradesh', 'andhra', 'ap state', 'amaravati', 'visakhapatnam', 'vijayawada', 'tirupati'],
    'AR': ['arunachal pradesh', 'arunachal', 'itanagar'],
    'AS': ['assam', 'guwahati', 'dispur'],
    'BR': ['bihar', 'patna', 'gaya', 'bhagalpur'],
    'CG': ['chhattisgarh', 'raipur', 'bhilai'],
    'DL': ['delhi', 'new delhi', 'ncr', 'capital'],
    'GA': ['goa', 'panaji', 'margao'],
    'GJ': ['gujarat', 'ahmedabad', 'surat', 'gandhinagar', 'rajkot', 'vadodara'],
    'HR': ['haryana', 'chandigarh', 'gurgaon', 'gurugram', 'faridabad', 'rohtak'],
    'HP': ['himachal pradesh', 'himachal', 'shimla', 'dharamshala', 'manali'],
    'JH': ['jharkhand', 'ranchi', 'jamshedpur', 'dhanbad'],
    'KA': ['karnataka', 'bengaluru', 'bangalore', 'mysore', 'mangalore', 'hubli'],
    'KL': ['kerala', 'thiruvananthapuram', 'kochi', 'cochin', 'calicut', 'kozhikode'],
    'MP': ['madhya pradesh', 'mp state', 'bhopal', 'indore', 'gwalior', 'jabalpur'],
    'MH': ['maharashtra', 'mumbai', 'pune', 'nagpur', 'thane', 'nashik', 'aurangabad'],
    'MN': ['manipur', 'imphal'],
    'ML': ['meghalaya', 'shillong'],
    'MZ': ['mizoram', 'aizawl'],
    'NL': ['nagaland', 'kohima', 'dimapur'],
    'OD': ['odisha', 'orissa', 'bhubaneswar', 'cuttack', 'puri'],
    'PB': ['punjab', 'chandigarh', 'ludhiana', 'amritsar', 'jalandhar', 'patiala'],
    'RJ': ['rajasthan', 'jaipur', 'jodhpur', 'udaipur', 'kota', 'ajmer'],
    'SK': ['sikkim', 'gangtok'],
    'TN': ['tamil nadu', 'tn state', 'chennai', 'madras', 'coimbatore', 'madurai', 'tiruchirappalli', 'trichy'],
    'TG': ['telangana', 'hyderabad', 'warangal', 'nizamabad'],
    'TR': ['tripura', 'agartala'],
    'UP': ['uttar pradesh', 'up state', 'lucknow', 'kanpur', 'agra', 'varanasi', 'meerut', 'allahabad', 'prayagraj', 'noida', 'ghaziabad'],
    'UT': ['uttarakhand', 'dehradun', 'haridwar', 'rishikesh'],
    'WB': ['west bengal', 'bengal', 'kolkata', 'calcutta', 'darjeeling', 'siliguri'],
    'AN': ['andaman', 'nicobar', 'port blair'],
    'CH': ['chandigarh'],
    'DN': ['dadra and nagar haveli', 'daman and diu'],
    'JK': ['jammu and kashmir', 'jammu', 'kashmir', 'srinagar', 'j&k'],
    'LA': ['ladakh', 'leh', 'kargil'],
    'LD': ['lakshadweep', 'kavaratti'],
    'PY': ['puducherry', 'pondicherry', 'pondy'],
}

def detect_state(text):
    """
    Detect Indian state from text by matching keywords.
    Returns state code or None.
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Check each state's keywords
    for state_code, keywords in STATE_KEYWORDS.items():
        for keyword in keywords:
            # Use word boundary regex for better matching
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                return state_code
    
    return None

def populate_states():
    """Populate state data for all articles."""
    articles = NewsArticle.objects.all()
    total = articles.count()
    updated = 0
    
    print(f'Processing {total} articles...\n')
    
    for article in articles:
        # Combine title and description for better matching
        combined_text = f"{article.title} {article.description or ''}"
        
        # Detect state
        state_code = detect_state(combined_text)
        
        if state_code:
            article.indian_state = state_code
            article.is_indian_news = True
            article.save(update_fields=['indian_state', 'is_indian_news'])
            updated += 1
            state_name = dict(IndianState.choices).get(state_code)
            print(f'✓ Updated: {article.title[:60]}... → {state_name}')
    
    print(f'\n' + '='*70)
    print(f'Summary:')
    print(f'Total articles: {total}')
    print(f'Updated with state: {updated}')
    print(f'Remaining without state: {total - updated}')
    print('='*70)
    
    # Show distribution
    from django.db.models import Count
    state_distribution = NewsArticle.objects.exclude(
        indian_state=None
    ).values('indian_state').annotate(
        count=Count('id')
    ).order_by('-count')
    
    if state_distribution:
        print(f'\nState-wise distribution:')
        for item in state_distribution:
            state_name = dict(IndianState.choices).get(item['indian_state'])
            print(f'{state_name}: {item["count"]} articles')

if __name__ == '__main__':
    populate_states()
