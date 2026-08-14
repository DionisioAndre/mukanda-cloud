from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Painel de Auditoria Imutável.
    Configurado para análise forense e alta performance.
    """
    # 1. Lista de exibição otimizada para snapshots
    list_display = (
        'timestamp_format', 
        'user_email', 
        'action_label', 
        'result_badge', 
        'node_name', 
        'ip_address'
    )

    # 2. Filtros laterais inteligentes
    list_filter = (
        'action', 
        'result', 
        'timestamp', 
        'user_role', 
        'dept_name'
    )

    # 3. Busca rápida por utilizador ou ficheiro
    search_fields = (
        'user_email', 
        'node_name', 
        'node_path', 
        'reason', 
        'ip_address'
    )

    # 4. Otimização de queries (evita N+1 SELECTs)
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'department', 'node')

    # 5. Segurança: Tornar tudo "Read-Only" no painel
    # Logs de auditoria nunca devem ser editados via Admin
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    # --- Métodos de Formatação Visual ---

    @admin.display(description='Data/Hora', ordering='timestamp')
    def timestamp_format(self, obj):
        return obj.timestamp.strftime("%d/%m/%Y %H:%M:%S")

    @admin.display(description='Ação')
    def action_label(self, obj):
        return dict(obj._meta.get_field('action').choices).get(obj.action)

    @admin.display(description='Resultado')
    def result_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'success': '#22c55e', # Verde
            'denied': '#ef4444',  # Vermelho
            'error': '#f59e0b',   # Amarelo
        }
        return format_html(
            '<span style="color: white; background: {}; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; text-transform: uppercase;">{}</span>',
            colors.get(obj.result, '#6b7280'),
            obj.get_result_display()
        )

    # 6. Detalhes organizados para investigação
    readonly_fields = [f.name for f in AuditLog._meta.get_fields()]
    fieldsets = (
        ('Quem', {'fields': (('user', 'user_email'), ('user_role', 'department', 'dept_name'))}),
        ('O Quê', {'fields': ('action', 'result', 'reason')}),
        ('Alvo', {'fields': ('node', 'node_name', 'node_path')}),
        ('Contexto Técnico', {'fields': ('timestamp', 'ip_address', 'user_agent', 'extra')}),
    )