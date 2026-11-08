from django.conf import settings
from django.db import models


class Product(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=80)
    description = models.TextField()
    image = models.CharField(max_length=255)
    price_kes = models.DecimalField(max_digits=10, decimal_places=2)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, default="Nairobi")
    county = models.CharField(max_length=100, default="Nairobi")
    subtotal_kes = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_kes = models.DecimalField(max_digits=10, decimal_places=2)
    total_kes = models.DecimalField(max_digits=10, decimal_places=2)
    paypal_kes_per_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default="130.0000",
    )
    paypal_total_usd = models.DecimalField(max_digits=10, decimal_places=2)
    paypal_order_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} — {self.user}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=120)
    unit_price_kes = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.name}"
