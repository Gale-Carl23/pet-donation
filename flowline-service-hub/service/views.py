from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .audit import audit
from .forms import (
    ComponentFormSet,
    CompanySettingsForm,
    CustomerForm,
    JobAssignForm,
    JobFieldForm,
    JobForm,
    WaterSystemForm,
)
from .models import DUE_SOON_DAYS, AuditLog, CompanySettings, Component, Customer, Job, WaterSystem, today
from .permissions import admin_required, get_job_for_user, office_required

User = get_user_model()


def home(request):
    return redirect("dashboard" if request.user.is_office else "field")


# --- Dashboard ----------------------------------------------------------------

def due_systems():
    """Active systems with at least one component due within DUE_SOON_DAYS, most urgent first."""
    horizon = today() + timedelta(days=DUE_SOON_DAYS)
    open_jobs = Job.objects.filter(status__in=Job.OPEN_STATUSES).order_by("scheduled_date")
    systems = (
        WaterSystem.objects.filter(is_active=True, customer__is_active=True)
        .select_related("customer")
        .prefetch_related("components", Prefetch("jobs", queryset=open_jobs, to_attr="open_jobs"))
    )
    rows = []
    for system in systems:
        due = [c for c in system.components.all() if c.next_due <= horizon]
        if due:
            due.sort(key=lambda c: c.days_left)
            rows.append({"system": system, "due": due, "worst": due[0],
                         "booked": system.open_jobs[0] if system.open_jobs else None})
    rows.sort(key=lambda r: r["worst"].days_left)
    return rows


@office_required
def dashboard(request):
    rows = due_systems()
    now = today()
    todays = Job.objects.filter(scheduled_date=now).exclude(status=Job.Status.CANCELLED) \
        .select_related("customer", "technician")
    overdue = sum(1 for r in rows for c in r["due"] if c.days_left < 0)
    return render(request, "service/dashboard.html", {
        "rows": rows,
        "todays": todays,
        "kpi_overdue": overdue,
        "kpi_soon": sum(len(r["due"]) for r in rows) - overdue,
        "kpi_done": Job.objects.filter(status=Job.Status.DONE, completed_at__date__gte=now.replace(day=1)).count(),
        "unbooked": sum(1 for r in rows if not r["booked"]),
        "today": now,
    })


# --- Schedule -----------------------------------------------------------------

STATUS_FILTERS = {
    "open": ("Open jobs", Job.OPEN_STATUSES),
    "done": ("Completed", (Job.Status.DONE,)),
    "cancelled": ("Cancelled", (Job.Status.CANCELLED,)),
    "all": ("All jobs", None),
}


@office_required
def schedule(request):
    status = request.GET.get("status", "open")
    if status not in STATUS_FILTERS:
        status = "open"
    jobs = Job.objects.select_related("customer", "technician", "system")
    statuses = STATUS_FILTERS[status][1]
    if statuses:
        jobs = jobs.filter(status__in=statuses)
    tech_id = request.GET.get("tech", "")
    if tech_id.isdigit():
        jobs = jobs.filter(technician_id=int(tech_id))
    if status in ("done", "cancelled"):
        jobs = jobs.order_by("-scheduled_date", "-scheduled_time")
    page = Paginator(jobs, 50).get_page(request.GET.get("page"))
    return render(request, "service/schedule.html", {
        "page": page,
        "status": status,
        "status_filters": [(k, v[0]) for k, v in STATUS_FILTERS.items()],
        "tech_id": tech_id,
        "technicians": User.objects.filter(role=User.Role.TECHNICIAN, is_active=True),
        "today": today(),
    })


