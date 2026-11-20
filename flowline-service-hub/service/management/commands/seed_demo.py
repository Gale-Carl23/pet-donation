"""Load sample customers, systems, staff and jobs for a demo or local testing.

Refuses to run unless DEBUG is on or --force is given, so it can't add
demo accounts to a live system by accident. Passwords are random and
printed once.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from service.models import CompanySettings, Customer, Job, WaterSystem, today

User = get_user_model()


class Command(BaseCommand):
    help = "Load sample data for a demo (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=true (or pass --force on a demo server).")
        if Customer.objects.exists():
            raise CommandError("The database already has customers; seed_demo only fills an empty database.")

        now = today()
        cfg = CompanySettings.load()
        cfg.company_name = cfg.company_name or settings.COMPANY_NAME
        cfg.save()

        accounts = []

        def staff(email, first, last, role, **extra):
            password = secrets.token_urlsafe(12)
            user = User.objects.create_user(email=email, password=password, first_name=first, last_name=last,
                                            role=role, must_change_password=True, **extra)
            accounts.append((email, password, user.get_role_display()))
            return user

        staff("admin@example.com", "Ana", "Admin", User.Role.ADMIN, is_staff=True, is_superuser=True)
        staff("office@example.com", "Olive", "Office", User.Role.OFFICE)
        rafael = staff("rafael@example.com", "Rafael", "Tech", User.Role.TECHNICIAN)
        joan = staff("joan@example.com", "Joan", "Tech", User.Role.TECHNICIAN)

        def customer(name, ctype, contact, area):
            return Customer.objects.create(name=f"{name} (sample)", customer_type=ctype, contact_name=contact,
                                           phone="0917 000 0000", area=area, address="Sample address")

        def system(cust, stype, label, model, serial, ages):
            s = WaterSystem.objects.create(customer=cust, system_type=stype, label=label, model=model, serial=serial,
                                           install_date=now - timedelta(days=800))
            s.add_preset_components()
            for comp, days_ago in zip(s.components.all(), ages):
                comp.last_changed = now - timedelta(days=days_ago)
                comp.save()
            return s

        santos = customer("Santos Residence", Customer.Type.RESIDENTIAL, "Maria Santos", "Alabang, Muntinlupa")
        aqua = customer("AquaPure Refilling", Customer.Type.REFILLING, "Ben Cruz", "Tunasan, Muntinlupa")
        kusina = customer("Kusina Grill", Customer.Type.FOOD, "Liza Reyes", "BF Homes, Parañaque")
        tower = customer("Southpoint Tower", Customer.Type.COMMERCIAL, "Engr. Dela Paz", "Filinvest, Alabang")

        system(santos, "ro", "Kitchen", "5-stage RO 75 GPD", "RO75-0001", [102, 179, 179, 544])
        s_aqua = system(aqua, "refilling", "Main line", "RO 2,000 GPD skid", "RS2K-0002", [26, 26, 36, 476, 264])
        s_kusina = system(kusina, "softener", "Dishwashing line", "Softener 1054", "WS-0003", [8, 292])
        s_tower = system(tower, "multimedia", "Roof deck", "MMF 1665 + ACF 1665", "MMF-0004", [23, 629])

        j = Job.objects.create(customer=aqua, system=s_aqua, technician=rafael, scheduled_date=now,
                               scheduled_time="09:30", instructions="Bring 2 sample bottles for the lab.")
        j.build_tasks(list(s_aqua.components.all())[:3])
        j = Job.objects.create(customer=tower, system=s_tower, technician=joan, scheduled_date=now + timedelta(days=3),
                               scheduled_time="14:00", instructions="Coordinate with building admin for roof access.")
        j.build_tasks(list(s_tower.components.all())[:1])
        j = Job.objects.create(customer=kusina, system=s_kusina, technician=joan, scheduled_date=now - timedelta(days=8),
                               scheduled_time="10:00")
        j.build_tasks(list(s_kusina.components.all())[:1])

        self.stdout.write(self.style.SUCCESS("Sample data loaded. Demo sign-ins (each must set a new password):"))
        for email, password, role in accounts:
            self.stdout.write(f"  {role:<20} {email:<24} {password}")
