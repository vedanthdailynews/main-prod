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
            translated = GoogleTranslator(source=source_lang, target='en').translate(text)
            return translated if translated else text
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text

    @classmethod
    def _translate_long_text(cls, text: str, source_lang: str = 'auto') -> str:
        """
        Translate long content by splitting into ~4500-char chunks on paragraph or
        sentence boundaries, translating each chunk in parallel, then rejoining.
        """
        CHUNK = 4500
        if not text or len(text) <= CHUNK:
            return cls._translate_text(text, source_lang=source_lang)

        # Split into paragraphs first
        paragraphs = text.split('\n')
        chunks, current = [], ''
        for p in paragraphs:
            if len(current) + len(p) + 1 > CHUNK:
                if current:
                    chunks.append(current.strip())
                current = p
            else:
                current = (current + '\n' + p) if current else p
        if current:
            chunks.append(current.strip())

        if not chunks:
            return text

        # Translate all chunks in parallel
        translated_chunks = [''] * len(chunks)
        with ThreadPoolExecutor(max_workers=min(len(chunks), 10)) as ex:
            futures = {ex.submit(cls._translate_text, c, source_lang): i for i, c in enumerate(chunks)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    translated_chunks[idx] = future.result()
                except Exception:
                    translated_chunks[idx] = chunks[idx]  # fallback to original

        return '\n\n'.join(translated_chunks)

    @classmethod
    def translate_article(cls, article) -> bool:
        """
        Translate a single NewsArticle's title + description + content to English.
        Saves to DB and marks is_translated=True.
        Returns True if any translation happened, False if already English or failed.
        """
        title = article.title or ''
        description = article.description or ''
        content = article.content or ''

        # Determine if anything needs translating
        lang = detect_language_fast(title)
        if lang in ('en', ''):
            lang = detect_language_fast(description) or detect_language_fast(content[:200])
        content_lang = detect_language_fast(content[:200]) if content else 'en'

        title_needs = is_non_english(title)
        desc_needs = is_non_english(description)
        content_needs = is_non_english(content[:200])

        # Skip entirely if already translated AND content is also fine
        if article.is_translated and not content_needs:
            return False

        # If already translated, we only need to fix the content field
        if article.is_translated and content_needs:
            try:
                effective_lang = content_lang if content_lang not in ('en', '') else 'auto'
                new_content = cls._translate_long_text(content, source_lang=effective_lang)
                article.content = new_content
                article.save(update_fields=['content'])
                logger.info(f"  → Content translated for already-translated article id={article.pk}")
                return True
            except Exception as e:
                logger.error(f"Content translation failed for {article.pk}: {e}")
                return False

        if not title_needs and not desc_needs and not content_needs:
            return False

        effective_lang = lang if lang not in ('en', '') else 'auto'
        logger.info(f"Translating [{effective_lang}] article id={article.pk}: {title[:50]}…")

        try:
            update_fields = []

            if title_needs:
                new_title = cls._translate_text(title, source_lang=effective_lang)
                if new_title and new_title != title:
                    article.original_title = title
                    article.title = new_title
                    update_fields += ['title', 'original_title']

            if desc_needs:
                new_desc = cls._translate_text(description[:5000], source_lang=effective_lang)
                if new_desc:
                    article.original_description = description or None
                    article.description = new_desc
                    update_fields += ['description', 'original_description']

            if content_needs and content:
                c_lang = content_lang if content_lang not in ('en', '') else effective_lang
                new_content = cls._translate_long_text(content, source_lang=c_lang)
                if new_content:
                    article.content = new_content
                    update_fields.append('content')

            if not update_fields:
                return False

            article.original_language = effective_lang
            article.is_translated = True
            update_fields += ['original_language', 'is_translated']

            article.save(update_fields=update_fields)
            logger.info(f"  → Done (fields: {update_fields})")
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
        Fetch all articles with non-English text (title, description, OR content)
        and translate them. Called by the Celery task every minute.
        """
        from news.models import NewsArticle

        # Pass 1: untranslated articles with non-English title/description
        candidates = (
            NewsArticle.objects
            .filter(is_translated=False)
            .exclude(title='')
            .order_by('-published_at')[:limit * 3]
        )
        non_english = [
            a for a in candidates
            if is_non_english(a.title or '') or is_non_english(a.description or '')
        ][:limit]

        # Pass 2: already-translated articles whose content is still non-English
        content_candidates = (
            NewsArticle.objects
            .filter(is_translated=True)
            .exclude(content='')
            .exclude(content__isnull=True)
            .order_by('-published_at')[:limit * 2]
        )
        content_non_english = [
            a for a in content_candidates
            if is_non_english((a.content or '')[:200])
        ][:limit]

        to_process = list({a.pk: a for a in non_english + content_non_english}.values())

        if not to_process:
            logger.info("[TranslationService] No pending non-English articles.")
            return {'translated': 0, 'skipped': 0, 'failed': 0}

        logger.info(f"[TranslationService] Found {len(to_process)} articles to translate (title/desc/content)")
        return cls.translate_batch(to_process)

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
