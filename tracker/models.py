from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=255)
    # unique=True prevents the same URL from being added multiple times by different users
    url = models.URLField(unique=True) 
    current_price = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)  # Automatically updates when you save

    def __str__(self):
        return self.name

class TrackedItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    target_price = models.FloatField()
    # This field prevents the email spamming issue
    last_notified_price = models.FloatField(null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"