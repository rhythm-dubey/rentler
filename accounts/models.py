from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import AllObjectsManager, UserManager


class Permission(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['codename']

    def __str__(self):
        return self.codename


class Role(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles',
        blank=True,
    )

    class Meta:
        ordering = ['slug']

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = [('role', 'permission')]

    def __str__(self):
        return f'{self.role.slug}:{self.permission.codename}'


class User(AbstractBaseUser, PermissionsMixin):
    class Gender(models.TextChoices):
        MALE = 'M', 'Male'
        FEMALE = 'F', 'Female'

    email = models.EmailField(max_length=150, unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    country_code = models.CharField(max_length=5, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    profile = models.ImageField(upload_to='profiles/', blank=True, null=True)

    address = models.TextField(blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    post_code = models.CharField(max_length=10, blank=True)

    business_name = models.CharField(max_length=255, blank=True)
    abn = models.CharField(max_length=50, blank=True)
    platform_fee = models.FloatField(null=True, blank=True)
    import_token = models.CharField(max_length=64, blank=True)

    bsb = models.CharField(max_length=6, blank=True)
    account_number = models.CharField(max_length=9, blank=True)
    bank_account_id = models.CharField(max_length=255, blank=True)

    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_connected_account_id = models.CharField(max_length=255, blank=True)
    stripe_charges_enabled = models.BooleanField(default=False)

    id_proof = models.FileField(upload_to='verification/', blank=True, null=True)
    utility_bill = models.FileField(upload_to='verification/', blank=True, null=True)
    address_verification = models.FileField(
        upload_to='verification/', blank=True, null=True
    )
    scanned_profile = models.FileField(upload_to='verification/', blank=True, null=True)
    documents = models.JSONField(default=dict, blank=True)

    is_blocked = models.BooleanField(default=False)
    is_identity_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    roles = models.ManyToManyField(
        Role,
        through='UserRole',
        related_name='users',
        blank=True,
    )

    objects = UserManager()
    all_objects = AllObjectsManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        ordering = ['email']

    def __str__(self):
        return self.email

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=['deleted_at', 'is_active'])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def has_role(self, slug: str) -> bool:
        return self.roles.filter(slug=slug).exists()

    def has_permission(self, codename: str) -> bool:
        if self.is_superuser:
            return True
        return self.roles.filter(permissions__codename=codename).exists()

    def assign_role(self, slug: str) -> Role:
        role = Role.objects.get(slug=slug)
        UserRole.objects.get_or_create(user=self, role=role)
        return role

    def remove_role(self, slug: str) -> None:
        UserRole.objects.filter(user=self, role__slug=slug).delete()


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'role')]

    def __str__(self):
        return f'{self.user.email}:{self.role.slug}'
