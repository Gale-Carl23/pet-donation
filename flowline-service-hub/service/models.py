from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

DUE_SOON_DAYS = 14

# Service intervals in days for each system type. Used to pre-fill components
# when a new system is recorded; office staff can adjust them per system.
SYSTEM_PRESETS = {
    "ro": [("Sediment filter 5 µm", 90), ("Carbon block (CTO)", 180), ("Post-carbon T33", 365), ("RO membrane", 730)],
    "ro_uv": [("Sediment filter 5 µm", 90), ("Carbon block (CTO)", 180), ("Post-carbon T33", 365),
              ("RO membrane", 730), ("UV lamp", 365)],
    "refilling": [("Micron cartridges", 30), ("Tank & line sanitation", 30), ("Bacteriological test", 30),
                  ("RO membranes", 730), ("UV lamp", 365)],
    "softener": [("Salt refill & regeneration check", 30), ("Resin bed inspection", 365)],
    "multimedia": [("Backwash & service", 30), ("Filter media replacement", 730)],
    "uv": [("UV lamp", 365), ("Quartz sleeve cleaning", 180)],
}

STANDARD_TASKS = [
    "Check fittings and housings for leaks",
    "Flush system and check pressure",
    "Record TDS and pH readings",
    "Clean work area and brief customer",
]


def today():
    return timezone.localdate()


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Customer(TimeStamped):
    class Type(models.TextChoices):
        RESIDENTIAL = "residential", "Residential"
        REFILLING = "refilling", "Refilling station"
        FOOD = "food", "Restaurant / food"
        COMMERCIAL = "commercial", "Commercial building"
        INDUSTRIAL = "industrial", "Industrial"
        HEALTH = "health", "Hospital / clinic"
        SCHOOL = "school", "School"

    name = models.CharField(max_length=150)
    customer_type = models.CharField("type", max_length=20, choices=Type.choices, default=Type.RESIDENTIAL)
    contact_name = models.CharField("contact person", max_length=120, blank=True)
    phone = models.CharField("mobile number", max_length=30, blank=True)
    email = models.EmailField(blank=True)
    area = models.CharField("city / area", max_length=120, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WaterSystem(TimeStamped):
    class SystemType(models.TextChoices):
        RO = "ro", "RO system (5-stage)"
        RO_UV = "ro_uv", "RO + UV system"
        REFILLING = "refilling", "Refilling station"
        SOFTENER = "softener", "Water softener"
        MULTIMEDIA = "multimedia", "Multimedia + carbon filter"
        UV = "uv", "UV sterilizer"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="systems")
    system_type = models.CharField(max_length=20, choices=SystemType.choices)
    label = models.CharField("location label", max_length=80, blank=True, help_text="e.g. Kitchen, Production line 2")
    model = models.CharField("brand / model", max_length=120, blank=True)
    serial = models.CharField("serial no.", max_length=80, blank=True)
    install_date = models.DateField(default=today)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["customer__name", "system_type"]
        verbose_name = "water system"

    def __str__(self):
        text = self.get_system_type_display()
        return f"{text} · {self.label}" if self.label else text

    def add_preset_components(self, last_changed=None):
        last_changed = last_changed or self.install_date
        Component.objects.bulk_create(
            Component(system=self, name=name, interval_days=days, last_changed=last_changed, position=i)
            for i, (name, days) in enumerate(SYSTEM_PRESETS.get(self.system_type, []))
        )


class Component(models.Model):
    system = models.ForeignKey(WaterSystem, on_delete=models.CASCADE, related_name="components")
    name = models.CharField(max_length=120)
    interval_days = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3650)])
    last_changed = models.DateField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name

    @property
    def next_due(self):
        return self.last_changed + timedelta(days=self.interval_days)

    @property
    def days_left(self):
        return (self.next_due - today()).days

    @property
    def level(self):
        days = self.days_left
        if days < 0:
            return "bad"
        return "warn" if days <= DUE_SOON_DAYS else "ok"

    @property
    def due_label(self):
        days = self.days_left
        if days < 0:
            return f"{-days} d overdue"
        if days == 0:
            return "Due today"
        return f"Due in {days} d"