@office_required
def job_new(request, system_id=None, customer_id=None):
    system = None
    if system_id is not None:
        system = get_object_or_404(WaterSystem.objects.select_related("customer"), pk=system_id, is_active=True)
        customer = system.customer
    elif customer_id is not None:
        customer = get_object_or_404(Customer, pk=customer_id, is_active=True)
    else:
        return redirect("customers")

    form = JobForm(request.POST or None, system=system,
                   initial={"scheduled_date": today() + timedelta(days=1), "scheduled_time": "09:00"})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            job = form.save(commit=False)
            job.customer, job.system, job.created_by = customer, system, request.user
            job.save()
            job.build_tasks(form.cleaned_data.get("components") or [])
            audit(request, "job_created", job)
        messages.success(request, f"Visit booked for {job.scheduled_date:%b %d}.")
        return redirect("job_detail", pk=job.pk)
    return render(request, "service/job_form.html", {"form": form, "system": system, "customer": customer})


# --- Job sheet ----------------------------------------------------------------

def job_detail(request, pk):
    job = get_job_for_user(request.user, pk)
    return render(request, "service/job_detail.html", {
        "job": job,
        "tasks": job.tasks.all(),
        "field_form": JobFieldForm(instance=job),
        "assign_form": JobAssignForm(instance=job) if request.user.is_office else None,
        "report": service_report(job) if job.status == Job.Status.DONE else "",
    })


def _save_field_work(request, job):
    """Save readings and ticked tasks. Returns the form (check .is_valid())."""
    form = JobFieldForm(request.POST, instance=job)
    if form.is_valid():
        form.save()
        ticked = {int(x) for x in request.POST.getlist("task") if x.isdigit()}
        for task in job.tasks.all():
            done = task.pk in ticked
            if task.done != done:
                task.done = done
                task.save(update_fields=["done"])
    return form


def _render_job_errors(request, job, form):
    messages.error(request, "Some readings need fixing before the job can be saved.")
    return render(request, "service/job_detail.html", {
        "job": job, "tasks": job.tasks.all(), "field_form": form,
        "assign_form": JobAssignForm(instance=job) if request.user.is_office else None,
    }, status=400)


@require_POST
def job_save(request, pk):
    with transaction.atomic():
        job = get_job_for_user(request.user, pk)
        job = Job.objects.select_for_update().get(pk=job.pk)
        if not job.is_open:
            messages.error(request, "This job is closed and can no longer be changed.")
            return redirect("job_detail", pk=job.pk)
        form = _save_field_work(request, job)
        if not form.is_valid():
            return _render_job_errors(request, job, form)
        action = request.POST.get("action", "save")
        if action == "start" and job.status == Job.Status.SCHEDULED:
            job.status, job.started_at = Job.Status.IN_PROGRESS, timezone.now()
            job.save(update_fields=["status", "started_at", "updated_at"])
            audit(request, "job_started", job)
            messages.success(request, "Job started.")
        elif action == "complete":
            done_tasks = [t for t in job.tasks.select_related("component") if t.done]
            if not done_tasks:
                messages.error(request, "Tick the tasks you finished before completing the job.")
                return redirect("job_detail", pk=job.pk)
            # Reset due dates only for components of this job's own system.
            reset = [t.component for t in done_tasks if t.component and t.component.system_id == job.system_id]
            for comp in reset:
                comp.last_changed = today()
                comp.save(update_fields=["last_changed"])
            job.status, job.completed_at, job.completed_by = Job.Status.DONE, timezone.now(), request.user
            job.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
            audit(request, "job_completed", job, f"{job} · {len(reset)} due dates reset")
            messages.success(request, f"Job complete. {len(reset)} due date{'s' if len(reset) != 1 else ''} reset.")
        else:
            audit(request, "job_updated", job)
            messages.success(request, "Progress saved.")
    return redirect("job_detail", pk=job.pk)


