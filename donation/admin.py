from django.contrib import admin
from .models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("id", "price", "payment_method", "donator")
    list_filter = ("payment_method",)
    search_fields = ("donator__email", "donator__first_name", "donator__last_name")
    list_select_related = ("donator",)
    ordering = ("-id",)
    fields = ("donator", "price", "payment_method", "file")
