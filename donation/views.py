from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import DonationForm, RegistrationForm


def home(request):
    return render(request, "donation/home.html")


def about(request):
    return render(request, "donation/about.html")


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your account is ready. Welcome to Kindred Paws!")
            return redirect("home")
    else:
        form = RegistrationForm()

    return render(request, "donation/register.html", {"form": form})


@login_required(login_url="login")
def create_donation(request):
    if request.method == "POST":
        form = DonationForm(request.POST, request.FILES)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.donator = request.user
            donation.save()
            messages.success(request, "Your donation was submitted.")
            return redirect("home")
    else:
        form = DonationForm()

    return render(request, "donation/donation_form.html", {"form": form})
