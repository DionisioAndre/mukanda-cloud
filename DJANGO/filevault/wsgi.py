"""
WSGI config for filevault project.
"""

import os

from django.core.wsgi import get_wsgi_application

# Define qual arquivo de configurações o WSGI deve usar
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filevault.settings')

application = get_wsgi_application()