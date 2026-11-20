from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Job


def office_required(view):
    """Only office staff and administrators: customers, schedule, settings."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_office:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def get_job_for_user(user, pk):
    """Office staff see every job; a technician only sees jobs assigned to them.

    Other technicians' jobs return 404 rather than 403, so job ids can't be
    probed to learn which exist.
    """
    qs = Job.objects.select_related("customer", "system", "technician")
    if not user.is_office:
        qs = qs.filter(technician=user)
    return get_object_or_404(qs, pk=pk)
