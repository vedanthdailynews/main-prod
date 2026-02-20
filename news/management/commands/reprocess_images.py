"""
Management command to reprocess images for existing articles.
For articles with no image or a generic Picsum placeholder,
re-runs the contextual entity lookup + LoremFlickr topic match
so they get a relevant image instead of a random one.

Run with: python manage.py reprocess_images
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from news.models import NewsArticle
from news.image_service import get_contextual_image, get_topic_image
from news.services import GoogleNewsService


class Command(BaseCommand):
    help = 'Reprocess images for articles with missing or Picsum placeholder images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reprocess ALL articles (default: only blank/Picsum ones)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Max number of articles to process (default: 500)',
        )

    def handle(self, *args, **options):
        if options['all']:
            qs = NewsArticle.objects.all()
        else:
            qs = NewsArticle.objects.filter(
                Q(image_url__isnull=True) |
                Q(image_url='') |
                Q(image_url__contains='picsum.photos')
            )

        qs = qs.order_by('-published_at')[:options['limit']]
        total = qs.count()
        self.stdout.write(f'Reprocessing images for {total} articles...')

        updated = 0
        already_good = 0

        for article in qs.iterator(chunk_size=50):
            # Step 1: entity map (Wikipedia)
            img = get_contextual_image(article.title, article.description or '')

            # Step 2: LoremFlickr topic match
            if not img:
                img = get_topic_image(article.title)

            # Step 3: Picsum unique fallback
            if not img:
                import hashlib
                seed = hashlib.md5(article.title.encode()).hexdigest()[:16]
                img = f'https://picsum.photos/seed/{seed}/800/450'

            if img and img != article.image_url:
                article.image_url = img
                article.save(update_fields=['image_url'])
                updated += 1
            else:
                already_good += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Updated: {updated} | Already had good image: {already_good}'
        ))
