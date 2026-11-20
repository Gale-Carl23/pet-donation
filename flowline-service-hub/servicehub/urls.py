from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.views import password_change

admin.site.site_header = "Service Hub administration"
admin.site.site_title = "Service Hub admin"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/password/", password_change, name="password_change"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("service.urls")),
]
