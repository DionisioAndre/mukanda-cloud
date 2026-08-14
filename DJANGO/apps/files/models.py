import uuid
import os
from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, Q, F
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models.functions import Now


class NodeType(models.TextChoices):
    FOLDER = 'folder', 'Pasta'
    FILE = 'file', 'Ficheiro'


class FileSystemNode(models.Model):
    """
    Unified tree node for folders and files.
    
    Multi-tenant: Each node belongs to a company.
    One root folder per company (parent=None, name=company.slug).
    Departments are subfolders within the company root.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=6, choices=NodeType.choices, default=NodeType.FOLDER)

    # ── Tree relations ──
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='children'
    )
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='nodes'
    )
    department = models.ForeignKey(
        'accounts.Department', null=True, blank=True, on_delete=models.SET_NULL, 
        related_name='nodes'
    )
    materialized_path = models.CharField(max_length=2048, db_index=True, blank=True)

    # ── File metadata ──
    # Use Azure Files storage if configured, otherwise use local storage
    storage_backend = None
    if hasattr(settings, 'AZURE_FILES_STORAGE'):
        storage_backend = settings.AZURE_FILES_STORAGE
    
    file_field = models.FileField(
        upload_to='files/%Y/%m/', 
        null=True, 
        blank=True,
        storage=storage_backend
    )
    size_bytes = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, blank=True)
    extension = models.CharField(max_length=20, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    
    # ── Document content (for rich text editor) ──
    content = models.TextField(blank=True, help_text="HTML content for document editor")

    # ── Metadata ──
    tags = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    is_starred = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    # ── Ownership ──
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='nodes_created'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='nodes_updated'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Soft delete ──
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='nodes_deleted'
    )

    class Meta:
        ordering = ['node_type', 'name']
        indexes = [
            models.Index(fields=['company', 'materialized_path']),
            models.Index(fields=['parent', 'name']),
            models.Index(fields=['node_type', 'company']),
            models.Index(fields=['is_deleted', 'company']),
            models.Index(fields=['company', 'name']),
            models.Index(fields=['department', 'materialized_path'])
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'name', 'company'],
                condition=models.Q(is_deleted=False),
                name='unique_name_in_parent'
            )
        ]

    def __str__(self):
        return f'[{self.node_type}] {self.materialized_path}'

    def clean(self):
        invalid_chars = ['/', '\\', '\0']
        if any(char in self.name for char in invalid_chars):
            raise ValidationError("Nome inválido.")

        if self.parent:
            if self.parent.company_id != self.company_id:
                raise ValidationError("O pai e o item devem pertencer à mesma empresa.")
            if self.parent.node_type == NodeType.FILE:
                raise ValidationError("Não é possível criar itens dentro de um ficheiro.")

        if self.node_type == NodeType.FOLDER and self.file_field:
            raise ValidationError("Uma pasta não pode possuir ficheiro.")

        if self.node_type == NodeType.FILE and not self.file_field:
            raise ValidationError("Um ficheiro precisa de conteúdo.")

        if self.pk and self.node_type == NodeType.FILE and self.children.exists():
            raise ValidationError("Um ficheiro não pode conter filhos.")

    def save(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        old_path = None
        if self.pk:
            old_path = FileSystemNode.objects.filter(pk=self.pk).values_list('materialized_path', flat=True).first()

        self.materialized_path = self._build_path()

        if user:
            self.updated_by = user
            if not self.pk:
                self.created_by = user

        if self.node_type == NodeType.FILE:
            _, ext = os.path.splitext(self.name)
            self.extension = ext.lower().lstrip('.') if ext else ''
            if self.file_field:
                self.size_bytes = self.file_field.size

        super().save(*args, **kwargs)

        if old_path and old_path != self.materialized_path and self.node_type == NodeType.FOLDER:
            for child in self.children.all():
                child._update_children_paths(old_path, self.materialized_path)

    def _update_children_paths(self, old_path, new_path):
        self.materialized_path = self.materialized_path.replace(old_path, new_path, 1)
        FileSystemNode.objects.filter(pk=self.pk).update(
            materialized_path=self.materialized_path,
            updated_at=timezone.now()
        )
        for child in self.children.all():
            child._update_children_paths(old_path, new_path)

    def soft_delete(self, actor):
        FileSystemNode.objects.filter(pk=self.pk).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            deleted_by=actor,
            updated_at=timezone.now()
        )
        for child in self.children.filter(is_deleted=False):
            child.soft_delete(actor)

    @property
    def total_size_bytes(self):
        if self.node_type == NodeType.FILE:
            return self.size_bytes
        result = FileSystemNode.objects.filter(
            materialized_path__startswith=self.materialized_path,
            node_type=NodeType.FILE,
            is_deleted=False
        ).aggregate(total=Sum('size_bytes'))
        return result['total'] or 0

    @property
    def size_display(self):
        size = self.total_size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def _build_path(self):
        if self.parent_id is None:
            company_slug = self.company.slug if self.company else 'no-company'
            return f'/{company_slug}/{self.name}'
        return f'{self.parent.materialized_path.rstrip("/")}/{self.name}'

    def get_ancestors(self):
        chain = []
        node = self.parent
        while node:
            chain.insert(0, node)
            node = node.parent
        return chain

    def get_breadcrumbs(self):
        crumbs = [{'id': str(n.id), 'name': n.name, 'path': n.materialized_path} for n in self.get_ancestors()]
        crumbs.append({'id': str(self.id), 'name': self.name, 'path': self.materialized_path, 'current': True})
        return crumbs


class UserFilePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='file_permissions')
    node = models.ForeignKey(FileSystemNode, on_delete=models.CASCADE, related_name='user_permissions')
    permission_mask = models.IntegerField(default=1)
    assigned_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='permissions_assigned'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'node')
        ordering = ['-assigned_at']
        indexes = [models.Index(fields=['user', 'node', 'is_active'])]

    def __str__(self):
        return f'{self.user.email} → {self.node.name} [{self.permission_mask}]'

    def can_read(self): return bool(self.permission_mask & 1)
    def can_write(self): return bool(self.permission_mask & 2)
    def can_execute(self): return bool(self.permission_mask & 4)
    def can_delete(self): return bool(self.permission_mask & 8)


class FileLock(models.Model):
    """
    System-level file locking mechanism.
    Prevents concurrent edits by multiple users (e.g., AutoCAD).
    Uses database-level locking to prevent race conditions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    node = models.ForeignKey(
        FileSystemNode, on_delete=models.CASCADE, related_name='locks',
        limit_choices_to={'node_type': NodeType.FILE}
    )
    locked_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='file_locks'
    )
    locked_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Lock metadata
    client_info = models.JSONField(default=dict, blank=True, help_text="Client identifier (hostname, IP, etc.)")
    lock_type = models.CharField(
        max_length=20,
        choices=[
            ('exclusive', 'Exclusive Lock'),
            ('shared', 'Shared Lock'),
        ],
        default='exclusive'
    )

    class Meta:
        ordering = ['-locked_at']
        indexes = [
            models.Index(fields=['node', 'is_active']),
            models.Index(fields=['locked_by', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['node'],
                condition=models.Q(is_active=True),
                name='active_lock_per_file'
            )
        ]

    def __str__(self):
        return f'Lock on {self.node.name} by {self.locked_by}'

    @classmethod
    def acquire_lock(cls, node, user, lock_type='exclusive', expires_in_minutes=30, client_info=None):
        """
        Acquire a file lock atomically to prevent race conditions.
        Uses SELECT FOR UPDATE to ensure no two users can acquire lock simultaneously.
        
        Args:
            node: FileSystemNode instance
            user: User instance acquiring the lock
            lock_type: 'exclusive' or 'shared'
            expires_in_minutes: Lock expiration time
            client_info: Dict with client identification info
            
        Returns:
            FileLock instance if successful
            
        Raises:
            ValidationError: If file is already locked
        """
        with transaction.atomic():
            # Lock the row to prevent concurrent acquisitions
            node = FileSystemNode.objects.select_for_update().get(pk=node.pk)
            
            # Check if there's an active lock
            active_lock = cls.objects.filter(
                node=node,
                is_active=True
            ).exclude(
                expires_at__lt=timezone.now()
            ).first()
            
            if active_lock:
                # Check if lock is expired
                if active_lock.expires_at and active_lock.expires_at < timezone.now():
                    active_lock.is_active = False
                    active_lock.save()
                else:
                    raise ValidationError(
                        f"File is locked by {active_lock.locked_by} since {active_lock.locked_at}"
                    )
            
            # Create new lock
            expires_at = timezone.now() + timezone.timedelta(minutes=expires_in_minutes) if expires_in_minutes else None
            
            lock = cls.objects.create(
                node=node,
                locked_by=user,
                lock_type=lock_type,
                expires_at=expires_at,
                client_info=client_info or {}
            )
            
            # Update node lock status
            node.is_locked = True
            node.save(update_fields=['is_locked'])
            
            return lock

    def release_lock(self):
        """Release the lock."""
        with transaction.atomic():
            self.is_active = False
            self.save(update_fields=['is_active'])
            
            # Update node lock status if no other active locks
            if not FileLock.objects.filter(
                node=self.node,
                is_active=True
            ).exists():
                self.node.is_locked = False
                self.node.save(update_fields=['is_locked'])

    def refresh_lock(self, additional_minutes=30):
        """Extend the lock expiration time."""
        if self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=additional_minutes)
            self.save(update_fields=['expires_at'])

    @property
    def is_expired(self):
        """Check if lock is expired."""
        return self.expires_at and self.expires_at < timezone.now()

    @classmethod
    def cleanup_expired_locks(cls):
        """Clean up expired locks (should be run periodically)."""
        expired_locks = cls.objects.filter(
            is_active=True,
            expires_at__lt=timezone.now()
        )
        
        for lock in expired_locks:
            lock.is_active = False
            lock.save(update_fields=['is_active'])
            
            # Update node lock status
            if not cls.objects.filter(
                node=lock.node,
                is_active=True
            ).exists():
                lock.node.is_locked = False
                lock.node.save(update_fields=['is_locked'])
        
        return expired_locks.count()


class GroupFilePermission(models.Model):
    """
    Group-based ACL permissions.
    Allows permissions to be assigned to groups of users.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        'accounts.Department', on_delete=models.CASCADE, related_name='group_file_permissions',
        null=True, blank=True
    )
    node = models.ForeignKey(FileSystemNode, on_delete=models.CASCADE, related_name='group_permissions')
    permission_mask = models.IntegerField(default=1)
    assigned_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='group_permissions_assigned'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('group', 'node')
        ordering = ['-assigned_at']
        indexes = [models.Index(fields=['group', 'node', 'is_active'])]

    def __str__(self):
        return f'{self.group.name if self.group else "No Group"} → {self.node.name} [{self.permission_mask}]'

    def can_read(self): return bool(self.permission_mask & 1)
    def can_write(self): return bool(self.permission_mask & 2)
    def can_execute(self): return bool(self.permission_mask & 4)
    def can_delete(self): return bool(self.permission_mask & 8)