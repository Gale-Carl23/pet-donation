from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("A superuser needs is_staff and is_superuser set.")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """A staff member who signs in with their email address."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        OFFICE = "office", "Office / dispatcher"
        TECHNICIAN = "technician", "Field technician"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TECHNICIAN)
    phone = models.CharField(max_length=30, blank=True)
    must_change_password = models.BooleanField(
        default=True, help_text="Ask the user to choose a new password at their next sign-in."
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name", "email"]

    def __str__(self):
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_technician(self):
        return self.role == self.Role.TECHNICIAN

    @property
    def is_office(self):
        """Office staff and administrators manage customers and the schedule."""
        return self.is_active and (self.role in (self.Role.OFFICE, self.Role.ADMIN) or self.is_superuser)

    @property
    def is_admin(self):
        return self.is_active and (self.role == self.Role.ADMIN or self.is_superuser)
