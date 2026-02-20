"""
Smart contextual image service for news articles.
Fetches relevant images based on named entities (people, orgs, events)
mentioned in the article title and description.
Uses Wikipedia's free REST API — no API key needed.
"""
import requests
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity → Wikipedia page-title mapping
# Keys are lowercase; more SPECIFIC entries must come before shorter ones.
# The iterator stops at the first match, so order matters.
# ---------------------------------------------------------------------------
ENTITY_MAP = {
    # ── Indian Prime Ministers / Presidents ──────────────────────────────
    'narendra modi':            'Narendra_Modi',
    'pm modi':                  'Narendra_Modi',
    'droupadi murmu':           'Droupadi_Murmu',
    'jagdeep dhankhar':         'Jagdeep_Dhankhar',

    # ── BJP / Central Government ─────────────────────────────────────────
    'amit shah':                'Amit_Shah',
    'rajnath singh':            'Rajnath_Singh',
    'nirmala sitharaman':       'Nirmala_Sitharaman',
    'smriti irani':             'Smriti_Irani',
    'jp nadda':                 'J._P._Nadda',
    'nitin gadkari':            'Nitin_Gadkari',
    's jaishankar':             'S._Jaishankar',
    'jaishankar':               'S._Jaishankar',

    # ── Opposition ───────────────────────────────────────────────────────
    'rahul gandhi':             'Rahul_Gandhi',
    'sonia gandhi':             'Sonia_Gandhi',
    'priyanka gandhi':          'Priyanka_Gandhi_Vadra',
    'mallikarjun kharge':       'Mallikarjun_Kharge',
    'arvind kejriwal':          'Arvind_Kejriwal',
    'mamata banerjee':          'Mamata_Banerjee',
    'yogi adityanath':          'Yogi_Adityanath',
    'nitish kumar':             'Nitish_Kumar',
    'sharad pawar':             'Sharad_Pawar',
    'akhilesh yadav':           'Akhilesh_Yadav',
    'uddhav thackeray':         'Uddhav_Thackeray',
    'hemant soren':             'Hemant_Soren',
    'naveen patnaik':           'Naveen_Patnaik',
    'chandrababu naidu':        'N._Chandrababu_Naidu',
    'mk stalin':                'M._K._Stalin',
    'siddaramaiah':             'Siddaramaiah',

    # ── Indian Business Leaders ──────────────────────────────────────────
    'mukesh ambani':            'Mukesh_Ambani',
    'nita ambani':              'Nita_Ambani',
    'gautam adani':             'Gautam_Adani',
    'ratan tata':               'Ratan_Tata',
    'azim premji':              'Azim_Premji',
    'narayana murthy':          'N._R._Narayana_Murthy',
    'kumar mangalam birla':     'Kumar_Mangalam_Birla',
    'anand mahindra':           'Anand_Mahindra',

    # ── Indian Companies / Brands ────────────────────────────────────────
    'reliance industries':      'Reliance_Industries',
    'reliance jio':             'Jio',
    'adani group':              'Adani_Group',
    'tata consultancy':         'Tata_Consultancy_Services',
    'tata motors':              'Tata_Motors',
    'tata group':               'Tata_Group',
    'infosys':                  'Infosys',
    'wipro':                    'Wipro',
    'hdfc bank':                'HDFC_Bank',
    'icici bank':               'ICICI_Bank',
    'state bank of india':      'State_Bank_of_India',
    'sbi':                      'State_Bank_of_India',
    'bajaj':                    'Bajaj_Auto',
    'mahindra':                 'Mahindra_Group',
    'hero motocorp':            'Hero_MotoCorp',
    'air india':                'Air_India',
    'indigo airline':           'IndiGo',
    'indigo':                   'IndiGo',
    'ola':                      'Ola_Cabs',
    'zomato':                   'Zomato',
    'swiggy':                   'Swiggy',
    'flipkart':                 'Flipkart',
    'paytm':                    'Paytm',
    'byju':                     'BYJU\'S',

    # ── Stock Market / Finance ───────────────────────────────────────────
    'bombay stock exchange':    'Bombay_Stock_Exchange',
    'national stock exchange':  'National_Stock_Exchange_of_India',
    'reserve bank of india':    'Reserve_Bank_of_India',
    'securities and exchange board': 'Securities_and_Exchange_Board_of_India',
    'sensex':                   'BSE_SENSEX',
    'nifty 50':                 'NIFTY_50',
    'nifty':                    'NIFTY_50',
    'sebi':                     'Securities_and_Exchange_Board_of_India',
    'rbi':                      'Reserve_Bank_of_India',
    'bse':                      'Bombay_Stock_Exchange',
    'nse':                      'National_Stock_Exchange_of_India',
    'union budget':             'Indian_government_budget',
    'budget 2026':              'Indian_government_budget',
    'gst':                      'Goods_and_Services_Tax_(India)',
    'upi':                      'Unified_Payments_Interface',
    'ipo':                      'Initial_public_offering',

    # ── Indian Sports ────────────────────────────────────────────────────
    'virat kohli':              'Virat_Kohli',
    'rohit sharma':             'Rohit_Sharma',
    'ms dhoni':                 'MS_Dhoni',
    'sachin tendulkar':         'Sachin_Tendulkar',
    'pv sindhu':                'P._V._Sindhu',
    'neeraj chopra':            'Neeraj_Chopra',
    'hardik pandya':            'Hardik_Pandya',
    'shubman gill':             'Shubman_Gill',
    'jasprit bumrah':           'Jasprit_Bumrah',
    'saina nehwal':             'Saina_Nehwal',
    'mary kom':                 'Mary_Kom',
    'mirabai chanu':            'Mirabai_Chanu',
    'indian cricket team':      'India_national_cricket_team',
    'team india':               'India_national_cricket_team',
    'ipl':                      'Indian_Premier_League',
    'bcci':                     'Board_of_Control_for_Cricket_in_India',
    'world cup cricket':        'Cricket_World_Cup',

    # ── Indian Institutions / Events ─────────────────────────────────────
    'isro':                     'Indian_Space_Research_Organisation',
    'chandrayaan':              'Chandrayaan_programme',
    'gaganyaan':                'Gaganyaan',
    'mangalyaan':               'Mars_Orbiter_Mission',
    'supreme court of india':   'Supreme_Court_of_India',
    'parliament of india':      'Parliament_of_India',
    'lok sabha':                'Lok_Sabha',
    'rajya sabha':              'Rajya_Sabha',
    'indian army':              'Indian_Army',
    'indian air force':         'Indian_Air_Force',
    'indian navy':              'Indian_Navy',
    'aadhar':                   'Aadhaar',
    'aadhaar':                  'Aadhaar',
    'demonetisation':           'Demonetisation_in_India',
    'demonetization':           'Demonetisation_in_India',

    # ── International Leaders ────────────────────────────────────────────
    'donald trump':             'Donald_Trump',
    'trump':                    'Donald_Trump',
    'joe biden':                'Joe_Biden',
    'biden':                    'Joe_Biden',
    'kamala harris':            'Kamala_Harris',
    'xi jinping':               'Xi_Jinping',
    'vladimir putin':           'Vladimir_Putin',
    'putin':                    'Vladimir_Putin',
    'volodymyr zelensky':       'Volodymyr_Zelensky',
    'zelensky':                 'Volodymyr_Zelensky',
    'elon musk':                'Elon_Musk',
    'musk':                     'Elon_Musk',
    'rishi sunak':              'Rishi_Sunak',
    'keir starmer':             'Keir_Starmer',
    'starmer':                  'Keir_Starmer',
    'emmanuel macron':          'Emmanuel_Macron',
    'macron':                   'Emmanuel_Macron',
    'olaf scholz':              'Olaf_Scholz',
    'angela merkel':            'Angela_Merkel',
    'benjamin netanyahu':       'Benjamin_Netanyahu',
    'netanyahu':                'Benjamin_Netanyahu',
    'kim jong':                 'Kim_Jong-un',
    'justin trudeau':           'Justin_Trudeau',
    'antonio guterres':         'António_Guterres',

    # ── Countries / Regions in conflict ──────────────────────────────────
    'iran':                     'Iran',
    'ukraine':                  'Ukraine',
    'russia':                   'Russia',
    'israel':                   'Israel',
    'hamas':                    'Hamas',
    'gaza':                     'Gaza_Strip',
    'taiwan':                   'Taiwan',
    'pakistan':                 'Pakistan',
    'china':                    'China',

    # ── International Tech / Companies ───────────────────────────────────
    'openai':                   'OpenAI',
    'chatgpt':                  'ChatGPT',
    'microsoft':                'Microsoft',
    'google':                   'Google',
    'apple inc':                'Apple_Inc.',
    'amazon':                   'Amazon_(company)',
    'meta platforms':           'Meta_Platforms',
    'tesla':                    'Tesla,_Inc.',
    'nvidia':                   'Nvidia',
    'spacex':                   'SpaceX',

    # ── International Orgs ───────────────────────────────────────────────
    'united nations':           'United_Nations',
    'nato':                     'NATO',
    'world health organization': 'World_Health_Organization',
    'imf':                      'International_Monetary_Fund',
    'world bank':               'World_Bank',
    'g20':                      'G20',
    'g7':                       'G7',
    'brics':                    'BRICS',

    # ── Generic fallback topics ──────────────────────────────────────────
    'ukraine war':              'Russian_invasion_of_Ukraine',
    'russia ukraine':           'Russian_invasion_of_Ukraine',
    'israel hamas':             'Hamas–Israel_conflict',
    'earthquake':               'Earthquake',
    'flood':                    'Flood',
    'cyclone':                  'Cyclone',
    'artificial intelligence':  'Artificial_intelligence',
    'cryptocurrency':           'Cryptocurrency',
    'bitcoin':                  'Bitcoin',
}

