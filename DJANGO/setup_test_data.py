import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'filevault.settings')
django.setup()

from apps.accounts.models import User, Company, Department

print("Setting up test data...")

# Get the admin user
admin = User.objects.get(email='admin@mukanda.com')

# Create a test company if it doesn't exist
company, created = Company.objects.get_or_create(
    name='Test Company',
    defaults={
        'is_active': True,
        'created_by': admin
    }
)

if created:
    print(f"✅ Created company: {company.name}")
else:
    print(f"ℹ️  Company already exists: {company.name}")

# Assign admin to the company
admin.company = company
admin.save()
print(f"✅ Assigned admin to company: {company.name}")

# Create a test department
dept, created = Department.objects.get_or_create(
    name='IT Department',
    company=company,
    defaults={
        'is_active': True,
        'created_by': admin,
        'color': '#3B82F6'
    }
)

if created:
    print(f"✅ Created department: {dept.name}")
else:
    print(f"ℹ️  Department already exists: {dept.name}")

# Assign admin to department
admin.department = dept
admin.save()
print(f"✅ Assigned admin to department: {dept.name}")

print("\n✅ Test data setup complete!")
print(f"User: {admin.email}")
print(f"Company: {admin.company.name}")
print(f"Department: {admin.department.name}")