@require_POST
@office_required
def job_assign(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if not job.is_open:
        raise PermissionDenied
    form = JobAssignForm(request.POST, instance=job)
    if form.is_valid():
        form.save()
        audit(request, "job_rescheduled", job)
        messages.success(request, "Job updated.")
    else:
        messages.error(request, "Check the date, time and technician, then try again.")
    return redirect("job_detail", pk=job.pk)


@require_POST
@office_required
def job_cancel(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if job.is_open:
        job.status = Job.Status.CANCELLED
        job.save(update_fields=["status", "updated_at"])
        audit(request, "job_cancelled", job)
        messages.success(request, "Job cancelled.")
    return redirect("job_detail", pk=job.pk)


def service_report(job):
    lines = [
        f"SERVICE REPORT · {CompanySettings.load().company_name or ''}".rstrip(" ·"),
        f"Customer: {job.customer.name}",
    ]
    if job.system:
        serial = f" · S/N {job.system.serial}" if job.system.serial else ""
        lines.append(f"System: {job.system}{serial}")
    when = timezone.localtime(job.completed_at) if job.completed_at else job.scheduled_date
    tech = f" by {job.completed_by}" if job.completed_by else ""
    lines += [f"Visit: {job.get_job_type_display()} on {when:%b %d, %Y}{tech}", "", "Work done:"]
    lines += [f"• {t.label}" for t in job.tasks.all() if t.done]
    readings = [
        f"Raw TDS {job.tds_raw} mg/L" if job.tds_raw is not None else "",
        f"Product TDS {job.tds_product} mg/L" if job.tds_product is not None else "",
        f"pH {job.ph}" if job.ph is not None else "",
        f"Pressure {job.pressure_psi} psi" if job.pressure_psi is not None else "",
    ]
    readings = [r for r in readings if r]
    if readings:
        lines += ["", "Readings: " + " · ".join(readings)]
    if job.parts_used:
        lines.append(f"Parts used: {job.parts_used}")
    if job.field_notes:
        lines.append(f"Notes: {job.field_notes}")
    if job.received_by:
        lines.append(f"Received by: {job.received_by}")
    if job.system:
        nxt = min(job.system.components.all(), key=lambda c: c.next_due, default=None)
        if nxt:
            lines += ["", f"Next service: {nxt.name} around {nxt.next_due:%b %d, %Y}"]
    return "\n".join(lines)


# --- Field app ----------------------------------------------------------------

def field(request):
    """A technician's jobs for today, carried-over jobs, and the next 7 days."""
    techs = User.objects.filter(role=User.Role.TECHNICIAN, is_active=True)
    tech = request.user
    if request.user.is_office:
        tech_id = request.GET.get("tech", "")
        tech = techs.filter(pk=int(tech_id)).first() if tech_id.isdigit() else None
    now = today()
    jobs = Job.objects.none()
    if tech is not None:
        jobs = Job.objects.filter(technician=tech).exclude(status=Job.Status.CANCELLED) \
            .select_related("customer", "system")
    current = jobs.filter(Q(scheduled_date=now) | Q(scheduled_date__lt=now, status__in=Job.OPEN_STATUSES))
    upcoming = jobs.filter(scheduled_date__gt=now, scheduled_date__lte=now + timedelta(days=7))
    return render(request, "service/field.html", {
        "tech": tech, "technicians": techs if request.user.is_office else None,
        "current": current, "upcoming": upcoming, "today": now,
    })


# --- Customers and systems ----------------------------------------------------

@office_required
def customers(request):
    q = request.GET.get("q", "").strip()[:100]
    qs = Customer.objects.filter(is_active=True).prefetch_related(
        Prefetch("systems", queryset=WaterSystem.objects.filter(is_active=True).prefetch_related("components")))
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(area__icontains=q) | Q(contact_name__icontains=q)
                       | Q(address__icontains=q) | Q(phone__icontains=q))
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    for customer in page:
        for system in customer.systems.all():
            system.worst = min(system.components.all(), key=lambda c: c.days_left, default=None)
    return render(request, "service/customers.html", {
        "page": page, "q": q, "total_customers": Customer.objects.filter(is_active=True).count(),
        "total_systems": WaterSystem.objects.filter(is_active=True, customer__is_active=True).count(),
    })


@office_required
def customer_form(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk, is_active=True) if pk else None
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if customer is None:
            obj.created_by = request.user
        obj.save()
        audit(request, "customer_updated" if customer else "customer_created", obj)
        messages.success(request, "Customer saved.")
        return redirect("customer_detail", pk=obj.pk)
    return render(request, "service/customer_form.html", {"form": form, "customer": customer})


@office_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk, is_active=True)
    systems = customer.systems.filter(is_active=True).prefetch_related("components")
    jobs = customer.jobs.select_related("technician", "system").order_by("-scheduled_date")[:30]
    return render(request, "service/customer_detail.html", {"customer": customer, "systems": systems, "jobs": jobs})


