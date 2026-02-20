"""
Smart contextual image service for news articles.
Fetches relevant images based on named entities (people, orgs, events)
mentioned in the article title and description.
Uses Wikipedia's free REST API and LoremFlickr — no API key needed.
"""
import re
import hashlib
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
    # ── Tata Car Models ───────────────────────────────────────────────────
    'tata punch ev':            'Tata_Punch_(electric)',
    'tata punch':               'Tata_Punch_(electric)',
    'tata nexon ev':            'Tata_Nexon_EV',
    'tata nexon':               'Tata_Nexon',
    'tata harrier':             'Tata_Harrier',
    'tata safari':              'Tata_Safari',
    'tata curvv':               'Tata_Curvv',
    'tata altroz':              'Tata_Altroz',
    'tata tiago ev':            'Tata_Tiago_EV',
    'tata tiago':               'Tata_Tiago',
    'tata tigor':               'Tata_Tigor',
    # ── Maruti / Suzuki Models ────────────────────────────────────────────
    'maruti suzuki':            'Maruti_Suzuki',
    'maruti swift':             'Suzuki_Swift',
    'maruti baleno':            'Suzuki_Baleno',
    'maruti brezza':            'Maruti_Brezza',
    'maruti alto':              'Maruti_Alto',
    'maruti wagon r':           'Maruti_Wagon_R',
    'maruti ertiga':            'Maruti_Ertiga',
    'suzuki jimny':             'Suzuki_Jimny',
    # ── Mahindra Car Models ───────────────────────────────────────────────
    'mahindra xuv 3xo':         'Mahindra_XUV300',
    'mahindra xuv700':          'Mahindra_XUV700',
    'mahindra xuv400':          'Mahindra_XUV400',
    'mahindra scorpio':         'Mahindra_Scorpio',
    'mahindra thar':            'Mahindra_Thar',
    'mahindra bolero':          'Mahindra_Bolero',
    'mahindra be 6':            'Mahindra_BE_6',
    # ── Hyundai / Kia Models ─────────────────────────────────────────────
    'hyundai creta':            'Hyundai_Creta',
    'hyundai i20':              'Hyundai_i20',
    'hyundai verna':            'Hyundai_Verna',
    'hyundai alcazar':          'Hyundai_Alcazar',
    'kia seltos':               'Kia_Seltos',
    'kia sonet':                'Kia_Sonet',
    'kia carens':               'Kia_Carens',
    'kia ev6':                  'Kia_EV6',
    # ── International Car Brands ──────────────────────────────────────────
    'ford':                     'Ford_Motor_Company',
    'chevrolet':                'Chevrolet',
    'volkswagen':               'Volkswagen',
    'bmw':                      'BMW',
    'mercedes benz':            'Mercedes-Benz',
    'mercedes-benz':            'Mercedes-Benz',
    'audi':                     'Audi',
    'porsche':                  'Porsche',
    'toyota':                   'Toyota',
    'honda car':                'Honda',
    'nissan':                   'Nissan',
    'renault':                  'Renault',
    'volvo car':                'Volvo_Cars',
    'lamborghini':              'Lamborghini',
    'ferrari':                  'Ferrari',
    # ── EV / Auto keywords (matched title-only) ───────────────────────────
    'electric vehicle':         'Electric_vehicle',
    'ev charging':              'Charging_station',
    'charging station':         'Charging_station',
    'electric scooter':         'Electric_motorcycles_and_scooters',
    'ola electric':             'Ola_Electric',
    'ather energy':             'Ather_Energy',
    'tvs iqube':                'TVS_Motor_Company',
    'bajaj chetak':             'Bajaj_Auto',
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

