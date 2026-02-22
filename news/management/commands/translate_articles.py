"""
Management command to translate non-English articles to English.
Uses ThreadPoolExecutor for maximum parallel throughput.

Usage:
    python manage.py translate_articles               # translate all pending (up to 500)
    python manage.py translate_articles --limit 1000  # translate up to 1000
    python manage.py translate_articles --workers 30  # use 30 parallel threads
    python manage.py translate_articles --all         # translate everything (no limit)
"""
from django.core.management.base import BaseCommand
from news.translation_service import TranslationService, is_non_english
from news.models import NewsArticle


class Command(BaseCommand):
    help = 'Translate non-English (Hindi/Tamil/Telugu etc.) articles to English in parallel'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500, help='Max articles to translate (default: 500)')
        parser.add_argument('--workers', type=int, default=20, help='Parallel thread workers (default: 20)')
        parser.add_argument('--all', action='store_true', help='Translate all pending without limit')
        parser.add_argument('--stats', action='store_true', help='Only show stats, do not translate')

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('=== Parallel Article Translation ==='))

        # Stats mode
        total_non_eng = sum(
            1 for a in NewsArticle.objects.filter(is_translated=False).only('title', 'description')
            if is_non_english(a.title or '') or is_non_english(a.description or '')
        )
        already_translated = NewsArticle.objects.filter(is_translated=True).count()
        self.stdout.write(f'Non-English (untranslated): {total_non_eng}')
        self.stdout.write(f'Already translated:          {already_translated}')

        if options['stats']:
            return

        limit = None if options['all'] else options['limit']
        workers = options['workers']

        self.stdout.write(f'Translating up to {limit or "ALL"} articles with {workers} parallel workers...')

        if limit:
            results = TranslationService.translate_pending(limit=limit)
        else:
            # Translate everything with no limit
            candidates = list(
                NewsArticle.objects.filter(is_translated=False).order_by('-published_at')
            )
            non_english = [
                a for a in candidates
                if is_non_english(a.title or '') or is_non_english(a.description or '')
            ]
            self.stdout.write(f'Found {len(non_english)} non-English articles total')
            results = TranslationService.translate_batch(non_english, max_workers=workers)

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Translated: {results['translated']} | "
            f"Skipped (English): {results['skipped']} | "
            f"Failed: {results['failed']}"
        ))
