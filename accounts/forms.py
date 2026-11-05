import re
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Phone, Email, or Username", max_length=150,
                               widget=forms.TextInput(attrs={
                                   'class': 'form-input', 'placeholder': 'Enter your email',
                                   'autocomplete': 'username', 'autofocus': True,
                               }))
    password = forms.CharField(label="Password",
                               widget=forms.PasswordInput(attrs={
                                   'class': 'form-input', 'placeholder': '••••••••••••',
                                   'autocomplete': 'current-password',
                               }))


class UserSignupForm(UserCreationForm):
    phone = forms.CharField(max_length=20, required=False,
                            widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+923001234567'}))
    email = forms.EmailField(required=False,
                             widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Enter your email'}))
    cnic = forms.CharField(max_length=20, required=False,
                           widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '35202-1234567-8'}))
    first_name = forms.CharField(max_length=80, required=True,
                                 widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your full name'}))

    class Meta:
        model = User
        fields = ('first_name', 'phone', 'email', 'cnic', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ('password1', 'password2'):
            self.fields[f].widget.attrs.update({'class': 'form-input'})

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get('phone') or '').strip()
        email = (cleaned.get('email') or '').strip()
        if not phone and not email:
            raise forms.ValidationError("Please provide at least a phone number or email.")
        if phone and not re.match(r'^\+?\d{10,15}$', phone):
            raise forms.ValidationError({"phone": "Phone must be 10–15 digits, optionally starting with +."})
        cnic = cleaned.get('cnic', '').strip()
        if cnic and not re.match(r'^\d{5}-\d{7}-\d$', cnic):
            raise forms.ValidationError({"cnic": "CNIC must be in format NNNNN-NNNNNNN-N."})

        if phone:
            if User.objects.filter(phone=phone).exists():
                raise forms.ValidationError({"phone": "An account with this phone number already exists."})
        if email:
            if User.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError({"email": "An account with this email already exists."})
        if cnic:
            if User.objects.filter(cnic=cnic).exists():
                raise forms.ValidationError({"cnic": "An account with this CNIC already exists."})
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        phone = (self.cleaned_data.get('phone') or '').strip()
        email = (self.cleaned_data.get('email') or '').strip()
        user.username = phone or email
        user.phone = phone or None
        user.email = email or None
        user.first_name = self.cleaned_data.get('first_name', '')
        user.cnic = self.cleaned_data.get('cnic', '') or None
        user.role = User.USER
        if commit:
            user.save()
        return user


class DigCreateUserForm(forms.Form):
    ROLE_CHOICES = [
        ('DIG',        'DIG (Super Admin)'),
        ('SSP',        'SSP | Senior Superintendent'),
        ('SUPV',       'Supervisor'),
        ('OFFICER',    'Officer (issue challan only - NO appeal approval)'),
        ('AUDIT',      'Audit Officer'),
        ('IT',         'IT Support (dev/testing only - NO operational access)'),
        ('USER',       'Registered Citizen'),
    ]
    first_name = forms.CharField(max_length=80, required=True,
                                 widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone = forms.CharField(max_length=20, required=False,
                            widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+923001234567',
                                                         'data-autocomplete': 'phone',
                                                         'data-validate': 'phone',
                                                         'data-autocomplete-url': '/portal/dig/autocomplete/',
                                                         'autocomplete': 'off'}))
    email = forms.EmailField(required=False,
                             widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Enter your email',
                                                            'data-autocomplete': 'email',
                                                            'data-validate': 'email',
                                                            'data-autocomplete-url': '/portal/dig/autocomplete/',
                                                            'autocomplete': 'off'}))
    cnic = forms.CharField(max_length=20, required=False,
                           widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '35202-1234567-8',
                                                        'data-autocomplete': 'cnic',
                                                        'data-validate': 'cnic',
                                                        'data-autocomplete-url': '/portal/dig/autocomplete/',
                                                        'autocomplete': 'off'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial='OFFICER',
                             widget=forms.Select(attrs={'class': 'form-input'}))
    staff_id = forms.CharField(max_length=30, required=False,
                               widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'PSC-2026-XXX-001'}))
    region = forms.CharField(max_length=60, required=False,
                             widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Central Region'}))
    password = forms.CharField(min_length=12,
                               widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Min 12 characters'}))

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get('phone') or '').strip()
        email = (cleaned.get('email') or '').strip()
        if not phone and not email:
            raise forms.ValidationError("At least one of phone or email is required.")
        cnic = cleaned.get('cnic', '').strip()
        if cnic and not re.match(r'^\d{5}-\d{7}-\d$', cnic):
            raise forms.ValidationError({"cnic": "CNIC must be in format NNNNN-NNNNNNN-N."})

        if phone and User.objects.filter(phone=phone).exists():
            raise forms.ValidationError({"phone": "An account with this phone number already exists."})
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError({"email": "An account with this email already exists."})
        if cnic and User.objects.filter(cnic=cnic).exists():
            raise forms.ValidationError({"cnic": "An account with this CNIC already exists."})
        return cleaned

    def save(self, creator):
        phone = (self.cleaned_data.get('phone') or '').strip()
        email = (self.cleaned_data.get('email') or '').strip()
        user = User.objects.create_user(
            username=phone or email,
            phone=phone or None,
            email=email or None,
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data.get('first_name', ''),
            cnic=self.cleaned_data.get('cnic', '') or None,
            role=self.cleaned_data.get('role', User.OFFICER),
        )
        user.staff_id = (self.cleaned_data.get('staff_id') or '').strip() or None
        user.region   = (self.cleaned_data.get('region') or '').strip() or None
        user.save()
        from .permissions import get_role_permissions
        user._auto_assigned_permissions = sorted(get_role_permissions(user.role))
        return user


class ProfileEditForm(forms.Form):
    first_name = forms.CharField(max_length=80, required=False,
                                 widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone = forms.CharField(max_length=20, required=False,
                            widget=forms.TextInput(attrs={'class': 'form-input'}))
    email = forms.EmailField(required=False,
                             widget=forms.EmailInput(attrs={'class': 'form-input'}))
    cnic = forms.CharField(max_length=20, required=False,
                           widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '35202-1234567-8'}))

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get('phone') or '').strip()
        email = (cleaned.get('email') or '').strip()
        cnic = (cleaned.get('cnic') or '').strip()
        if not phone and not email:
            raise forms.ValidationError("At least one of phone or email must be provided.")
        if phone and not re.match(r'^\+?\d{10,15}$', phone):
            raise forms.ValidationError({"phone": "Phone must be 10–15 digits, optionally starting with +."})
        if cnic and not re.match(r'^\d{5}-\d{7}-\d$', cnic):
            raise forms.ValidationError({"cnic": "CNIC must be in format NNNNN-NNNNNNN-N."})
        return cleaned


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input'}))
    new_password1 = forms.CharField(min_length=12, widget=forms.PasswordInput(attrs={'class': 'form-input'}))
    new_password2 = forms.CharField(min_length=12, widget=forms.PasswordInput(attrs={'class': 'form-input'}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password1') != cleaned.get('new_password2'):
            raise forms.ValidationError("New passwords do not match.")
        return cleaned

