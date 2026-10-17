from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm

from .forms import RegistrationForm
from .models import Donation, User


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AdminUserChangeForm
    add_form = RegistrationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "first_name", "last_name", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("id", "price", "payment_method", "donator")
    list_filter = ("payment_method",)
    search_fields = ("donator__email", "donator__first_name", "donator__last_name")
    list_select_related = ("donator",)
    ordering = ("-id",)
    fields = ("donator", "price", "payment_method", "file")
