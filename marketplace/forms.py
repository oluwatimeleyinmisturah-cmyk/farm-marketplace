from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile


class SignupForm(UserCreationForm):

    # ROLE (FIXED)
    role = forms.ChoiceField(
        choices=[
            ("", "Select your role"),   # 👈 important
            ("buyer", "Buyer"),
            ("farmer", "Farmer")
        ],
        required=True,
        widget=forms.Select(attrs={
            "class": "form-control",
            "id": "roleSelect"
        })
    )

    # EMAIL
    username = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )

    # NAME
    first_name = forms.CharField(
        label="Name",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = User
        fields = ["first_name", "username", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    # EMAIL VALIDATION
    def clean_username(self):
        email = self.cleaned_data.get("username")

        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Email already exists")

        return email

    # ROLE VALIDATION 
    def clean_role(self):
        role = self.cleaned_data.get("role")

        if role == "":
            raise forms.ValidationError("Please choose if you want to buy or sell.")

        return role

    # SAVE USER + PROFILE
    def save(self, commit=True):
        user = super().save(commit=False)

        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data["username"]
        user.first_name = self.cleaned_data["first_name"]

        if commit:
            user.save()

            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data["role"]
            profile.save()

        return user