from django.contrib import admin
from .models import Product, TrackedItem

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'current_price', 'url_link')
    search_fields = ('name',)

    def url_link(self, obj):
        return f'<a href="{obj.url}" target="_blank">View on Site</a>'
    url_link.allow_tags = True
    url_link.short_description = "Live Link"
    # Add this inside your ProductAdmin class in admin.py
    actions = ['force_update']

    def force_update(self, request, queryset):
        from .tasks import update_product_price
        for product in queryset:
            update_product_price.delay(product.id)
        self.message_user(request, "Update tasks have been sent to the worker.")
    force_update.short_description = "Force Price Update Now"

@admin.register(TrackedItem)
class TrackedItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'target_price')
    list_filter = ('user',)