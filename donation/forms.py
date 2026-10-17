from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Donation, User


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email address")

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class DonationForm(forms.ModelForm):
    file = forms.ImageField(
        help_text="Upload a readable image no larger than 5 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = Donation
        fields = ("price", "payment_method", "file")
        labels = {
            "price": "Donation amount",
            "file": "Payment proof image",
        }
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def clean_file(self):
        image = self.cleaned_data["file"]
        if image.size > 5 * 1024 * 1024:
            raise ValidationError("The proof image must be 5 MB or smaller.")
        return image
