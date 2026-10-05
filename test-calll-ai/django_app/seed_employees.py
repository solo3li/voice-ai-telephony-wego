import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from voice_assistant.models import EmployeeProfile, CallQueue, QueueMembership

def seed():
    print("--- Seeding Employees & Queues ---")
    
    # 1. Employee 101 (Ahmed)
    user_ahmed, _ = User.objects.get_or_create(username='ahmed', defaults={'first_name': 'أحمد', 'last_name': 'مصطفى'})
    user_ahmed.set_password('password123')
    user_ahmed.save()
    
    emp_ahmed, _ = EmployeeProfile.objects.update_or_create(
        user=user_ahmed,
        defaults={
            'extension': '101',
            'display_name': 'أحمد مصطفى',
            'department': 'المبيعات',
            'status': 'ready',
            'avatar_url': 'https://api.dicebear.com/7.x/bottts/png?seed=101'
        }
    )
    print(f"Created/Updated: {emp_ahmed}")

    # 2. Employee 102 (Sara)
    user_sara, _ = User.objects.get_or_create(username='sara', defaults={'first_name': 'سارة', 'last_name': 'خليل'})
    user_sara.set_password('password123')
    user_sara.save()

    emp_sara, _ = EmployeeProfile.objects.update_or_create(
        user=user_sara,
        defaults={
            'extension': '102',
            'display_name': 'سارة خليل',
            'department': 'الدعم الفني',
            'status': 'ready',
            'avatar_url': 'https://api.dicebear.com/7.x/bottts/png?seed=102'
        }
    )
    print(f"Created/Updated: {emp_sara}")

    # 3. Employee 103 (Mohamed)
    user_mohamed, _ = User.objects.get_or_create(username='mohamed', defaults={'first_name': 'محمد', 'last_name': 'علي'})
    user_mohamed.set_password('password123')
    user_mohamed.save()

    emp_mohamed, _ = EmployeeProfile.objects.update_or_create(
        user=user_mohamed,
        defaults={
            'extension': '103',
            'display_name': 'محمد علي',
            'department': 'المبيعات',
            'status': 'break',
            'avatar_url': 'https://api.dicebear.com/7.x/bottts/png?seed=103'
        }
    )
    print(f"Created/Updated: {emp_mohamed}")

    # 4. Sales Queue 200
    queue = CallQueue.objects.filter(code='200').first()
    if not queue:
        queue = CallQueue.objects.create(
            user=user_ahmed,
            code='200',
            name='طابور المبيعات (Sales Queue)',
            strategy='round_robin',
            ring_timeout_seconds=15,
            total_timeout_seconds=60,
            fallback_action='ai_assistant'
        )
    print(f"Queue: {queue}")

    # Add memberships
    QueueMembership.objects.update_or_create(
        queue=queue,
        employee=emp_ahmed,
        defaults={'order': 1, 'is_active': True}
    )
    QueueMembership.objects.update_or_create(
        queue=queue,
        employee=emp_mohamed,
        defaults={'order': 2, 'is_active': True}
    )
    print("Memberships assigned to Sales Queue!")
    print("Done!")

if __name__ == '__main__':
    seed()
