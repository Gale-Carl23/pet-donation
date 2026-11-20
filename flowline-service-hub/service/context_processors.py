from django.conf import settings


def company(request):
    name = settings.COMPANY_NAME
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        from .models import CompanySettings

        name = CompanySettings.load().company_name or name
    return {"company_name": name}
