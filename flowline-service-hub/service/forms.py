from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.forms import inlineformset_factory

from .models import CompanySettings, Component, Customer, Job, WaterSystem

User = get_user_model()

phone_validator = RegexValidator(
    r"^[0-9+()\-\s]{7,30}$", "Enter a phone number using digits, spaces, +, - or brackets."
)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, **kwargs):
        super().__init__(format="%H:%M", **kwargs)


def technicians():
    return User.objects.filter(role=User.Role.TECHNICIAN, is_active=True)


class CustomerForm(forms.ModelForm):
    phone = forms.CharField(label="Mobile number", required=False, max_length=30, validators=[phone_validator],
                            widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "0917 123 4567"}))

    class Meta:
        model = Customer
        fields = ["name", "customer_type", "contact_name", "phone", "email", "area", "address", "notes"]
        widgets = {
            "area": forms.TextInput(attrs={"placeholder": "e.g. Alabang, Muntinlupa"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class WaterSystemForm(forms.ModelForm):
    class Meta:
        model = WaterSystem
        fields = ["system_type", "label", "model", "serial", "install_date"]
        widgets = {"install_date": DateInput()}


ComponentFormSet = inlineformset_factory(
    WaterSystem,
    Component,
    fields=["name", "interval_days", "last_changed"],
    widgets={"last_changed": DateInput(), "interval_days": forms.NumberInput(attrs={"min": 1, "max": 3650})},
    extra=1,
    can_delete=True,
)


class JobForm(forms.ModelForm):
    """Office: book a visit for one water system (or a customer with no system yet).

    The system and customer come from the URL, never from the form, so a
    tampered POST can't attach a job or components to someone else's system.
    """

    components = forms.ModelMultipleChoiceField(
        queryset=Component.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        label="Components to service",
    )

    class Meta:
        model = Job
        fields = ["job_type", "technician", "scheduled_date", "scheduled_time", "instructions"]
        widgets = {
            "scheduled_date": DateInput(),
            "scheduled_time": TimeInput(),
            "instructions": forms.Textarea(attrs={"rows": 2, "placeholder": "Gate code, parking, parts to bring"}),
        }

    def __init__(self, *args, system=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["technician"].queryset = technicians()
        self.fields["technician"].required = False
        if system is not None:
            comps = system.components.all()
            self.fields["components"].queryset = comps
            self.fields["components"].label_from_instance = lambda c: f"{c.name} · {c.due_label}"
            if not self.is_bound:
                self.initial["components"] = [c.pk for c in comps if c.days_left <= 14]
        else:
            del self.fields["components"]


class JobAssignForm(forms.ModelForm):
    """Office: reschedule or reassign an open job."""

    class Meta:
        model = Job
        fields = ["technician", "scheduled_date", "scheduled_time", "instructions"]
        widgets = {
            "scheduled_date": DateInput(),
            "scheduled_time": TimeInput(),
            "instructions": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["technician"].queryset = technicians()
        self.fields["technician"].required = False


class JobFieldForm(forms.ModelForm):
    """Technician: on-site readings, parts and sign-off."""

    class Meta:
        model = Job
        fields = ["tds_raw", "tds_product", "ph", "pressure_psi", "parts_used", "field_notes", "received_by"]
        labels = {"ph": "pH", "tds_raw": "Raw TDS (mg/L)", "tds_product": "Product TDS (mg/L)"}
        widgets = {
            "tds_raw": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.1"}),
            "tds_product": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.1"}),
            "ph": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.01"}),
            "pressure_psi": forms.NumberInput(attrs={"inputmode": "decimal", "step": "0.1"}),
            "parts_used": forms.TextInput(attrs={"placeholder": "e.g. 2× sediment 5 µm 10\", 1× CTO 10\""}),
            "field_notes": forms.Textarea(attrs={"rows": 3}),
            "received_by": forms.TextInput(attrs={"placeholder": "Name of person who accepted the work"}),
        }


class CompanySettingsForm(forms.ModelForm):
    class Meta:
        model = CompanySettings
        fields = ["company_name", "reminder_template"]
        widgets = {"reminder_template": forms.Textarea(attrs={"rows": 4})}

    def clean_reminder_template(self):
        text = self.cleaned_data["reminder_template"]
        try:
            text.format(contact="x", company="x", system="x", components="x")
        except (KeyError, IndexError, ValueError):
            raise forms.ValidationError("Use only the placeholders {contact}, {company}, {system} and {components}.")
        return text