# ---------------------------------------------------------------------------
# Words to skip when extracting proper nouns / search keywords
# ---------------------------------------------------------------------------
_TITLE_SKIP_WORDS = {
    'The', 'A', 'An', 'This', 'That', 'These', 'Those', 'Is', 'Are', 'Was',
    'Were', 'Has', 'Have', 'Had', 'Be', 'Been', 'How', 'Why', 'When', 'What',
    'Where', 'Who', 'Watch', 'Read', 'Get', 'See', 'Says', 'Said', 'Here',
    'Breaking', 'Live', 'New', 'Big', 'Top', 'Key', 'Major', 'Latest',
    'India', 'Indian', 'Report', 'Update', 'News', 'After', 'Over', 'From',
}

_STOP_WORDS_LC = {
    'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
    'but', 'is', 'are', 'was', 'were', 'be', 'been', 'with', 'this', 'that',
    'from', 'by', 'as', 'into', 'out', 'over', 'under', 'says', 'said',
    'amid', 'after', 'since', 'while', 'due', 'its', 'his', 'her', 'their',
    'our', 'you', 'we', 'he', 'she', 'it', 'they', 'what', 'how', 'when',
    'where', 'why', 'who', 'all', 'no', 'not', 'than', 'then', 'now', 'just',
    'more', 'also', 'has', 'have', 'had', 'get', 'got', 'up', 'about', 'new',
    'launch', 'launches', 'launched', 'price', 'prices', 'start', 'starts',
    'india', 'rs', 'lakh', 'crore', 'year', 'day', 'days', 'vs', 'per',
    'top', 'best', 'here', 'know', 'check', 'report', 'reports', 'latest',
    'big', 'key', 'live', 'breaking', 'update', 'updates', 'read', 'full',
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _extract_proper_nouns(title: str) -> list:
    """
    Extract sequences of capitalized/acronym tokens from the original article
    title — these are the most likely named entities (people, products, orgs).

    "Tata Punch EV Facelift Launched in India"  → ['Tata Punch EV', 'Tata Punch EV Facelift']
    "Narendra Modi meets Xi Jinping at G20"      → ['Narendra Modi', 'Xi Jinping', 'G20']
    "Virat Kohli scores century vs Australia"    → ['Virat Kohli', 'Australia']

    Returns list of candidate phrases sorted longest-first.
    """
    tokens = title.split()
    candidates = []
    current = []

    for raw_token in tokens:
        token = re.sub(r'[^\w\-]', '', raw_token)
        if not token:
            if current:
                candidates.append(' '.join(current))
                current = []
            continue

        # Accept: starts-with-capital OR all-caps acronym (EV, IPL, GDP…)
        is_proper = (token[0].isupper() or (token.isupper() and len(token) > 1))
        is_skip = token in _TITLE_SKIP_WORDS

        if is_proper and not is_skip:
            current.append(token)
        else:
            if len(current) >= 1:
                candidates.append(' '.join(current))
            current = []

    if current:
        candidates.append(' '.join(current))

    # Deduplicate, keep phrases with at least 1 word, sort longest-first
    seen = set()
    result = []
    for c in sorted(set(candidates), key=lambda x: len(x.split()), reverse=True):
        if c not in seen and len(c) > 1:
            seen.add(c)
            result.append(c)
    return result[:5]


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
                src = re.sub(r'/\d+px-', '/600px-', src)
                return src
    except Exception as e:
        logger.debug(f"[ImageService] Wikipedia direct lookup failed for '{wiki_title}': {e}")
    return ''


@lru_cache(maxsize=1024)
def _search_wikipedia_thumbnail(query: str) -> str:
    """
    Search Wikipedia for any query string, take the top result, return its
    thumbnail. Works for any subject — car models, politicians, films, places.

    Uses the MediaWiki Action API (pageimages + search generator).
    Free, no API key, rate-limit friendly.
    """
    try:
        params = {
            'action': 'query',
            'generator': 'search',
            'gsrsearch': query,
            'gsrlimit': 5,
            'gsrnamespace': 0,
            'prop': 'pageimages',
            'pithumbsize': 600,
            'pilimit': 5,
            'format': 'json',
            'formatversion': 2,
        }
        resp = requests.get(
            'https://en.wikipedia.org/w/api.php',
            params=params,
            timeout=8,
            headers={'User-Agent': 'VedantDailyNews/1.0 (news aggregator)'},
        )
        if resp.status_code == 200:
            pages = resp.json().get('query', {}).get('pages', [])
            # Pages are returned in search-relevance order
            for page in pages:
                src = page.get('thumbnail', {}).get('source', '')
                if src:
                    # Skip logos, icons, flags — they're rarely what we want
                    if any(skip in src.lower() for skip in [
                        'flag_of', 'logo', 'icon', 'emblem', 'coat_of_arms',
                        'wikimedia', 'commons-logo', 'question_mark',
                    ]):
                        continue
                    logger.debug(
                        f"[ImageService] Wikipedia search '{query}' → "
                        f"{page.get('title')} → {src[:60]}"
                    )
                    return src
    except Exception as e:
        logger.debug(f"[ImageService] Wikipedia search API failed for '{query}': {e}")
    return ''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_contextual_image(title: str, description: str = '') -> str:
    """
    Two-stage contextual image lookup — works for any article subject.

    Stage 1 — Entity map (fast, for pre-mapped known entities)
      Checks ENTITY_MAP against both title and description.

    Stage 2 — Wikipedia search (universal, handles anything)
      Extracts proper-noun phrases from the title, searches Wikipedia for
      each one, and returns the thumbnail of the best matching article.
      Covers politicians, celebrities, car models, companies, events, etc.
      that aren't pre-listed in the entity map.

    Examples:
      "Tata Punch EV Facelift Launched" → Wikipedia search "Tata Punch EV"
                                          → returns Tata Punch EV photo
      "Shehbaz Sharif visits Beijing"   → Wikipedia search "Shehbaz Sharif"
                                          → returns Shehbaz Sharif portrait
      "Virat Kohli scores century"      → Wikipedia search "Virat Kohli"
                                          → returns Virat Kohli photo
    """
    title_lower = title.lower()
    desc_lower  = description.lower()

    # ── Stage 1: pre-mapped entity lookup ───────────────────────────────
    for keyword in _SORTED_ENTITY_KEYS:
        word_count = len(keyword.split())
        if word_count <= 2:
            matched = keyword in title_lower
        else:
            matched = (keyword in title_lower) or (keyword in desc_lower)

        if matched:
            img_url = _fetch_wikipedia_thumbnail(ENTITY_MAP[keyword])
            if img_url:
                logger.debug(f"[ImageService] Entity map hit: '{keyword}'")
                return img_url

    # ── Stage 2: Wikipedia search on proper-noun phrases from title ──────
    candidates = _extract_proper_nouns(title)
    for phrase in candidates:
        img_url = _search_wikipedia_thumbnail(phrase)
        if img_url:
            return img_url

    return ''


@lru_cache(maxsize=1024)
def get_topic_image(title: str) -> str:
    """
    LoremFlickr fallback — fetches a Flickr photo matching title keywords.
    Used only when Wikipedia returns nothing (very new events, local news, etc.)

    Deterministic lock seed ensures the same article always gets the same image.
    """
    words = re.sub(r'[^\w\s]', ' ', title.lower()).split()
    keywords = [w for w in words if w not in _STOP_WORDS_LC and len(w) > 2][:5]

    if not keywords:
        return ''

    lock = int(hashlib.md5(title.encode()).hexdigest()[:8], 16) % 100000
    query = ','.join(keywords[:4])
    url = f"https://loremflickr.com/800/450/{query}?lock={lock}"

    try:
        resp = requests.get(url, timeout=8, allow_redirects=True)
        if resp.status_code == 200:
            final_url = resp.url
            if 'staticflickr.com' in final_url or 'loremflickr.com' in final_url:
                logger.debug(f"[ImageService] LoremFlickr '{query}' → {final_url[:70]}")
                return final_url
    except Exception as e:
        logger.debug(f"[ImageService] LoremFlickr failed for '{title[:40]}': {e}")
    return ''
