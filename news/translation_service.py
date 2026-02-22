"""
Translation service for non-English news articles.
Uses deep-translator (Google Translate free tier) with concurrent.futures
for maximum parallel throughput — no API key required.

Key design:
- detect_language(): fast Unicode-range check (no network call) to identify Hindi/Tamil/Telugu etc.
- translate_article(): translates a single article's title + description → English, saves to DB
- translate_batch(): uses ThreadPoolExecutor(max_workers=N) to translate many articles at once
- is_non_english(): quick filter — returns True for any Indian script or likely non-English text
"""
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

logger = logging.getLogger(__name__)

# ─── Language detection via Unicode character ranges ─────────────────────────
# Much faster than langdetect for the common case (Indian scripts are distinctive
# Unicode blocks that require zero network calls).
_SCRIPT_RANGES = [
    # (unicode_range_check, language_code, name)
    (lambda c: '\u0900' <= c <= '\u097F', 'hi', 'Hindi (Devanagari)'),
    (lambda c: '\u0980' <= c <= '\u09FF', 'bn', 'Bengali'),
    (lambda c: '\u0A00' <= c <= '\u0A7F', 'pa', 'Punjabi/Gurmukhi'),
    (lambda c: '\u0A80' <= c <= '\u0AFF', 'gu', 'Gujarati'),
    (lambda c: '\u0B00' <= c <= '\u0B7F', 'or', 'Odia'),
    (lambda c: '\u0B80' <= c <= '\u0BFF', 'ta', 'Tamil'),
    (lambda c: '\u0C00' <= c <= '\u0C7F', 'te', 'Telugu'),
    (lambda c: '\u0C80' <= c <= '\u0CFF', 'kn', 'Kannada'),
    (lambda c: '\u0D00' <= c <= '\u0D7F', 'ml', 'Malayalam'),
    (lambda c: '\u0E00' <= c <= '\u0E7F', 'th', 'Thai'),
    (lambda c: '\u0600' <= c <= '\u06FF', 'ar', 'Arabic/Urdu'),
    (lambda c: '\u4E00' <= c <= '\u9FFF', 'zh', 'Chinese'),
    (lambda c: '\u3040' <= c <= '\u30FF', 'ja', 'Japanese'),
    (lambda c: '\uAC00' <= c <= '\uD7AF', 'ko', 'Korean'),
]

# Minimum fraction of non-ASCII chars to consider text non-English
_NON_ASCII_THRESHOLD = 0.15


def detect_language_fast(text: str) -> str:
    """
    Detect language from Unicode character ranges — no network call.
    Returns ISO 639-1 code ('hi', 'ta', 'te', 'en', etc.) or '' if unknown.
    """
    if not text or len(text) < 4:
        return ''
    # Count characters per script
    counts = {}
    for ch in text:
        for check, code, _ in _SCRIPT_RANGES:
            if check(ch):
                counts[code] = counts.get(code, 0) + 1
                break
    if not counts:
        return 'en'
    # Most frequent script wins
    dominant = max(counts, key=counts.get)
    dominant_count = counts[dominant]
    # Only declare non-English if at least 15% of chars are that script
    if dominant_count / len(text) >= _NON_ASCII_THRESHOLD:
        return dominant
    return 'en'


def is_non_english(text: str) -> bool:
    """Quick check: is this text in a non-English / non-Latin script?"""
    lang = detect_language_fast(text or '')
    return lang not in ('en', '')


