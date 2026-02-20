"""
Management command to re-categorize all articles in the database using keyword matching.
Run with: python manage.py recategorize_articles

Useful after deploying the new classifier to fix existing uncategorized articles.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from news.models import NewsArticle
from news.services import GoogleNewsService


class Command(BaseCommand):
    help = 'Re-categorize all articles (or only uncategorized ones) using keyword matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Re-categorize ALL articles (default: only uncategorized ones)',
        )

    def handle(self, *args, **options):
        if options['all']:
            qs = NewsArticle.objects.all()
            self.stdout.write(f'Re-categorizing ALL {qs.count()} articles...')
        else:
            qs = NewsArticle.objects.filter(
                Q(category__isnull=True) | Q(category='') | Q(category='WORLD')
            )
            self.stdout.write(f'Found {qs.count()} uncategorized/world articles. Classifying...')

        updated = 0
        skipped = 0
        stats = {}

        for article in qs.iterator(chunk_size=200):
            category = GoogleNewsService.classify_category(
                article.title, article.description or ''
            )
            if category and category != article.category:
                article.category = category
                article.save(update_fields=['category'])
                updated += 1
                stats[category] = stats.get(category, 0) + 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Updated: {updated} | Skipped (no match or unchanged): {skipped}'
        ))
        if stats:
            self.stdout.write('Category breakdown:')
            for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
                self.stdout.write(f'  {cat}: {count}')
