from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import AuditLog, Customer, Job, WaterSystem, today

User = get_user_model()
PASSWORD = "a-Long-unique-passphrase-91"


def make_user(email, role, **extra):
    return User.objects.create_user(email=email, password=PASSWORD, role=role, must_change_password=False, **extra)


class BaseCase(TestCase):
    def setUp(self):
        self.office = make_user("office@example.com", User.Role.OFFICE)
        self.tech = make_user("tech@example.com", User.Role.TECHNICIAN)
        self.other_tech = make_user("tech2@example.com", User.Role.TECHNICIAN)
        self.admin = make_user("admin@example.com", User.Role.ADMIN, is_staff=True)
        self.customer = Customer.objects.create(name="Santos Residence")
        self.system = WaterSystem.objects.create(customer=self.customer, system_type="ro",
                                                 install_date=today() - timedelta(days=200))
        self.system.add_preset_components()
        self.job = Job.objects.create(customer=self.customer, system=self.system, technician=self.tech,
                                      scheduled_date=today())
        self.job.build_tasks(list(self.system.components.all()[:2]))

    def login(self, user):
        self.client.force_login(user)


class AuthenticationTests(BaseCase):
    def test_every_page_requires_sign_in(self):
        for url in [reverse("dashboard"), reverse("schedule"), reverse("field"), reverse("customers"),
                    reverse("job_detail", args=[self.job.pk]), reverse("company_settings")]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("login"), response["Location"])

    def test_sign_in_with_email(self):
        response = self.client.post(reverse("login"), {"username": "office@example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(action="login", user=self.office).exists())

    def test_lockout_after_repeated_failures(self):
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "office@example.com", "password": "wrong"})
        response = self.client.post(reverse("login"), {"username": "office@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(AuditLog.objects.filter(action="login_failed").exists())

    def test_temporary_password_must_be_changed(self):
        self.office.must_change_password = True
        self.office.save()
        self.login(self.office)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("password_change"))
        new = "Another-strong-passphrase-42"
        self.client.post(reverse("password_change"),
                         {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
        self.office.refresh_from_db()
        self.assertFalse(self.office.must_change_password)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_weak_passwords_rejected(self):
        self.login(self.office)
        response = self.client.post(reverse("password_change"),
                                    {"old_password": PASSWORD, "new_password1": "password123",
                                     "new_password2": "password123"})
        self.assertEqual(response.status_code, 200)
        self.office.refresh_from_db()
        self.assertTrue(self.office.check_password(PASSWORD))

    def test_passwords_hashed_with_argon2(self):
        self.assertTrue(self.office.password.startswith("argon2"))

    def test_logout_requires_post(self):
        self.login(self.office)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)


class CsrfTests(BaseCase):
    def test_posts_without_csrf_token_are_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tech)
        response = client.post(reverse("job_save", args=[self.job.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 403)


class RoleTests(BaseCase):
    def test_technician_cannot_open_office_pages(self):
        self.login(self.tech)
        for url in [reverse("dashboard"), reverse("schedule"), reverse("customers"),
                    reverse("customer_detail", args=[self.customer.pk]), reverse("company_settings"),
                    reverse("audit_log")]:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_technician_only_sees_own_jobs(self):
        self.login(self.other_tech)
        self.assertEqual(self.client.get(reverse("job_detail", args=[self.job.pk])).status_code, 404)
        response = self.client.post(reverse("job_save", args=[self.job.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 404)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.SCHEDULED)

    def test_technician_cannot_reassign_or_cancel(self):
        self.login(self.tech)
        self.assertEqual(self.client.post(reverse("job_cancel", args=[self.job.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("job_assign", args=[self.job.pk]),
                                          {"scheduled_date": today()}).status_code, 403)

    def test_office_cannot_change_settings(self):
        self.login(self.office)
        self.assertEqual(self.client.get(reverse("company_settings")).status_code, 403)

    def test_admin_area_needs_staff_flag(self):
        from django.conf import settings
        self.login(self.office)
        response = self.client.get("/" + settings.ADMIN_URL)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(self.client.get("/admin/").status_code, 200)


class WorkflowTests(BaseCase):
    def test_dashboard_lists_due_components(self):
        self.login(self.office)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Santos Residence")
        self.assertContains(response, "Sediment filter")

    def test_book_visit_creates_tasks(self):
        self.login(self.office)
        comp = self.system.components.first()
        response = self.client.post(reverse("job_new", args=[self.system.pk]), {
            "job_type": "pms", "technician": self.tech.pk, "scheduled_date": today() + timedelta(days=2),
            "scheduled_time": "10:00", "components": [comp.pk],
        })
        job = Job.objects.latest("id")
        self.assertRedirects(response, reverse("job_detail", args=[job.pk]))
        self.assertEqual(job.tasks.filter(component=comp).count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="job_created").exists())

    def test_cannot_book_components_from_another_system(self):
        other = WaterSystem.objects.create(customer=self.customer, system_type="uv")
        other.add_preset_components()
        self.login(self.office)
        response = self.client.post(reverse("job_new", args=[self.system.pk]), {
            "job_type": "pms", "scheduled_date": today(), "components": [other.components.first().pk],
        })
        self.assertEqual(response.status_code, 200)  # form re-shown with an error
        self.assertEqual(Job.objects.count(), 1)

    def test_completing_job_resets_due_dates(self):
        self.login(self.tech)
        tasks = list(self.job.tasks.all())
        comp = tasks[0].component
        response = self.client.post(reverse("job_save", args=[self.job.pk]), {
            "action": "complete", "task": [tasks[0].pk], "ph": "7.2", "tds_raw": "300", "tds_product": "20",
            "received_by": "Maria Santos",
        })
        self.assertRedirects(response, reverse("job_detail", args=[self.job.pk]))
        self.job.refresh_from_db()
        comp.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.DONE)
        self.assertEqual(self.job.completed_by, self.tech)
        self.assertEqual(comp.last_changed, today())
        self.assertContains(self.client.get(reverse("job_detail", args=[self.job.pk])), "SERVICE REPORT")

    def test_cannot_complete_without_ticking_tasks(self):
        self.login(self.tech)
        self.client.post(reverse("job_save", args=[self.job.pk]), {"action": "complete"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.SCHEDULED)

    def test_completed_job_is_locked(self):
        self.job.status = Job.Status.DONE
        self.job.save()
        self.login(self.tech)
        self.client.post(reverse("job_save", args=[self.job.pk]), {"action": "save", "ph": "3"})
        self.job.refresh_from_db()
        self.assertIsNone(self.job.ph)

    def test_out_of_range_readings_rejected(self):
        self.login(self.tech)
        response = self.client.post(reverse("job_save", args=[self.job.pk]), {"action": "save", "ph": "19"})
        self.assertEqual(response.status_code, 400)
        self.job.refresh_from_db()
        self.assertIsNone(self.job.ph)

    def test_pnsdw_flags(self):
        self.job.ph, self.job.tds_raw, self.job.tds_product = 9, 400, 100
        levels = [level for level, _ in self.job.reading_flags()]
        self.assertEqual(levels, ["bad", "warn"])

    def test_html_in_input_is_escaped(self):
        self.login(self.office)
        self.client.post(reverse("customer_new"), {"name": "<script>alert(1)</script>", "customer_type": "residential"})
        response = self.client.get(reverse("customers"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_archive_keeps_history(self):
        self.job.status = Job.Status.DONE
        self.job.save()
        self.login(self.office)
        self.client.post(reverse("customer_archive", args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertTrue(Job.objects.filter(pk=self.job.pk).exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class HeaderTests(BaseCase):
    def test_security_headers(self):
        response = self.client.get(reverse("login"))
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
