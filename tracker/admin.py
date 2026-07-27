from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Product, TrackedItem

# --- 1. Custom Admin Index Wrap for Analytics Dashboard & Charts ---
original_index = admin.site.index

def custom_admin_index(request, extra_context=None):
    extra_context = extra_context or {}
    
    from django.contrib.auth.models import User
    
    # Calculate key metrics
    products_count = Product.objects.count()
    items_count = TrackedItem.objects.count()
    users_count = User.objects.count()
    
    target_met_count = sum(
        1 for item in TrackedItem.objects.all()
        if item.product.current_price and item.product.current_price <= item.target_price
    )
    
    # Top 5 most tracked products
    top_products = Product.objects.annotate(
        num_trackers=Count('trackeditem')
    ).order_by('-num_trackers')[:5]
    
    # Update context
    extra_context.update({
        'products_count': products_count,
        'items_count': items_count,
        'users_count': users_count,
        'target_met_count': target_met_count,
        'top_products': top_products,
        'show_analytics': True,
    })
    
    return original_index(request, extra_context)

admin.site.index = custom_admin_index


# --- 2. Upgraded Product Admin ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'current_price', 'url_link', 'total_trackers', 'updated_at')
    search_fields = ('name', 'url')
    list_filter = ('updated_at',)
    actions = ['force_update']

    def url_link(self, obj):
        return format_html('<a href="{}" target="_blank" style="font-weight: 600; color: #6366f1;">Open Store ↗</a>', obj.url)
    url_link.short_description = "Store Link"

    def total_trackers(self, obj):
        return obj.trackeditem_set.count()
    total_trackers.short_description = "Active Trackers"

    def force_update(self, request, queryset):
        from .tasks import update_product_price
        for product in queryset:
            update_product_price.delay(product.id)
        self.message_user(request, f"⚡ Triggered price updates for {queryset.count()} product(s).")
    force_update.short_description = "⚡ Force Price Update Now"


# --- 3. Upgraded TrackedItem Admin ---
@admin.register(TrackedItem)
class TrackedItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product_name_link', 'target_price', 'current_price_display', 'target_met', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'product__name')

    def product_name_link(self, obj):
        return obj.product.name
    product_name_link.short_description = "Product Name"

    def current_price_display(self, obj):
        return f"₹{obj.product.current_price}" if obj.product.current_price else "Fetching..."
    current_price_display.short_description = "Current Price"

    def target_met(self, obj):
        if obj.product.current_price and obj.product.current_price <= obj.target_price:
            return True
        return False
    target_met.boolean = True
    target_met.short_description = "Target Met?"