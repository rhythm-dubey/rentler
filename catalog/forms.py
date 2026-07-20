from django import forms
from django.core.files.storage import default_storage

from .models import Category, Product, ProductVariant


class ProductBrowseFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Keywords')
    category = forms.SlugField(required=False)
    city = forms.CharField(required=False)
    state = forms.CharField(required=False)
    post_code = forms.CharField(required=False)
    delivery = forms.BooleanField(required=False)
    pickup = forms.BooleanField(required=False)
    postage = forms.BooleanField(required=False)


class ProductForm(forms.ModelForm):
    image_upload = forms.ImageField(
        required=False,
        help_text='Upload a product image (you can add more by editing again).',
    )
    available_on_days = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday'),
        ],
        widget=forms.CheckboxSelectMultiple,
    )
    selling_points_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='One selling point per line.',
        label='Selling points',
    )

    class Meta:
        model = Product
        fields = [
            'category',
            'name',
            'description',
            'make_payment',
            'hourly_price',
            'daily_price',
            'weekly_price',
            'monthly_price',
            'minimum_weeks',
            'minimum_months',
            'has_multiple_items',
            'total_items',
            'address',
            'city',
            'state',
            'post_code',
            'year',
            'make',
            'model',
            'owner_delivery_pickup',
            'owner_delivery_pickup_km',
            'owner_delivery_pickup_cost',
            'owner_pickup',
            'owner_postage',
            'owner_postage_cost',
            'which_tnc',
            'tnc',
            'available_on_days',
            'starting_hour',
            'ending_hour',
            'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'tnc': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        if self.instance and self.instance.pk:
            self.fields['available_on_days'].initial = self.instance.available_on_days or []
            points = self.instance.selling_points or []
            if isinstance(points, list):
                self.fields['selling_points_text'].initial = '\n'.join(str(p) for p in points)

    def clean_total_items(self):
        total = self.cleaned_data.get('total_items') or 1
        if total < 1:
            raise forms.ValidationError('Total items must be at least 1.')
        return total

    def clean_selling_points_text(self):
        text = self.cleaned_data.get('selling_points_text') or ''
        return [line.strip() for line in text.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.selling_points = self.cleaned_data.get('selling_points_text') or []
        instance.available_on_days = self.cleaned_data.get('available_on_days') or []

        upload = self.cleaned_data.get('image_upload')
        if upload:
            path = default_storage.save(f'products/{upload.name}', upload)
            paths = list(instance.images or [])
            paths.append(path)
            instance.images = paths

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['sku', 'notes', 'is_sold']
