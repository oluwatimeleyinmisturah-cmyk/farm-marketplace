from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string


# ═══════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════
class Profile(models.Model):
    ROLE_CHOICES = (("buyer", "Buyer"), ("farmer", "Farmer"))

    user      = models.OneToOneField(User, on_delete=models.CASCADE)
    role      = models.CharField(max_length=10, choices=ROLE_CHOICES, default="buyer")
    phone     = models.CharField(max_length=20, blank=True, null=True)
    image     = models.ImageField(upload_to="profile_images/", blank=True, null=True)
    bio       = models.TextField(blank=True, null=True)
    location  = models.CharField(max_length=200, blank=True, null=True)
    farm_name = models.CharField(max_length=200, blank=True, null=True)
    address   = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def get_display_name(self):
        if self.role == "farmer" and self.farm_name:
            return self.farm_name
        return self.user.get_full_name() or self.user.username

    def get_avatar_initials(self):
        name  = self.user.get_full_name() or self.user.username
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()


# ═══════════════════════════════════════════════
# PRODUCT
# ═══════════════════════════════════════════════
class Product(models.Model):
    CATEGORY_CHOICES = (
        ("grain&cereal",              "Grain & Cereal"),
        ("tuber",                     "Tuber"),
        ("vegetable",                 "Vegetable"),
        ("fruit",                     "Fruit"),
        ("livestock",                 "Livestock"),
        ("seafood",                   "Seafood"),
        ("dairy&egg",                 "Dairy & Egg"),
        ("farmsupplies&inputs",       "Farm Supplies & Inputs"),
        ("organic&specialtyproducts", "Organic & Specialty Products"),
        ("snacks&processedfoods",     "Snacks & Processed Foods"),
        ("farmservices&equipment",    "Farm Services & Equipment"),
        ("beverages",                 "Beverages"),
    )

    farmer      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    name        = models.CharField(max_length=200)
    category    = models.CharField(max_length=200, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, null=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    quantity    = models.IntegerField()
    location    = models.CharField(max_length=200)
    image       = models.ImageField(upload_to="product_images/", blank=True, null=True)
    is_new      = models.BooleanField(default=False)
    is_hot      = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ═══════════════════════════════════════════════
# ORDER
# ═══════════════════════════════════════════════
class Order(models.Model):
    STATUS_CHOICES = (
        ("pending",   "Pending"),
        ("sent_out",  "Active"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("rejected",  "Rejected"),
        ("cancelled", "Cancelled"),
    )

    PAYMENT_CHOICES = (
        ('unpaid',  'Unpaid'),
        ('paid',    'Paid'),
        ('failed',  'Failed'),
    )

    buyer           = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    full_name       = models.CharField(max_length=200)
    email           = models.EmailField()
    phone           = models.CharField(max_length=20)
    address         = models.TextField()
    city            = models.CharField(max_length=100)
    state           = models.CharField(max_length=100)
    notes           = models.TextField(blank=True, null=True)
    delivery_method = models.CharField(max_length=50, default="standard")

    subtotal      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax           = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total         = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Paystack
    paystack_ref   = models.CharField(max_length=100, blank=True, null=True, unique=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='unpaid')
    paid_at        = models.DateTimeField(blank=True, null=True)

    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} — {self.buyer.username}"

    def days_to_complete(self):
        if self.completed_at and self.created_at:
            return (self.completed_at.date() - self.created_at.date()).days
        return None

    def expected_delivery(self):
        days = 1 if self.delivery_method == "express" else 3
        return self.created_at.date() + timezone.timedelta(days=days)

    @property
    def order_number(self):
        return f"ORD-{self.id:05d}"

    @property
    def total_kobo(self):
        """Paystack expects amount in kobo (1 NGN = 100 kobo)."""
        return int(self.total * 100)


# ═══════════════════════════════════════════════
# ORDER ITEM
# ═══════════════════════════════════════════════
class OrderItem(models.Model):
    order         = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product       = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="order_items")
    product_name  = models.CharField(max_length=200)
    product_image = models.ImageField(upload_to="order_snapshots/", blank=True, null=True)
    unit_price    = models.DecimalField(max_digits=10, decimal_places=2)
    quantity      = models.IntegerField()
    total_price   = models.DecimalField(max_digits=12, decimal_places=2)
    farmer        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="received_order_items"
    )

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


# ═══════════════════════════════════════════════
# OTP  — signup email verification + password reset
# ═══════════════════════════════════════════════
class OTP(models.Model):
    PURPOSE_SIGNUP  = 'signup'
    PURPOSE_RESET   = 'reset'
    PURPOSE_CHOICES = (
        (PURPOSE_SIGNUP, 'Email Verification'),
        (PURPOSE_RESET,  'Password Reset'),
    )

    email      = models.EmailField()
    code       = models.CharField(max_length=6)
    purpose    = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} [{self.purpose}] — {self.code}"

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    @classmethod
    def generate_for(cls, email, purpose):
        """Expire old OTPs for this email/purpose then issue a fresh one."""
        cls.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)
        code = ''.join(random.choices(string.digits, k=6))
        return cls.objects.create(email=email, code=code, purpose=purpose)


# ═══════════════════════════════════════════════
# NOTIFICATION
# ═══════════════════════════════════════════════
class Notification(models.Model):
    ORDER  = 'order'
    UPDATE = 'update'
    ALERT  = 'alert'

    TYPE_CHOICES = (
        (ORDER,  'New Order'),
        (UPDATE, 'Order Update'),
        (ALERT,  'Alert'),
    )

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message    = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=ORDER)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'unread' if not self.is_read else 'read'
        return f"[{status}] {self.user.username}: {self.message[:60]}"

    
        
