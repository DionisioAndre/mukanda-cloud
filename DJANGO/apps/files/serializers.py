from rest_framework import serializers
from django.utils import timezone

from .models import (
    FileSystemNode,
    UserFilePermission,
    FileLock,
    GroupFilePermission
)

from core.permissions import Bit


class FileSystemNodeSerializer(serializers.ModelSerializer):
    size_display = serializers.ReadOnlyField()
    children_count = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    company_name = serializers.ReadOnlyField(source='company.name')
    dept_name = serializers.ReadOnlyField(source='department.name')
    type = serializers.CharField(
        source="node_type",
        read_only=True
    )

    class Meta:
        model = FileSystemNode
        fields = [
            'id', 'name', 'type', 'node_type', 'parent', 'company', 'company_name', 
            'department', 'dept_name', 'materialized_path', 'file_field', 'size_bytes', 
            'size_display', 'mime_type', 'extension', 'tags', 'description', 'content',
            'is_starred', 'is_locked', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name', 'created_at', 'updated_at',
            'children_count', 'breadcrumbs', 'file_url',
        ]
        read_only_fields = [
            'id', 'type', 'materialized_path',
            'created_by', 'updated_by', 'created_at', 'updated_at',
            'extension', 'size_bytes',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        parent = attrs.get('parent')
        node_type = attrs.get('node_type')
        file_field = attrs.get('file_field')

        # Impedir alterar tipo depois de criado
        if self.instance:
            if 'node_type' in attrs and attrs['node_type'] != self.instance.node_type:
                raise serializers.ValidationError("Não é permitido alterar o tipo do nó.")
            node_type = self.instance.node_type

        # Pai não pode ser ficheiro
        if parent:
            if parent.node_type == 'file':
                raise serializers.ValidationError("Não é possível criar itens dentro de um ficheiro.")
            
            # Mesma empresa
            if self.instance and parent.company_id != self.instance.company_id:
                raise serializers.ValidationError("O pai pertence a outra empresa.")

        # Pasta não pode ter ficheiro
        if node_type == 'folder' and file_field:
            raise serializers.ValidationError("Uma pasta não pode possuir ficheiro.")

        # Ficheiro precisa upload na criação
        if node_type == 'file' and not file_field and not self.instance:
            raise serializers.ValidationError("Um ficheiro necessita de upload.")

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        # Get company - either from user or from request data (for SUPER_ADMIN)
        company = validated_data.get('company') or getattr(user, 'company', None)

        if not company:
            raise serializers.ValidationError(
                {"company": "Empresa é obrigatória. Utilizador não tem empresa associada."}
            )

        # Remove fields that should be set by backend
        validated_data.pop('company', None)
        validated_data.pop('created_by', None)
        validated_data.pop('updated_by', None)

        try:
            obj = FileSystemNode(
                **validated_data,
                company=company,
                created_by=user,
                updated_by=user
            )
            obj.full_clean()
            obj.save()
            return obj
        except Exception as e:
            raise serializers.ValidationError(f"Erro ao criar nó: {str(e)}")

    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if user:
            instance.updated_by = user

        instance.full_clean()
        instance.save()
        return instance

    def get_children_count(self, obj):
        if obj.node_type == 'folder':
            return obj.children.filter(is_deleted=False).count()
        return 0

    def get_breadcrumbs(self, obj):
        request = self.context.get('request')
        if request and request.method == "GET":
            return obj.get_breadcrumbs()
        return None

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj):
        return obj.updated_by.full_name if obj.updated_by else None

    def get_file_url(self, obj):
        if obj.node_type != 'file' or obj.is_deleted or not obj.file_field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.file_field.url) if request else obj.file_field.url


class UserFilePermissionSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.full_name')
    node_name = serializers.ReadOnlyField(source='node.name')
    assigned_by_name = serializers.ReadOnlyField(source='assigned_by.full_name')
    perm_labels = serializers.SerializerMethodField()

    class Meta:
        model = UserFilePermission
        fields = [
            'id', 'user', 'user_name', 'node', 'node_name',
            'permission_mask', 'perm_labels', 'assigned_by',
            'assigned_by_name', 'assigned_at', 'expires_at', 'is_active',
        ]
        read_only_fields = ['id', 'assigned_at', 'assigned_by']
        extra_kwargs = {
            'user': {'required': True},
            'node': {'required': True},
        }

    def validate_permission_mask(self, value):
        allowed = 1 | 2 | 4 | 8
        if value <= 0 or value & ~allowed:
            raise serializers.ValidationError("Permissão inválida.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data['assigned_by'] = request.user
        # Use get_or_create to handle existing permissions
        return UserFilePermission.objects.get_or_create(
            user=validated_data['user'],
            node=validated_data['node'],
            defaults={
                'permission_mask': validated_data.get('permission_mask', 1),
                'assigned_by': validated_data.get('assigned_by'),
                'expires_at': validated_data.get('expires_at'),
                'is_active': True
            }
        )[0]

    def get_perm_labels(self, obj):
        return Bit.labels(obj.permission_mask)


class FileLockSerializer(serializers.ModelSerializer):
    locked_by_name = serializers.ReadOnlyField(source='locked_by.full_name')
    node_name = serializers.ReadOnlyField(source='node.name')
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = FileLock
        fields = [
            'id', 'node', 'node_name', 'locked_by', 'locked_by_name',
            'locked_at', 'expires_at', 'is_active', 'is_expired',
            'time_remaining', 'lock_type', 'client_info'
        ]
        read_only_fields = ['id', 'locked_at', 'locked_by']

    def get_time_remaining(self, obj):
        if obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return None


class FileLockAcquireSerializer(serializers.Serializer):
    """Serializer for acquiring a file lock."""
    lock_type = serializers.ChoiceField(
        choices=['exclusive', 'shared'],
        default='exclusive'
    )
    expires_in_minutes = serializers.IntegerField(default=30, min_value=1, max_value=1440)
    client_info = serializers.JSONField(required=False, default=dict)


class GroupFilePermissionSerializer(serializers.ModelSerializer):
    group_name = serializers.ReadOnlyField(source='group.name')
    node_name = serializers.ReadOnlyField(source='node.name')
    assigned_by_name = serializers.ReadOnlyField(source='assigned_by.full_name')
    perm_labels = serializers.SerializerMethodField()

    class Meta:
        model = GroupFilePermission
        fields = [
            'id', 'group', 'group_name', 'node', 'node_name',
            'permission_mask', 'perm_labels', 'assigned_by',
            'assigned_by_name', 'assigned_at', 'expires_at', 'is_active',
        ]
        read_only_fields = ['id', 'assigned_at', 'assigned_by']
        extra_kwargs = {
            'group': {'required': False, 'allow_null': True},
            'node': {'required': True},
        }

    def validate_permission_mask(self, value):
        allowed = 1 | 2 | 4 | 8
        if value <= 0 or value & ~allowed:
            raise serializers.ValidationError("Permissão inválida.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data['assigned_by'] = request.user
        return GroupFilePermission.objects.get_or_create(
            group=validated_data.get('group'),
            node=validated_data['node'],
            defaults={
                'permission_mask': validated_data.get('permission_mask', 1),
                'assigned_by': validated_data.get('assigned_by'),
                'expires_at': validated_data.get('expires_at'),
                'is_active': True
            }
        )[0]

    def get_perm_labels(self, obj):
        return Bit.labels(obj.permission_mask)


class PresignedURLSerializer(serializers.Serializer):
    """Serializer for presigned URL requests."""
    file_path = serializers.CharField(required=True)
    expires_in_minutes = serializers.IntegerField(default=60, min_value=1, max_value=1440)
    max_file_size = serializers.IntegerField(required=False, default=1024 * 1024 * 1024)
    content_disposition = serializers.CharField(required=False)


class FileSystemNodePathSerializer(serializers.Serializer):
    """Serializer for path-based navigation."""
    path = serializers.CharField(required=False, help_text="Materialized path (e.g., /company/projects/)")
    company = serializers.UUIDField(required=False)
    parent = serializers.UUIDField(required=False)