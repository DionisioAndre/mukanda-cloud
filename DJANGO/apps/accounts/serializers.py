"""
backend/apps/accounts/serializers.py
Custom JWT serializer embeds role + department in token payload.
This eliminates extra API calls to fetch user context after login.
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Department, Company, CrossDeptPermission, Role


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends JWT payload with user context.
    Frontend reads these claims from the decoded token
    to build the role-aware UI without extra API calls.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Embed in JWT payload — available client-side after decode
        token['email']      = user.email
        token['full_name']  = user.full_name
        token['role']       = user.role
        token['company_id'] = str(user.company_id) if user.company_id else None
        token['company_name'] = user.company.name if user.company else None
        token['dept_id']    = str(user.department_id) if user.department_id else None
        token['dept_name']  = user.department.name    if user.department    else None
        token['dept_color'] = user.department.color   if user.department    else None
        token['initials']   = user.initials
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Add user data to response body as well (convenience)
        data['user'] = {
            'id':       str(self.user.id),
            'email':    self.user.email,
            'name':     self.user.full_name,
            'role':     self.user.role,
            'initials': self.user.initials,
            'company_id': str(self.user.company_id) if self.user.company_id else None,
            'company_name': self.user.company.name if self.user.company else None,
            'dept_id':  str(self.user.department_id) if self.user.department_id else None,
            'dept_name':self.user.department.name    if self.user.department    else None,
        }
        return data


class CompanySerializer(serializers.ModelSerializer):
    quota_pct      = serializers.ReadOnlyField()
    quota_exceeded = serializers.ReadOnlyField()
    user_count     = serializers.SerializerMethodField()
    dept_count     = serializers.SerializerMethodField()

    class Meta:
        model  = Company
        fields = [
            'id', 'name', 'slug', 'description',
            'quota_bytes', 'used_bytes', 'quota_pct', 'quota_exceeded',
            'created_at', 'is_active', 'user_count', 'dept_count',
        ]
        read_only_fields = ['id', 'created_at', 'used_bytes']

    def get_user_count(self, obj):
        return obj.users.filter(is_active=True).count()

    def get_dept_count(self, obj):
        return obj.departments.filter(is_active=True).count()


class DepartmentSerializer(serializers.ModelSerializer):
    company_name   = serializers.ReadOnlyField(source='company.name')
    member_count   = serializers.SerializerMethodField()

    class Meta:
        model  = Department
        fields = [
            'id', 'company', 'company_name', 'name', 'slug', 'description', 
            'color', 'icon', 'created_at', 'is_active', 'member_count',
        ]
        read_only_fields = ['id', 'created_at']

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def validate(self, data):
        request = self.context.get('request')
        actor = request.user if request else None

        # SUPER_ADMIN can create departments in any company
        if actor and actor.role == Role.SUPER_ADMIN:
            if not data.get('company'):
                raise serializers.ValidationError('Empresa é obrigatória.')
            return data

        # DEPT_MANAGER can only create departments in their own company
        if actor and actor.role == Role.DEPT_MANAGER:
            if data.get('company') != actor.company:
                raise serializers.ValidationError(
                    'Gestores só podem criar departamentos na sua empresa.'
                )

        return data


class UserSerializer(serializers.ModelSerializer):
    full_name   = serializers.ReadOnlyField()
    initials    = serializers.ReadOnlyField()
    company_id  = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    dept_id     = serializers.SerializerMethodField()
    dept_name   = serializers.SerializerMethodField()
    dept_color  = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'initials', 'role', 'company', 'company_id', 'company_name', 
            'department', 'dept_id', 'dept_name', 'dept_color',
            'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']

    def get_company_id(self, obj):
        return str(obj.company.id) if obj.company else None

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_dept_id(self, obj):
        return str(obj.department.id) if obj.department else None

    def get_dept_name(self, obj):
        return obj.department.name if obj.department else None

    def get_dept_color(self, obj):
        return obj.department.color if obj.department else None


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model  = User
        fields = ['email', 'first_name', 'last_name', 'role', 'company', 'department', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        request  = self.context['request']
        user = User(**validated_data)
        user.set_password(password)
        user.created_by = request.user
        user.save()
        return user

    def validate(self, data):
        request = self.context['request']
        actor   = request.user

        # Validate that department belongs to the selected company
        if data.get('company') and data.get('department'):
            if data.get('department').company != data.get('company'):
                raise serializers.ValidationError(
                    'Departamento deve pertencer à empresa selecionada.'
                )

        # SUPER_ADMIN can create users in any company
        if actor.role == Role.SUPER_ADMIN:
            if not data.get('company'):
                raise serializers.ValidationError('Empresa é obrigatória.')
            return data

        # DEPT_MANAGER can only create TEAM_MEMBERs in their own company and dept
        if actor.role == Role.DEPT_MANAGER:
            if data.get('role') != Role.TEAM_MEMBER:
                raise serializers.ValidationError(
                    'Gestores só podem criar utilizadores da equipa.'
                )
            if data.get('company') != actor.company:
                raise serializers.ValidationError(
                    'Gestores só podem criar utilizadores na sua empresa.'
                )
            if data.get('department') and data.get('department').company != actor.company:
                raise serializers.ValidationError(
                    'Departamento deve pertencer à mesma empresa.'
                )

        return data


class CrossDeptPermSerializer(serializers.ModelSerializer):
    manager_name    = serializers.ReadOnlyField(source='manager.full_name')
    target_dept_name= serializers.ReadOnlyField(source='target_department.name')
    perm_labels     = serializers.SerializerMethodField()

    class Meta:
        model  = CrossDeptPermission
        fields = [
            'id', 'manager', 'manager_name', 'target_department', 'target_dept_name',
            'permission_mask', 'perm_labels', 'granted_at', 'expires_at', 'is_active', 'notes',
        ]
        read_only_fields = ['id', 'granted_at']

    def get_perm_labels(self, obj):
        from core.permissions import Bit
        return Bit.labels(obj.permission_mask)
