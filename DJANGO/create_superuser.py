import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filevault.settings')
django.setup()

from apps.accounts.models import User

if not User.objects.filter(email='admin@mukanda.com').exists():
    user = User.objects.create_superuser(
        email='admin@mukanda.com',
        password='admin123',
        role='SUPER_ADMIN'
    )
    print(f'Superuser created: {user.email}')
else:
    print('Superuser already exists')
