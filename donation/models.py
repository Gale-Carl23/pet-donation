from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class User(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Pet(models.Model):
    class Category(models.TextChoices):
        CAT = "cat", "Cat"
        DOG = "dog", "Dog"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNAVAILABLE = "unavailable", "Unavailable"

    name = models.CharField(max_length=120)
    age = models.PositiveSmallIntegerField(help_text="Age in years")
    background = models.TextField()
    google_map_url = models.URLField()
    pet_img = models.ImageField(upload_to="pets/")
    category = models.CharField(max_length=3, choices=Category.choices)
    status = models.CharField(
        max_length=11,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    def __str__(self):
        return self.name


class Donation(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        ONLINE = "online", "Online payment"

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    file = models.ImageField(upload_to="donation_proofs/")
    donator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="donations",
    )

    def __str__(self):
        return f"Donation {self.pk} from {self.donator}"