# Sort keys longest-first so specific phrases match before single words
_SORTED_ENTITY_KEYS = sorted(ENTITY_MAP.keys(), key=len, reverse=True)


@lru_cache(maxsize=512)
def _fetch_wikipedia_thumbnail(wiki_title: str) -> str:
    """
    Fetch a thumbnail image URL from the Wikipedia REST summary API.
    Results are cached for the process lifetime.
    """
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_title}"
        resp = requests.get(
            url,
            timeout=6,
            headers={'User-Agent': 'VedantDailyNews/1.0 (news aggregator)'}
        )
        if resp.status_code == 200:
            data = resp.json()
            thumbnail = data.get('thumbnail', {})
            src = thumbnail.get('source', '')
            if src:
                # Upgrade to a larger image (320px wide instead of default)
                src = src.replace('/320px-', '/480px-')
                return src
    except Exception as e:
        logger.debug(f"[ImageService] Wikipedia lookup failed for '{wiki_title}': {e}")
    return ''


def get_contextual_image(title: str, description: str = '') -> str:
    """
    Scan article text for known entities and return a relevant Wikipedia image.

    Strategy:
    - Short keywords (1-2 words, e.g. 'ipl', 'bse', 'modi') → match TITLE only
      to prevent false positives from unrelated stories mixed in RSS descriptions.
    - Long keywords (3+ words, e.g. 'narendra modi') → match title first,
      then description as fallback.

    Args:
        title:       Article headline
        description: Article body / description

    Returns:
        Image URL string, or empty string if nothing matched.
    """
    title_lower = title.lower()
    desc_lower = description.lower()

    for keyword in _SORTED_ENTITY_KEYS:
        word_count = len(keyword.split())

        # Short / single-word keywords: title only (avoid pollution from RSS multi-story descriptions)
        if word_count <= 2:
            matched = keyword in title_lower
        else:
            # Long multi-word phrases: check title first, then description
            matched = (keyword in title_lower) or (keyword in desc_lower)

        if matched:
            wiki_title = ENTITY_MAP[keyword]
            img_url = _fetch_wikipedia_thumbnail(wiki_title)
            if img_url:
                logger.debug(
                    f"[ImageService] Matched '{keyword}' ({word_count}w, {'title' if keyword in title_lower else 'desc'}) → {wiki_title}"
                )
                return img_url

    return ''
