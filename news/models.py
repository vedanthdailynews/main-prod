"""
Django models for news articles.
"""
from django.db import models
from django.utils import timezone


class Continent(models.TextChoices):
    """Continent choices for news categorization."""
    AFRICA = 'AF', 'Africa'
    ASIA = 'AS', 'Asia'
    EUROPE = 'EU', 'Europe'
    NORTH_AMERICA = 'NA', 'North America'
    SOUTH_AMERICA = 'SA', 'South America'
    OCEANIA = 'OC', 'Oceania'
    GLOBAL = 'GL', 'Global'


class Category(models.TextChoices):
    """News category choices."""
    WORLD = 'WORLD', 'World'
    BUSINESS = 'BUSINESS', 'Business'
    TECHNOLOGY = 'TECHNOLOGY', 'Technology'
    ENTERTAINMENT = 'ENTERTAINMENT', 'Entertainment'
    SPORTS = 'SPORTS', 'Sports'
    SCIENCE = 'SCIENCE', 'Science'
    HEALTH = 'HEALTH', 'Health'
    BUDGET = 'BUDGET', 'Budget 2026'


class IndianState(models.TextChoices):
    """Indian states for regional news."""
    ANDHRA_PRADESH = 'AP', 'Andhra Pradesh'
    ARUNACHAL_PRADESH = 'AR', 'Arunachal Pradesh'
    ASSAM = 'AS', 'Assam'
    BIHAR = 'BR', 'Bihar'
    CHHATTISGARH = 'CG', 'Chhattisgarh'
    DELHI = 'DL', 'Delhi'
    GOA = 'GA', 'Goa'
    GUJARAT = 'GJ', 'Gujarat'
    HARYANA = 'HR', 'Haryana'
    HIMACHAL_PRADESH = 'HP', 'Himachal Pradesh'
    JHARKHAND = 'JH', 'Jharkhand'
    KARNATAKA = 'KA', 'Karnataka'
    KERALA = 'KL', 'Kerala'
    MADHYA_PRADESH = 'MP', 'Madhya Pradesh'
    MAHARASHTRA = 'MH', 'Maharashtra'
    MANIPUR = 'MN', 'Manipur'
    MEGHALAYA = 'ML', 'Meghalaya'
    MIZORAM = 'MZ', 'Mizoram'
    NAGALAND = 'NL', 'Nagaland'
    ODISHA = 'OD', 'Odisha'
    PUNJAB = 'PB', 'Punjab'
    RAJASTHAN = 'RJ', 'Rajasthan'
    SIKKIM = 'SK', 'Sikkim'
    TAMIL_NADU = 'TN', 'Tamil Nadu'
    TELANGANA = 'TS', 'Telangana'
    TRIPURA = 'TR', 'Tripura'
    UTTAR_PRADESH = 'UP', 'Uttar Pradesh'
    UTTARAKHAND = 'UK', 'Uttarakhand'
    WEST_BENGAL = 'WB', 'West Bengal'
    JAMMU_KASHMIR = 'JK', 'Jammu & Kashmir'
    LADAKH = 'LA', 'Ladakh'
    PUDUCHERRY = 'PY', 'Puducherry'
    CHANDIGARH = 'CH', 'Chandigarh'


