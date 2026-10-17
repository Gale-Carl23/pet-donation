from django.contrib.auth.models import AbstractUser
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
