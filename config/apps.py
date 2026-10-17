from django.contrib.admin.apps import AdminConfig


class PetDonationAdminConfig(AdminConfig):
    default_site = "config.admin.PetDonationAdminSite"
