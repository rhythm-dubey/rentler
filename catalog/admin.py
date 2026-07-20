from django.contrib import admin

from .models import Category, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('sku', 'is_sold', 'notes')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active', 'sort_order')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('sort_order', 'name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'sku',
        'owner',
        'category',
        'is_active',
        'is_admin_approved',
        'is_featured',
        'daily_price',
        'created_at',
    )
    list_filter = ('is_active', 'is_admin_approved', 'is_featured', 'category')
    search_fields = ('name', 'sku', 'owner__email', 'owner__name', 'city')
    readonly_fields = ('slug', 'sku', 'created_at', 'updated_at', 'deleted_at')
    inlines = [ProductVariantInline]
    actions = ['approve_products', 'feature_products', 'unfeature_products']

    def save_model(self, request, obj, form, change):
        obj.save(skip_approval_reset=True)

    @admin.action(description='Approve selected products')
    def approve_products(self, request, queryset):
        for product in queryset:
            product.is_admin_approved = True
            product.save(skip_approval_reset=True)

    @admin.action(description='Mark as featured')
    def feature_products(self, request, queryset):
        for product in queryset:
            product.is_featured = True
            product.save(skip_approval_reset=True)

    @admin.action(description='Remove featured')
    def unfeature_products(self, request, queryset):
        for product in queryset:
            product.is_featured = False
            product.save(skip_approval_reset=True)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'is_sold')
    list_filter = ('is_sold',)
    search_fields = ('sku', 'product__name')