class Job(TimeStamped):
    class JobType(models.TextChoices):
        PMS = "pms", "Preventive maintenance (PMS)"
        FILTER = "filter", "Filter change"
        REPAIR = "repair", "Repair / troubleshooting"
        TEST = "test", "Water testing"
        INSTALL = "install", "Installation"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    OPEN_STATUSES = (Status.SCHEDULED, Status.IN_PROGRESS)

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="jobs")
    system = models.ForeignKey(WaterSystem, null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.PMS)
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="jobs", limit_choices_to={"role": "technician", "is_active": True})
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    instructions = models.TextField("notes for the technician", blank=True)

    # Filled in on site
    tds_raw = models.DecimalField("raw TDS (mg/L)", max_digits=7, decimal_places=1, null=True, blank=True,
                                  validators=[MinValueValidator(0), MaxValueValidator(50000)])
    tds_product = models.DecimalField("product TDS (mg/L)", max_digits=7, decimal_places=1, null=True, blank=True,
                                      validators=[MinValueValidator(0), MaxValueValidator(50000)])
    ph = models.DecimalField("pH", max_digits=4, decimal_places=2, null=True, blank=True,
                             validators=[MinValueValidator(0), MaxValueValidator(14)])
    pressure_psi = models.DecimalField("pressure (psi)", max_digits=6, decimal_places=1, null=True, blank=True,
                                       validators=[MinValueValidator(0), MaxValueValidator(1000)])
    parts_used = models.CharField(max_length=500, blank=True)
    field_notes = models.TextField("notes", blank=True)
    received_by = models.CharField("received by", max_length=120, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")

    class Meta:
        ordering = ["scheduled_date", "scheduled_time"]
        indexes = [models.Index(fields=["scheduled_date", "status"]), models.Index(fields=["technician", "status"])]

    def __str__(self):
        return f"{self.get_job_type_display()} · {self.customer} · {self.scheduled_date:%b %d, %Y}"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_late(self):
        return self.is_open and self.scheduled_date < today()

    def build_tasks(self, components):
        tasks = []
        for i, comp in enumerate(components):
            verb = "" if any(w in comp.name.lower() for w in ("test", "check", "inspection", "sanitation", "cleaning",
                                                                "service")) else "Replace "
            tasks.append(JobTask(job=self, label=f"{verb}{comp.name}", component=comp, position=i))
        offset = len(tasks)
        tasks += [JobTask(job=self, label=label, position=offset + i) for i, label in enumerate(STANDARD_TASKS)]
        JobTask.objects.bulk_create(tasks)

    def reading_flags(self):
        """Compare readings with Philippine drinking water standards (PNSDW 2017)."""
        flags = []
        if self.ph is not None:
            if self.ph < 6.5 or self.ph > 8.5:
                flags.append(("bad", f"pH {self.ph} is outside the PNSDW range of 6.5–8.5."))
            else:
                flags.append(("ok", f"pH {self.ph} is within the PNSDW range."))
        if self.tds_product is not None and self.tds_product > 600:
            flags.append(("bad", f"Product TDS {self.tds_product} mg/L is above the PNSDW limit of 600 mg/L."))
        if (self.tds_raw and self.tds_product is not None and self.system
                and self.system.system_type in ("ro", "ro_uv", "refilling")):
            rejection = round((1 - float(self.tds_product) / float(self.tds_raw)) * 100, 1)
            if rejection < 90:
                flags.append(("warn", f"Salt rejection is {rejection}%. Below 90% usually means the RO membrane "
                                      "needs replacing."))
            else:
                flags.append(("ok", f"Salt rejection is {rejection}%."))
        return flags


class JobTask(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="tasks")
    label = models.CharField(max_length=200)
    component = models.ForeignKey(Component, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    done = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.label


class CompanySettings(models.Model):
    """One row of company-wide settings, edited by administrators."""

    company_name = models.CharField(max_length=150, blank=True)
    reminder_template = models.TextField(
        blank=True,
        default=(
            "Hi {contact}! This is {company}. Your {system} is due for: {components}. Regular changes keep your "
            "water clean and protect your system. Reply with a date that suits you and we'll send a technician. "
            "Thank you!"
        ),
        help_text="Placeholders: {contact}, {company}, {system}, {components}",
    )

    class Meta:
        verbose_name = "company settings"
        verbose_name_plural = "company settings"

    def __str__(self):
        return "Company settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    """Append-only record of who changed what, for accountability."""

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=40, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.user} {self.action} {self.object_type} {self.object_id}"
