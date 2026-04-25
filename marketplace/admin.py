from django.contrib import admin
from .models import Profile, Product, Order, OrderItem, Notification


# ── Profile ──────────────────────────────────────────────
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'role', 'phone', 'location', 'farm_name')
    list_filter   = ('role',)
    search_fields = ('user__username', 'user__email', 'farm_name', 'location')
    ordering      = ('user__username',)


# ── Product ───────────────────────────────────────────────
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ('name', 'farmer', 'category', 'price', 'quantity', 'is_new', 'is_hot', 'created_at')
    list_filter   = ('category', 'is_new', 'is_hot', 'created_at')
    search_fields = ('name', 'farmer__username', 'location')
    list_editable = ('price', 'quantity', 'is_new', 'is_hot')  # 🔥 added more control
    ordering      = ('-created_at',)


# ── Order Item inline ─────────────────────────────────────
class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ('product_name', 'quantity', 'unit_price', 'total_price', 'farmer')
    readonly_fields = ('product_name', 'unit_price', 'total_price', 'farmer')
    can_delete = False  # 🔥 prevents accidental deletion


# ── Order ─────────────────────────────────────────────────
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ('order_number_display', 'buyer', 'full_name', 'payment_status', 'status', 'total', 'created_at')
    list_filter   = ('status', 'payment_status', 'delivery_method', 'state', 'created_at')
    search_fields = ('buyer__username', 'full_name', 'email', 'phone', 'paystack_ref')
    readonly_fields = ('order_number_display', 'created_at', 'updated_at', 'delivered_at', 'completed_at', 'paid_at')
    inlines       = [OrderItemInline]
    ordering      = ('-created_at',)

    fieldsets = (
        ('Customer Info', {
            'fields': ('buyer', 'full_name', 'email', 'phone')
        }),
        ('Delivery Info', {
            'fields': ('address', 'city', 'state', 'delivery_method', 'notes')
        }),
        ('Payment Info', {
            'fields': ('subtotal', 'tax', 'shipping_cost', 'total', 'paystack_ref', 'payment_status', 'paid_at')
        }),
        ('Order Status', {
            'fields': ('status', 'delivered_at', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    # clean display for order number
    def order_number_display(self, obj):
        return obj.order_number
    order_number_display.short_description = 'Order ID'

    # ── Admin Actions ──
    actions = ['mark_sent_out', 'mark_delivered', 'mark_completed', 'mark_rejected']

    def mark_sent_out(self, request, queryset):
        queryset.update(status='sent_out')
    mark_sent_out.short_description = 'Mark selected orders as Active (sent out)'

    def mark_delivered(self, request, queryset):
        queryset.update(status='delivered')
    mark_delivered.short_description = 'Mark selected orders as Delivered'

    def mark_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_completed.short_description = 'Mark selected orders as Completed'

    def mark_rejected(self, request, queryset):
        queryset.update(status='rejected')
    mark_rejected.short_description = 'Mark selected orders as Rejected'


# ── Notification ──────────────────────────────────────────
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('user', 'notif_type', 'is_read', 'short_message', 'created_at')
    list_filter   = ('notif_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message')
    list_editable = ('is_read',)
    ordering      = ('-created_at',)

    def short_message(self, obj):
        return obj.message[:70] + ('...' if len(obj.message) > 70 else '')
    short_message.short_description = 'Message'