@require_POST
@office_required
def customer_archive(request, pk):
    customer = get_object_or_404(Customer, pk=pk, is_active=True)
    if customer.jobs.filter(status__in=Job.OPEN_STATUSES).exists():
        messages.error(request, "Cancel or finish this customer's open jobs first.")
        return redirect("customer_detail", pk=pk)
    # Archive rather than delete, so service history stays intact.
    customer.is_active = False
    customer.save(update_fields=["is_active", "updated_at"])
    audit(request, "customer_archived", customer)
    messages.success(request, f"{customer.name} archived.")
    return redirect("customers")


@office_required
def system_new(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id, is_active=True)
    form = WaterSystemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            system = form.save(commit=False)
            system.customer = customer
            system.save()
            system.add_preset_components()
            audit(request, "system_created", system, f"{customer.name} · {system}")
        messages.success(request, "System added. Check when each part was last changed.")
        return redirect("system_detail", pk=system.pk)
    return render(request, "service/system_form.html", {"form": form, "customer": customer})


@office_required
def system_detail(request, pk):
    system = get_object_or_404(WaterSystem.objects.select_related("customer"), pk=pk, is_active=True)
    form = WaterSystemForm(request.POST or None, instance=system, prefix="sys")
    formset = ComponentFormSet(request.POST or None, instance=system, prefix="comp")
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                audit(request, "system_updated", system, f"{system.customer.name} · {system}")
            messages.success(request, "System saved.")
            return redirect("system_detail", pk=system.pk)
        messages.error(request, "Some fields need fixing.")
    jobs = system.jobs.select_related("technician").order_by("-scheduled_date")[:30]
    return render(request, "service/system_detail.html", {
        "system": system, "form": form, "formset": formset, "jobs": jobs,
        "components": system.components.all(),
    })


@require_POST
@office_required
def system_archive(request, pk):
    system = get_object_or_404(WaterSystem, pk=pk, is_active=True)
    system.is_active = False
    system.save(update_fields=["is_active", "updated_at"])
    audit(request, "system_archived", system)
    messages.success(request, "System removed from tracking.")
    return redirect("customer_detail", pk=system.customer_id)


@office_required
def reminder(request, pk):
    system = get_object_or_404(WaterSystem.objects.select_related("customer"), pk=pk, is_active=True)
    due = [c for c in system.components.all() if c.days_left <= DUE_SOON_DAYS]
    cfg = CompanySettings.load()
    contact = (system.customer.contact_name or system.customer.name).split(" ")[0]
    text = cfg.reminder_template.format(
        contact=contact,
        company=cfg.company_name or "your water service team",
        system=str(system),
        components=", ".join(c.name for c in due) or "a routine check",
    )
    return render(request, "service/reminder.html", {"system": system, "text": text, "due": due})


# --- Administration -----------------------------------------------------------

@admin_required
def company_settings(request):
    cfg = CompanySettings.load()
    form = CompanySettingsForm(request.POST or None, instance=cfg)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "settings_updated", cfg)
        messages.success(request, "Settings saved.")
        return redirect("company_settings")
    staff = User.objects.order_by("-is_active", "role", "first_name")
    return render(request, "service/settings.html", {"form": form, "staff": staff})


@admin_required
def audit_log(request):
    page = Paginator(AuditLog.objects.select_related("user"), 100).get_page(request.GET.get("page"))
    return render(request, "service/audit_log.html", {"page": page})
