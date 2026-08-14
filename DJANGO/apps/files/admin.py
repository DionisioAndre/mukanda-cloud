from django.contrib import admin
from django.utils.html import format_html
from .models import FileSystemNode, UserFilePermission

@admin.register(FileSystemNode)
class FileSystemNodeAdmin(admin.ModelAdmin):
    """
    Interface para gestão da Árvore de Ficheiros.
    Suporta filtros por departamento e visualização de metadados.
    """
    list_display = (
        'icon_type', 
        'name', 
        'department', 
        'node_type', 
        'size_readable', 
        'is_deleted_badge', 
        'created_at'
    )
    
    list_filter = (
        'node_type', 
        'department', 
        'is_deleted', 
        'extension', 
        'is_locked'
    )
    
    search_fields = ('name', 'materialized_path', 'description')
    
    # Campo de leitura apenas para o caminho calculado (evita quebra da árvore)
    readonly_fields = ('materialized_path', 'checksum', 'size_bytes', 'extension')
    
    autocomplete_fields = ['parent', 'department', 'created_by']

    def get_queryset(self, request):
        # Otimiza carregando relações para evitar centenas de queries na listagem
        return super().get_queryset(request).select_related('department', 'parent')

    # --- Elementos Visuais ---

    @admin.display(description='')
    def icon_type(self, obj):
        """Renderiza um ícone para distinguir pastas de ficheiros."""
        icon = "📁" if obj.node_type == 'folder' else "📄"
        color = "#3b82f6" if obj.node_type == 'folder' else "#64748b"
        return format_html('<span style="font-size: 1.2rem; color: {};">{}</span>', color, icon)

    @admin.display(description='Tamanho')
    def size_readable(self, obj):
        return obj.size_display if obj.node_type == 'file' else "-"

    @admin.display(description='Estado')
    def is_deleted_badge(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: #ef4444;">🗑️ Eliminado</span>')
        return format_html('<span style="color: #22c55e;">✅ Ativo</span>')

    # Organização do Formulário de Edição
    fieldsets = (
        ('Localização na Árvore', {
            'fields': ('name', 'node_type', 'parent', 'department', 'materialized_path')
        }),
        ('Conteúdo', {
            'fields': ('file_field', 'description', 'tags')
        }),
        ('Metadados Técnicos', {
            'fields': (('size_bytes', 'extension'), 'checksum', 'is_locked', 'is_starred'),
            'classes': ('collapse',) # Esconde por padrão para limpar a UI
        }),
        ('Auditoria de Deleção', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserFilePermission)
class UserFilePermissionAdmin(admin.ModelAdmin):
    """
    Gestão de ACL (Access Control List) granular por utilizador.
    """
    list_display = ('user', 'node_link', 'mask_display', 'is_active', 'assigned_at')
    list_filter = ('is_active', 'assigned_at')
    search_fields = ('user__email', 'node__name')
    autocomplete_fields = ['user', 'node', 'assigned_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'node', 'assigned_by')

    @admin.display(description='Ficheiro/Pasta')
    def node_link(self, obj):
        return obj.node.materialized_path

    @admin.display(description='Permissões (Bitmask)')
    def mask_display(self, obj):
        """Traduz o bitmask para texto legível no Admin."""
        perms = []
        if obj.permission_mask & 1: perms.append("Read")
        if obj.permission_mask & 2: perms.append("Write")
        if obj.permission_mask & 4: perms.append("Exec")
        if obj.permission_mask & 8: perms.append("Del")
        
        label = ", ".join(perms) if perms else "None"
        color = "#1e293b"
        if obj.permission_mask == 15: # Full Control
            color = "#7c3aed"
            label = "FULL CONTROL"
            
        return format_html('<strong style="color: {};">{} ({})</strong>', color, label, obj.permission_mask)