class TranslationService:
    """
    Translate non-English news articles to English using Google Translate
    (deep-translator, free, no API key).

    Uses ThreadPoolExecutor for maximum parallel throughput.
    """

    # How many parallel translation threads to use.
    # Google Translate free tier is rate-limited per IP;
    # 20 workers gives good throughput without hitting 429s.
    MAX_WORKERS = 20

    # Minimum article title length before considering translation
    MIN_TITLE_LEN = 5

    @staticmethod
    def _translate_text(text: str, source_lang: str = 'auto') -> str:
        """
        Translate a single text to English.
        Returns translated string, or original on failure.
        """
        if not text or not text.strip():
            return text
        try:
            from deep_translator import GoogleTranslator
            # GoogleTranslator auto-detects source if source='auto'
            translated = GoogleTranslator(source=source_lang, target='en').translate(text)
            return translated if translated else text
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text

    @classmethod
    def translate_article(cls, article) -> bool:
        """
        Translate a single NewsArticle's title + description to English in-place.
        Saves to DB and marks is_translated=True.
        Returns True if translation happened, False if already English or failed.
        """
        if article.is_translated:
            return False

        title = article.title or ''
        description = article.description or ''

        # Fast language check
        lang = detect_language_fast(title)
        if lang in ('en', ''):
            # Double-check description if title seems English but might be mixed
            lang_desc = detect_language_fast(description)
            if lang_desc in ('en', ''):
                return False
            lang = lang_desc

        logger.info(f"Translating [{lang}] article id={article.pk}: {title[:50]}…")

        try:
            # Translate title
            new_title = cls._translate_text(title, source_lang=lang)
            # Translate description (may be longer — truncate to 5000 chars for API)
            new_description = ''
            if description:
                new_description = cls._translate_text(description[:5000], source_lang=lang)

            if not new_title or new_title == title:
                return False

            # Save originals + translated values
            article.original_title = title
            article.original_description = description or None
            article.original_language = lang
            article.title = new_title
            if new_description:
                article.description = new_description
            article.is_translated = True

            article.save(update_fields=[
                'title', 'description',
                'original_title', 'original_description',
                'original_language', 'is_translated',
            ])
            logger.info(f"  → Translated: {new_title[:60]}")
            return True

        except Exception as e:
            logger.error(f"Failed to translate article {article.pk}: {e}")
            return False

    @classmethod
    def translate_batch(cls, articles, max_workers: int = None) -> dict:
        """
        Translate a list/queryset of articles in parallel.
        Uses ThreadPoolExecutor with up to MAX_WORKERS threads.
        Returns {'translated': N, 'skipped': M, 'failed': K}
        """
        workers = max_workers or cls.MAX_WORKERS
        translated = skipped = failed = 0

        # Convert queryset to list so we can measure and iterate multiple times
        article_list = list(articles)
        if not article_list:
            return {'translated': 0, 'skipped': 0, 'failed': 0}

        logger.info(f"[TranslationService] Starting parallel translation of {len(article_list)} articles with {workers} workers")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_article = {
                executor.submit(cls.translate_article, art): art
                for art in article_list
            }
            for future in as_completed(future_to_article):
                art = future_to_article[future]
                try:
                    result = future.result()
                    if result:
                        translated += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error(f"Thread error for article {art.pk}: {e}")
                    failed += 1

        logger.info(f"[TranslationService] Done: {translated} translated, {skipped} skipped (already English), {failed} failed")
        return {'translated': translated, 'skipped': skipped, 'failed': failed}

    @classmethod
    def translate_pending(cls, limit: int = 200) -> dict:
        """
        Fetch all untranslated articles with non-English titles and translate them.
        Called by the Celery task every minute.
        limit: max articles to process per run (prevents overloading).
        """
        from news.models import NewsArticle

        # Grab untranslated articles — filter by Unicode non-ASCII title chars
        # We can't filter in SQL easily, so fetch a batch and filter in Python
        candidates = (
            NewsArticle.objects
            .filter(is_translated=False)
            .exclude(title='')
            .order_by('-published_at')[:limit * 3]  # fetch 3x, filter down to `limit`
        )

        # Fast-filter: only non-English titles
        non_english = [
            a for a in candidates
            if is_non_english(a.title or '') or is_non_english(a.description or '')
        ][:limit]

        if not non_english:
            logger.info("[TranslationService] No pending non-English articles.")
            return {'translated': 0, 'skipped': 0, 'failed': 0}

        logger.info(f"[TranslationService] Found {len(non_english)} non-English articles to translate")
        return cls.translate_batch(non_english)

    @classmethod
    def translate_article_inline(cls, title: str, description: str, lang: str = 'auto') -> dict:
        """
        Translate title + description strings directly (no DB write).
        Used during feed fetch to translate before saving to DB.
        Returns {'title': ..., 'description': ..., 'lang': ..., 'translated': bool}
        """
        detected = detect_language_fast(title)
        if detected in ('en', '') and not is_non_english(description or ''):
            return {'title': title, 'description': description, 'lang': 'en', 'translated': False}

        effective_lang = detected if detected not in ('en', '') else 'auto'
        try:
            new_title = cls._translate_text(title, source_lang=effective_lang)
            new_desc = cls._translate_text((description or '')[:5000], source_lang=effective_lang) if description else description
            return {
                'title': new_title or title,
                'description': new_desc or description,
                'lang': detected,
                'translated': bool(new_title and new_title != title),
            }
        except Exception as e:
            logger.warning(f"Inline translation failed: {e}")
            return {'title': title, 'description': description, 'lang': detected, 'translated': False}
