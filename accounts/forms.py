from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = (
        ('renter', 'Renter'),
        ('owner', 'Owner'),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy.'},
    )

    class Meta:
        model = User
        fields = ('email', 'name', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.name = self.cleaned_data['name']
        if commit:
            user.save()
            user.assign_role(self.cleaned_data['role'])
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if getattr(user, 'is_blocked', False):
            raise ValidationError('This account has been blocked.', code='blocked')
        if getattr(user, 'deleted_at', None) is not None:
            raise ValidationError('This account is no longer active.', code='deleted')

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )
            if self.user_cache is None:
                # Soft-deleted users are hidden from the default manager.
                deleted = User.all_objects.filter(email__iexact=email, deleted_at__isnull=False).first()
                if deleted:
                    raise ValidationError('This account is no longer active.', code='deleted')
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            'name',
            'phone',
            'country_code',
            'gender',
            'profile',
            'address',
            'state',
            'city',
            'post_code',
            'business_name',
            'abn',
        )
