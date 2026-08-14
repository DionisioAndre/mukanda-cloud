"""
backend/apps/accounts/views.py
Auth and user management endpoints.
"""
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import transaction

from .models import User, Department, Company, CrossDeptPermission, Role
from .serializers import (
    UserSerializer, CreateUserSerializer, DepartmentSerializer, CompanySerializer, 
    CrossDeptPermSerializer, CustomTokenObtainPairSerializer,
)
from core.permissions import IsSuperAdmin, IsDeptManagerOrAbove
from apps.audit.models import AuditLog, AuditAction


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/token/
    Returns JWT access + refresh + embedded user context.
    On success, logs AuditAction.LOGIN.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Log successful login
            try:
                user = User.objects.get(email=request.data.get('email', ''))
                AuditLog.record(
                    user=user, action=AuditAction.LOGIN,
                    ip_address=getattr(request, 'client_ip', None),
                    user_agent=getattr(request, 'client_ua', ''),
                )
            except User.DoesNotExist:
                pass
        return response


class CompanyViewSet(viewsets.ModelViewSet):
    """
    CRUD for companies — restricted to Super Admin only.
    Only SUPER_ADMIN can create, update, or delete companies.
    DEPT_MANAGER can only list their own company.
    """
    serializer_class   = CompanySerializer
    permission_classes = [IsSuperAdmin]
    queryset           = Company.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action == 'list':
            # Allow authenticated users to list companies (filtered by their company)
            return [IsAuthenticated()]
        return [IsSuperAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return Company.objects.filter(is_active=True)
        # DEPT_MANAGER and TEAM_MEMBER can only see their own company
        if user.company:
            return Company.objects.filter(id=user.company.id, is_active=True)
        return Company.objects.none()

    def perform_create(self, serializer):
        company = serializer.save(created_by=self.request.user)
        AuditLog.record(
            user=self.request.user, action=AuditAction.DEPT_CREATE,
            extra={'company_id': str(company.id), 'name': company.name},
        )


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for departments — restricted to Super Admin and Company Admins.
    Gestores can only GET their own department.
    """
    serializer_class   = DepartmentSerializer
    queryset           = Department.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsSuperAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        dept = serializer.save(created_by=self.request.user)
        AuditLog.record(
            user=self.request.user, action=AuditAction.DEPT_CREATE,
            extra={'dept_id': str(dept.id), 'name': dept.name},
        )

    def get_queryset(self):
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return Department.objects.filter(is_active=True)
        # Company isolation: users see only departments in their company
        return Department.objects.filter(company=user.company, is_active=True)


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD for users.
    - Super Admin: manages all users across all companies
    - Dept Manager: manages only users in their company
    - Team Member: read-only (own profile)
    """
    permission_classes = [IsDeptManagerOrAbove]

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateUserSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return User.objects.filter(is_active=True).select_related('company', 'department')
        # Company isolation: managers see only users in their company
        return User.objects.filter(company=user.company, is_active=True).select_related('company', 'department')

    @transaction.atomic
    def perform_create(self, serializer):
        user = serializer.save()
        AuditLog.record(
            user=self.request.user, action=AuditAction.USER_CREATE,
            extra={'new_user_id': str(user.id), 'role': user.role},
        )


class CrossDeptPermViewSet(viewsets.ModelViewSet):
    """Cross-department access grants — Super Admin only."""
    serializer_class   = CrossDeptPermSerializer
    permission_classes = [IsSuperAdmin]
    queryset           = CrossDeptPermission.objects.select_related('manager', 'target_department', 'granted_by')

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)


class MeView(APIView):
    """GET /api/auth/me/ — returns current user profile."""
    def get(self, request):
        return Response(UserSerializer(request.user).data)
