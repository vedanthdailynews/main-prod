"""
Management command to fix articles that have no image_url.
Assigns a unique per-article Picsum placeholder based on the article title.
Run with: python manage.py fix_empty_images
"""
import hashlib
from django.core.management.base import BaseCommand
from news.models import NewsArticle


def title_to_picsum(title: str, width: int = 800, height: int = 450) -> str:
    seed = hashlib.md5(title.encode()).hexdigest()[:16]
    return f"https://picsum.photos/seed/{seed}/{width}/{height}"


class Command(BaseCommand):
    help = 'Backfill missing image_url fields with unique Picsum placeholders'

    def handle(self, *args, **options):
        qs = NewsArticle.objects.filter(image_url__isnull=True) | \
             NewsArticle.objects.filter(image_url='')
        # Django ORM union via Q
        from django.db.models import Q
        qs = NewsArticle.objects.filter(Q(image_url__isnull=True) | Q(image_url=''))
        count = qs.count()
        self.stdout.write(f'Found {count} articles with no image. Backfilling...')

        updated = 0
        for article in qs.iterator():
            article.image_url = title_to_picsum(article.title)
            article.save(update_fields=['image_url'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Done. Updated {updated} articles.'))
