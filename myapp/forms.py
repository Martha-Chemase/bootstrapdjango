from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from myapp.models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class StoreAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class SignUpForm(UserCreationForm):
    email = forms.EmailField()

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email address.")
        return email


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=32)
    address = forms.CharField(max_length=255, label="Delivery address")
    city = forms.CharField(max_length=100, initial="Nairobi")
    county = forms.CharField(max_length=100, initial="Nairobi")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
