"""backend/apps/audit/views.py"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from .models import AuditLog
from apps.accounts.models import Role
from core.permissions import IsDeptManagerOrAbove


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AuditLog
        fields = [
            'id', 'user_email', 'user_role', 'dept_name',
            'action', 'result', 'reason',
            'node_name', 'node_path',
            'ip_address', 'timestamp',
        ]
        read_only_fields = fields


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit log — Gestores and Admins only."""
    serializer_class   = AuditLogSerializer
    permission_classes = [IsDeptManagerOrAbove]

    def get_queryset(self):
        user = self.request.user
        qs   = AuditLog.objects.all()

        if user.role != Role.SUPER_ADMIN:
            # Filter by company for multi-tenancy
            if user.company:
                qs = qs.filter(company=user.company)
            else:
                # If user has no company, return empty
                qs = qs.none()

        # Filtering
        params = self.request.query_params
        if params.get('action'):  qs = qs.filter(action=params['action'])
        if params.get('result'):  qs = qs.filter(result=params['result'])
        if params.get('user_id'): qs = qs.filter(user_id=params['user_id'])

        return qs[:500]  # Limit to last 500 records
