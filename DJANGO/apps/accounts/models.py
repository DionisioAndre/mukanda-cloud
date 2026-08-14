"""
backend/apps/accounts/models.py
═══════════════════════════════════════════════════════════════
FileVault — User Hierarchy & RBAC Data Models

Role Hierarchy (mirrors Windows Server Active Directory):
  SUPER_ADMIN  →  Full Control (God mode — Diretor)
  DEPT_MANAGER →  Full Control over own department
  TEAM_MEMBER  →  Granular permissions set by their Gestor

Permission Bitmask (NTFS-inspired):
  READ    = 0b0001  (1)
  WRITE   = 0b0010  (2)
  EXECUTE = 0b0100  (4)
  DELETE  = 0b1000  (8)
  FULL    = 0b1111  (15)

Combining with OR: READ|WRITE = 3, READ|WRITE|DELETE = 11
Testing with AND:  (mask & READ) != 0  → user can read
═══════════════════════════════════════════════════════════════
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


# ── Role Enum ─────────────────────────────────────────────────

class Role(models.TextChoices):
    SUPER_ADMIN  = 'super_admin',  'Super Admin (Diretor)'
    DEPT_MANAGER = 'dept_manager', 'Gestor de Departamento'
    TEAM_MEMBER  = 'team_member',  'Utilizador (Equipa)'


# ── Permission Bitmask ────────────────────────────────────────

class PermBit(models.IntegerChoices):
    READ    = 1,  'Leitura'
    WRITE   = 2,  'Escrita'
    EXECUTE = 4,  'Executar'
    DELETE  = 8,  'Eliminar'
    FULL    = 15, 'Controlo Total'


# ── Company ─────────────────────────────────────────────────

class Company(models.Model):
    """
    Multi-tenant: Each company is completely isolated.
    Only SUPER_ADMIN can create companies.
    Storage quota is enforced at company level.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=120, unique=True)
    slug        = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    
    # Quota management — updated atomically on every file write
    quota_bytes = models.BigIntegerField(default=10 * 1024 * 1024 * 1024)  # 10 GB default
    used_bytes  = models.BigIntegerField(default=0)

    created_at  = models.DateTimeField(auto_now_add=True)
    created_by  = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='companies_created',
    )
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def quota_pct(self):
        if not self.quota_bytes:
            return 100
        return round((self.used_bytes / self.quota_bytes) * 100, 1)

    @property
    def quota_exceeded(self):
        return self.used_bytes >= self.quota_bytes


# ── Department ────────────────────────────────────────────────

class Department(models.Model):
    """
    Organisational unit within a company.
    No quota — quota is at Company level.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company     = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments')
    name        = models.CharField(max_length=120)
    slug        = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    color       = models.CharField(max_length=7,  default='#3b82f6')   # Hex for UI
    icon        = models.CharField(max_length=30, default='building')   # Lucide icon name

    created_at  = models.DateTimeField(auto_now_add=True)
    created_by  = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL,
        related_name='departments_created',
    )
    is_active   = models.BooleanField(default=True)

    class Meta:
        ordering = ['company', 'name']
        unique_together = [['company', 'name'], ['company', 'slug']]

    def __str__(self):
        return f'{self.company.name} - {self.name}'


# ── User Manager ──────────────────────────────────────────────

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault('role', Role.SUPER_ADMIN)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


# ── User ──────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user with embedded role, company and department.
    
    Multi-tenant: Every user belongs to ONE company.
    SUPER_ADMIN has no company (can manage all companies).
    Company users belong to ONE department within their company.
    Fine-grained file permissions live in UserFilePermission.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email       = models.EmailField(unique=True)
    first_name  = models.CharField(max_length=80)
    last_name   = models.CharField(max_length=80)

    role        = models.CharField(max_length=20, choices=Role.choices, default=Role.TEAM_MEMBER)
    company     = models.ForeignKey(
        Company, null=True, blank=True,
        on_delete=models.CASCADE, related_name='users',
    )
    department  = models.ForeignKey(
        Department, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='members',
    )
    created_by  = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_users',
    )

    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f'{self.full_name} <{self.email}> [{self.role}]'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def initials(self):
        return ''.join(n[0].upper() for n in [self.first_name, self.last_name] if n)

    @property
    def is_super_admin(self):  return self.role == Role.SUPER_ADMIN
    @property
    def is_dept_manager(self): return self.role == Role.DEPT_MANAGER
    @property
    def is_team_member(self):  return self.role == Role.TEAM_MEMBER


# ── Cross-Department Access ───────────────────────────────────

class CrossDeptPermission(models.Model):
    """
    Company admin grants manager of DeptA read/write access to DeptB within the same company.
    SUPER_ADMIN can also grant cross-department access.
    Stored as bitmask: READ=1, READ+WRITE=3, FULL=15.

    Checked by PermissionService BEFORE UserFilePermission.
    Applies to entire target_department tree.
    """
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    manager           = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='cross_dept_grants',
        limit_choices_to={'role': Role.DEPT_MANAGER},
    )
    target_department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='cross_accesses',
    )
    permission_mask   = models.IntegerField(default=PermBit.READ)
    granted_by        = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='cross_dept_granted',
    )
    granted_at        = models.DateTimeField(auto_now_add=True)
    expires_at        = models.DateTimeField(null=True, blank=True)
    is_active         = models.BooleanField(default=True)
    notes             = models.TextField(blank=True)

    class Meta:
        unique_together = ('manager', 'target_department')

    def __str__(self):
        return f'{self.manager.email} → {self.target_department.name} [{self.permission_mask}]'
