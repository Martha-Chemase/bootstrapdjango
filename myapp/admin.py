from django.contrib import admin

from myapp.models import ContactMessage, Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price_kes", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    list_editable = ("price_kes", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "category", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "unit_price_kes", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_kes", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "email", "full_name", "paypal_order_id")
    readonly_fields = ("paypal_order_id", "subtotal_kes", "delivery_kes", "total_kes", "paypal_total_usd")
    inlines = [OrderItemInline]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "created_at")
    search_fields = ("subject", "name", "email", "message")
    readonly_fields = ("name", "email", "subject", "message", "created_at")
