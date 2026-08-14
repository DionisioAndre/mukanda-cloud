# apps/accounts/admin.py
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Company, CrossDeptPermission

# --- FORMULÁRIO DE CRIAÇÃO DO ZERO (SEM HERANÇA DE USERNAME) ---
# backend/apps/accounts/admin.py

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'quota_bytes', 'is_active')
    search_fields = ('name', 'slug')
    exclude = ('created_by',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name',)

class MyUserCreationForm(forms.ModelForm):
    """
    Formulário customizado que ignora completamente o campo 'username' do Django.
    """
    password = forms.CharField(widget=forms.PasswordInput, label="Palavra-passe")

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'company', 'department', 'password')

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get('company')
        department = cleaned_data.get('department')

        # Validate that department belongs to the selected company
        if company and department:
            if department.company != company:
                raise forms.ValidationError(
                    {'department': 'Departamento deve pertencer à empresa selecionada.'}
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

class MyUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'company', 'department', 'is_active', 'is_staff')

# --- ADMIN ATUALIZADO ---

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = MyUserCreationForm
    form = MyUserChangeForm
    model = User

    # Campos exibidos na lista
    list_display = ('email', 'first_name', 'last_name', 'role', 'company', 'department', 'is_staff')
    
    # IMPORTANTE: Sobrescrevemos os fieldsets padrão do UserAdmin 
    # para garantir que o Django não injete o 'username' por baixo dos panos
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name', 'last_name')}),
        ('Hierarquia', {'fields': ('role', 'company', 'department')}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('extraweighted',),
            'fields': ('email', 'first_name', 'last_name', 'password', 'role', 'company', 'department'),
        }),
    )

    # Necessário para UserAdmin não quebrar sem username_field
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ()