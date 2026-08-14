from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import (
    Role,
    CrossDeptPermission,
    Company
)

from apps.files.models import (
    UserFilePermission
)



# ==========================================================
# BITMASK
# ==========================================================

class Bit:

    READ = 1          # Ler
    WRITE = 2         # Criar/editar
    EXECUTE = 4       # Abrir/executar
    DELETE = 8        # Apagar
    MANAGE = 16       # Gerir permissões

    FULL = 31         # Todas


    @staticmethod
    def labels(mask):

        result = []


        if mask & Bit.READ:
            result.append("Leitura")


        if mask & Bit.WRITE:
            result.append("Escrita")


        if mask & Bit.EXECUTE:
            result.append("Executar")


        if mask & Bit.DELETE:
            result.append("Eliminar")


        if mask & Bit.MANAGE:
            result.append("Gerir permissões")


        return result or ["Nenhuma"]





# ==========================================================
# SERVICE
# ==========================================================

class PermissionService:


    @staticmethod
    def resolve_mask(user, node):
        # Company isolation check - users can only access nodes in their company
        if user.role != Role.SUPER_ADMIN:
            if user.company_id != node.company_id:
                return 0

        # ADMIN TEM TUDO
        if user.role == Role.SUPER_ADMIN:
            return Bit.FULL

        # GESTOR
        if user.role == Role.DEPT_MANAGER:
            # Manager can access files in their department OR files without department (company-wide)
            if user.department_id == node.department_id or node.department_id is None:
                return Bit.FULL

            cross = CrossDeptPermission.objects.filter(
                manager=user,
                target_department_id=node.department_id,
                is_active=True
            ).filter(
                Q(expires_at__isnull=True)
                |
                Q(expires_at__gt=timezone.now())
            ).first()

            if cross:
                return cross.permission_mask

            return 0

        # DONO DO FICHEIRO
        if node.created_by_id == user.id:
            return Bit.FULL

        # UTILIZADOR NORMAL
        explicit = PermissionService._get_permission(
            user,
            node
        )

        if explicit is not None:
            return explicit

        return 0





    @staticmethod
    def _get_permission(user,node):


        perm = UserFilePermission.objects.filter(

            user=user,

            node=node,

            is_active=True

        ).filter(

            Q(expires_at__isnull=True)
            |
            Q(expires_at__gt=timezone.now())

        ).first()



        if perm:

            return perm.permission_mask



        if node.parent_id:

            parent_mask = PermissionService.resolve_mask(

                user,

                node.parent

            )


            return parent_mask



        return None






    @staticmethod
    def check(
        user,
        node,
        required_bit,
        log_action=None
    ):


        mask = PermissionService.resolve_mask(

            user,

            node

        )


        allowed = bool(
            mask & required_bit
        )



        if log_action:

            from apps.audit.models import AuditLog


            AuditLog.record(

                user=user,

                action=log_action,

                node=node,

                result="success" if allowed else "denied",

                reason=""

            )



        return allowed






    @staticmethod
    def assert_op(
        user,
        node,
        required_bit,
        log_action=None
    ):


        if not PermissionService.check(

            user,

            node,

            required_bit,

            log_action

        ):


            mask = PermissionService.resolve_mask(

                user,

                node

            )


            raise PermissionDenied({

                "error":
                "permission_denied",


                "required":
                Bit.labels(required_bit),


                "effective":
                Bit.labels(mask)

            })





    @staticmethod
    def get_user_permissions_summary(user,node):


        mask = PermissionService.resolve_mask(
            user,
            node
        )


        return {

            "mask": mask,

            "read":
                bool(mask & Bit.READ),

            "write":
                bool(mask & Bit.WRITE),

            "execute":
                bool(mask & Bit.EXECUTE),

            "delete":
                bool(mask & Bit.DELETE),

            "manage":
                bool(mask & Bit.MANAGE),

            "full":
                mask == Bit.FULL,

            "labels":
                Bit.labels(mask)

        }





# ==========================================================
# DRF PERMISSIONS
# ==========================================================

class IsSuperAdmin(BasePermission):


    def has_permission(self,request,view):

        return (

            request.user.is_authenticated

            and

            request.user.role == Role.SUPER_ADMIN

        )





class IsDeptManagerOrAbove(BasePermission):


    def has_permission(self,request,view):

        return (

            request.user.is_authenticated

            and

            request.user.role in [

                Role.SUPER_ADMIN,

                Role.DEPT_MANAGER

            ]

        )