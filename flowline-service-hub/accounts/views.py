from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from service.audit import audit


def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        # Keep this session; other sessions for the user are invalidated.
        update_session_auth_hash(request, user)
        audit(request, "password_changed", user)
        messages.success(request, "Password changed.")
        return redirect("home")
    return render(request, "registration/password_change.html", {"form": form})
