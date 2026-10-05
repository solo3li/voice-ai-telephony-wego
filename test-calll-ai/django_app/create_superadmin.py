import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from voice_assistant.models import EmployeeProfile

def create_admin():
    username = os.getenv('SUPERUSER_USERNAME', 'admin')
    email = os.getenv('SUPERUSER_EMAIL', 'admin@example.com')
    password = os.getenv('SUPERUSER_PASSWORD', 'admin123456')

    user, created = User.objects.get_or_create(username=username, defaults={'email': email})
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.set_password(password)
    user.save()

    # Also create employee profile so admin can test telephony / call center features
    EmployeeProfile.objects.update_or_create(
        user=user,
        defaults={
            'extension': '100',
            'display_name': 'مدير النظام (Super Admin)',
            'department': 'الإدارة العامة',
            'status': 'ready',
            'avatar_url': 'https://api.dicebear.com/7.x/bottts/png?seed=admin'
        }
    )

    action = "Created" if created else "Updated"
    print(f"Superuser successfully {action}:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print(f"  Email:    {email}")

if __name__ == '__main__':
    create_admin()
