import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .managers import AllObjectsManager, SoftDeleteManager


class Category(models.Model):
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        if self.parent_id:
            return f'{self.parent.name} / {self.name}'
        return self.name

    def get_root(self):
        node = self
        while node.parent_id:
            node = node.parent
        return node

    def get_descendant_ids(self):
        """Return this category id plus all descendant ids (BFS)."""
        ids = [self.pk]
        queue = list(self.children.values_list('pk', flat=True))
        while queue:
            child_id = queue.pop(0)
            ids.append(child_id)
            queue.extend(
                Category.objects.filter(parent_id=child_id).values_list('pk', flat=True)
            )
        return ids


class Product(models.Model):
    """
    Rental listing.

    Orders will relate via orders.Order.product (hasMany from this side) once
    the orders app exists — do not add a belongsTo-style reverse mistake.
    """

    class MakePayment(models.TextChoices):
        ONE_TIME = 'one_time', 'One time'
        PER_PERIOD = 'per_period', 'Per period'

    class WhichTnc(models.TextChoices):
        DEFAULT = 'default', 'Default'
        OWN = 'own', 'Own'

    class CreatedBy(models.IntegerChoices):
        WEB = 0, 'Web'
        APP = 1, 'App'
        IMPORT = 2, 'Import'
        CSV_IMPORT = 3, 'CSV import'
        API_IMPORT = 4, 'API import'

    slug = models.SlugField(max_length=120, unique=True)
    sku = models.CharField(max_length=50, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    images = models.JSONField(default=list, blank=True)

    make_payment = models.CharField(
        max_length=20,
        choices=MakePayment.choices,
        default=MakePayment.PER_PERIOD,
    )
    hourly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    daily_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weekly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_weeks = models.PositiveIntegerField(null=True, blank=True)
    minimum_months = models.PositiveIntegerField(null=True, blank=True)

    has_multiple_items = models.BooleanField(default=False)
    total_items = models.PositiveIntegerField(default=1)
    total_sold = models.PositiveIntegerField(default=0)

    selling_points = models.JSONField(default=list, blank=True)

    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    post_code = models.CharField(max_length=20, blank=True)
    latitude = models.CharField(max_length=50, blank=True)
    longitude = models.CharField(max_length=50, blank=True)

    year = models.CharField(max_length=10, blank=True)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)

    owner_delivery_pickup = models.BooleanField(default=False)
    owner_delivery_pickup_km = models.CharField(max_length=50, blank=True)
    owner_delivery_pickup_cost = models.CharField(max_length=50, blank=True)
    owner_pickup = models.BooleanField(default=False)
    owner_postage = models.BooleanField(default=False)
    owner_postage_cost = models.CharField(max_length=50, blank=True)

    which_tnc = models.CharField(
        max_length=20,
        choices=WhichTnc.choices,
        default=WhichTnc.DEFAULT,
    )
    tnc = models.TextField(blank=True)

    available_on_days = models.JSONField(default=list, blank=True)
    starting_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    ending_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    not_availability = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_admin_approved = models.BooleanField(default=False)

    created_by = models.PositiveSmallIntegerField(
        choices=CreatedBy.choices,
        default=CreatedBy.WEB,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(
            update_fields=['deleted_at', 'is_active', 'updated_at'],
            skip_approval_reset=True,
        )

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def save(self, *args, skip_approval_reset=False, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'product'
            candidate = base
            n = 1
            while Product.all_objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                n += 1
                candidate = f'{base}-{n}'
            self.slug = candidate

        if not self.sku:
            self.sku = f'SKU{uuid.uuid4().hex[:10].upper()}'

        is_update = self.pk is not None
        if is_update and not skip_approval_reset:
            self.is_admin_approved = False

        super().save(*args, **kwargs)

    @property
    def min_price(self):
        for value in (
            self.hourly_price,
            self.daily_price,
            self.weekly_price,
            self.monthly_price,
        ):
            if value and value > 0:
                return value
        return Decimal('0')

    @property
    def is_available(self):
        return max(0, (self.total_items or 0) - (self.total_sold or 0))

    @property
    def image_urls(self):
        from django.conf import settings as django_settings

        urls = []
        media_url = django_settings.MEDIA_URL
        for path in self.images or []:
            if not path:
                continue
            if str(path).startswith(('http://', 'https://', '/')):
                urls.append(str(path))
            else:
                urls.append(f'{media_url}{path}')
        return urls

    @property
    def main_category(self):
        return self.category.get_root() if self.category_id else None


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    sku = models.CharField(max_length=80, blank=True)
    is_sold = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.sku or f'Variant {self.pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku:
            self.sku = f'SKU{uuid.uuid4().hex[:8].upper()}{self.pk}'
            super().save(update_fields=['sku'])

    @classmethod
    def create_variants(cls, product, count=1, variant_sku=None):
        created = []
        for i in range(count):
            sku = variant_sku if (variant_sku and count == 1) else None
            if variant_sku and count > 1:
                sku = f'{variant_sku}-{i + 1}'
            variant = cls(product=product, sku=sku or '')
            variant.save()
            created.append(variant)
        return created