class NewsArticle(models.Model):
    """Model representing a news article."""
    
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    url = models.URLField(unique=True, max_length=1000)
    source = models.CharField(max_length=200)
    author = models.CharField(max_length=200, blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    
    # Categorization
    continent = models.CharField(
        max_length=2,
        choices=Continent.choices,
        default=Continent.GLOBAL
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.WORLD
    )
    
    # Indian regional news
    indian_state = models.CharField(
        max_length=2,
        choices=IndianState.choices,
        blank=True,
        null=True,
        help_text="Indian state for regional news"
    )
    district = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="District name for local news"
    )
    is_indian_news = models.BooleanField(
        default=False,
        help_text="Flag for India-focused news"
    )
    
    # AI-generated fields
    summary = models.TextField(blank=True, null=True, help_text="AI-generated summary")
    sentiment = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="positive, negative, or neutral"
    )
    tags = models.JSONField(default=list, blank=True, help_text="AI-generated tags")
    credibility_score = models.FloatField(
        default=0.0,
        help_text="AI credibility score (0-100). 80+: Verified, 50-80: Unverified, <50: Disputed"
    )
    
    # ePaper fields
    epaper_page = models.IntegerField(
        default=1,
        help_text="Page number in ePaper edition (1-based)"
    )
    epaper_section = models.CharField(
        max_length=50,
        default='FRONT_PAGE',
        help_text="ePaper section: FRONT_PAGE, CITY, NATION, WORLD, BUSINESS, SPORTS, ENTERTAINMENT"
    )
    epaper_position = models.IntegerField(
        default=0,
        help_text="Position within page (0=top, higher=lower)"
    )
    epaper_size = models.CharField(
        max_length=20,
        default='MEDIUM',
        help_text="Article size in ePaper: LARGE, MEDIUM, SMALL"
    )
    
    # Metadata
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['continent', '-published_at']),
            models.Index(fields=['category', '-published_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def increment_views(self):
        """Increment the view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class NewsSource(models.Model):
    """Model for tracking news sources."""
    
    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(max_length=1000)
    continent = models.CharField(
        max_length=2,
        choices=Continent.choices,
        default=Continent.GLOBAL
    )
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    fetch_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def update_fetch_status(self, success=True):
        """Update fetch statistics."""
        self.last_fetched = timezone.now()
        self.fetch_count += 1
        if not success:
            self.error_count += 1
        self.save(update_fields=['last_fetched', 'fetch_count', 'error_count'])


class DailyPaper(models.Model):
    """Model for daily newspaper PDF uploads."""
    
    date = models.DateField(unique=True, help_text="Publication date of the paper")
    pdf_file = models.FileField(
        upload_to='daily_papers/%Y/%m/',
        help_text="Upload the daily newspaper PDF file"
    )
    edition = models.CharField(
        max_length=100,
        default='Delhi Edition',
        help_text="Edition name (e.g., Delhi Edition, Mumbai Edition)"
    )
    total_pages = models.IntegerField(
        default=1,
        help_text="Total number of pages in the paper"
    )
    file_size = models.CharField(
        max_length=50,
        blank=True,
        help_text="File size (auto-calculated)"
    )
    is_published = models.BooleanField(
        default=True,
        help_text="Make this paper visible to users"
    )
    pdf_content = models.JSONField(
        default=list,
        blank=True,
        help_text="Extracted articles from PDF (auto-generated)"
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Paper'
        verbose_name_plural = 'Daily Papers'
    
    def __str__(self):
        return f"{self.edition} - {self.date.strftime('%d %B %Y')}"
    
    def save(self, *args, **kwargs):
        """Calculate file size and extract PDF content on save."""
        if self.pdf_file:
            # Calculate file size
            size = self.pdf_file.size
            if size < 1024:
                self.file_size = f"{size} bytes"
            elif size < 1024 * 1024:
                self.file_size = f"{size / 1024:.1f} KB"
            else:
                self.file_size = f"{size / (1024 * 1024):.1f} MB"
            
            # Extract PDF content
            try:
                from news.pdf_parser import PDFParserService
                
                # Get page count
                if not self.total_pages or self.total_pages == 1:
                    self.total_pages = PDFParserService.get_page_count(self.pdf_file)
                
                # Extract articles from PDF
                if not self.pdf_content or len(self.pdf_content) == 0:
                    self.pdf_content = PDFParserService.parse_articles_from_pdf(self.pdf_file)
            except Exception as e:
                import logging
                logging.error(f"Error processing PDF: {e}")
        
        super().save(*args, **kwargs)
