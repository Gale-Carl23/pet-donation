import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import AuditLog

logger = logging.getLogger("service.audit")


def client_ip(request):
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled unless a trusted
    # proxy rewrites it, and the proxy setup is per deployment.
    return request.META.get("REMOTE_ADDR") if request is not None else None


def audit(request, action, obj=None, summary=""):
    user = getattr(request, "user", None)
    entry = AuditLog.objects.create(
        user=user if user is not None and user.is_authenticated else None,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(getattr(obj, "pk", "") or ""),
        summary=(summary or (str(obj) if obj is not None else ""))[:255],
        ip_address=client_ip(request),
    )
    logger.info("%s user=%s %s:%s %s", action, entry.user_id, entry.object_type, entry.object_id, entry.summary)
    return entry


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    AuditLog.objects.create(user=user, action="login", ip_address=client_ip(request))


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        AuditLog.objects.create(user=user, action="logout", ip_address=client_ip(request))


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    # Never store the attempted password; keep the username for investigation.
    username = str(credentials.get("username", ""))[:120]
    AuditLog.objects.create(action="login_failed", summary=username, ip_address=client_ip(request))
