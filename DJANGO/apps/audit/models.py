"""
backend/apps/audit/models.py
Immutable audit log — append-only, never updated or deleted.
Records WHO did WHAT to WHICH file, WHEN and from WHERE.
"""
import uuid
from django.db import models


class AuditAction:
    FILE_VIEW    = 'file_view'
    FILE_CREATE  = 'file_create'
    FILE_EDIT    = 'file_edit'
    FILE_DELETE  = 'file_delete'
    FILE_RESTORE = 'file_restore'
    FILE_DOWNLOAD= 'file_download'
    FOLDER_CREATE= 'folder_create'
    FOLDER_DELETE= 'folder_delete'
    PERM_GRANT   = 'perm_grant'
    PERM_REVOKE  = 'perm_revoke'
    LOGIN        = 'login'
    LOGOUT       = 'logout'
    LOGIN_FAILED = 'login_failed'
    PERM_DENIED  = 'perm_denied'
    USER_CREATE  = 'user_create'
    DEPT_CREATE  = 'dept_create'

    CHOICES = [
        (FILE_VIEW,     'Visualizou ficheiro'),
        (FILE_CREATE,   'Criou ficheiro'),
        (FILE_EDIT,     'Editou ficheiro'),
        (FILE_DELETE,   'Eliminou ficheiro'),
        (FILE_RESTORE,  'Restaurou ficheiro'),
        (FILE_DOWNLOAD, 'Descarregou ficheiro'),
        (FOLDER_CREATE, 'Criou pasta'),
        (FOLDER_DELETE, 'Eliminou pasta'),
        (PERM_GRANT,    'Concedeu permissão'),
        (PERM_REVOKE,   'Revogou permissão'),
        (LOGIN,         'Iniciou sessão'),
        (LOGOUT,        'Terminou sessão'),
        (LOGIN_FAILED,  'Falha no login'),
        (PERM_DENIED,   'Acesso negado'),
        (USER_CREATE,   'Criou utilizador'),
        (DEPT_CREATE,   'Criou departamento'),
    ]


class AuditLog(models.Model):
    """
    Immutable audit record.
    Snapshots (user_email, node_path) preserved even if originals deleted.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who
    user        = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='audit_logs',
    )
    user_email  = models.EmailField(blank=True)      # snapshot
    user_role   = models.CharField(max_length=20, blank=True)
    company     = models.ForeignKey(
        'accounts.Company', null=True, on_delete=models.SET_NULL, related_name='audit_logs',
    )
    department  = models.ForeignKey(
        'accounts.Department', null=True, on_delete=models.SET_NULL, related_name='audit_logs',
    )
    dept_name   = models.CharField(max_length=120, blank=True)  # snapshot

    # What
    action      = models.CharField(max_length=20, choices=AuditAction.CHOICES)
    result      = models.CharField(
        max_length=10,
        choices=[('success','Sucesso'), ('denied','Negado'), ('error','Erro')],
        default='success',
    )
    reason      = models.CharField(max_length=255, blank=True)

    # Target
    node        = models.ForeignKey(
        'files.FileSystemNode', null=True, on_delete=models.SET_NULL, related_name='audit_logs',
    )
    node_name   = models.CharField(max_length=255, blank=True)   # snapshot
    node_path   = models.CharField(max_length=2048, blank=True)  # snapshot

    # Context
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True)
    extra       = models.JSONField(default=dict, blank=True)

    # When
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['node', 'timestamp']),
            models.Index(fields=['action', 'result']),
            models.Index(fields=['department', 'timestamp']),
        ]

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.user_email} {self.action} → {self.result}'

    @classmethod
    def record(cls, *, user, action, node=None, result='success',
               reason='', ip_address=None, user_agent='', extra=None):
        """
        Factory — creates immutable audit record. Never updates.

        Example:
            AuditLog.record(
                user=request.user,
                action=AuditAction.FILE_VIEW,
                node=node_obj,
                ip_address=request.client_ip,
                user_agent=request.client_ua,
            )
        """
        return cls.objects.create(
            user=user,
            user_email=user.email if user else '',
            user_role=user.role if user else '',
            company=user.company if user and hasattr(user, 'company') else None,
            department=user.department if user and hasattr(user, 'department') else None,
            dept_name=user.department.name if user and user.department else '',
            action=action,
            result=result,
            reason=reason,
            node=node,
            node_name=node.name if node else '',
            node_path=node.materialized_path if node else '',
            ip_address=ip_address,
            user_agent=user_agent,
            extra=extra or {},
        )
