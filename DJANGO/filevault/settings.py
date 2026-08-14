"""
backend/filevault/settings.py
FileVault Enterprise File Management System
"""
from pathlib import Path
from datetime import timedelta
import os

# Azure Files Storage Configuration
AZURE_STORAGE_ACCOUNT_NAME = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
AZURE_STORAGE_ACCOUNT_KEY = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
AZURE_STORAGE_SHARE_NAME = os.environ.get('AZURE_STORAGE_SHARE_NAME', 'filevault')
AZURE_STORAGE_IOPS_LIMIT = int(os.environ.get('AZURE_STORAGE_IOPS_LIMIT', '1000'))
AZURE_STORAGE_IOPS_WINDOW = float(os.environ.get('AZURE_STORAGE_IOPS_WINDOW', '1.0'))
AZURE_STORAGE_BURST_LIMIT = int(os.environ.get('AZURE_STORAGE_BURST_LIMIT', '100'))
AZURE_STORAGE_USER_IOPS_LIMIT = int(os.environ.get('AZURE_STORAGE_USER_IOPS_LIMIT', '100'))
AZURE_STORAGE_COMPANY_IOPS_LIMIT = int(os.environ.get('AZURE_STORAGE_COMPANY_IOPS_LIMIT', '500'))

# Use Azure Files if configured, otherwise use local storage
if AZURE_STORAGE_ACCOUNT_NAME or AZURE_STORAGE_CONNECTION_STRING:
    from core.azure_storage import AzureFilesStorage
    DEFAULT_FILE_STORAGE = 'core.azure_storage.AzureFilesStorage'
    AZURE_FILES_STORAGE = AzureFilesStorage(
        account_name=AZURE_STORAGE_ACCOUNT_NAME,
        account_key=AZURE_STORAGE_ACCOUNT_KEY,
        connection_string=AZURE_STORAGE_CONNECTION_STRING,
        share_name=AZURE_STORAGE_SHARE_NAME,
        iops_limit=AZURE_STORAGE_IOPS_LIMIT
    )

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-key-change-in-production')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'apps.accounts',
    'apps.files',
    'apps.audit',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.AuditContextMiddleware',
    'core.iops_middleware.IOPSThrottleMiddleware',
]

ROOT_URLCONF = 'filevault.urls'
AUTH_USER_MODEL = 'accounts.User'
WSGI_APPLICATION = 'filevault.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'TOKEN_OBTAIN_SERIALIZER': 'apps.accounts.serializers.CustomTokenObtainPairSerializer',
}

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DEFAULT_DEPARTMENT_QUOTA = 10 * 1024 * 1024 * 1024  # 10 GB
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760