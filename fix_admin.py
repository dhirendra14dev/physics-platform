import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = "admin_user"

try:
    user = User.objects.get(username=username)
    user.is_staff = True
    user.is_superuser = True
    user.role = "ADMIN"
    user.save()
    print(f"User '{username}' updated: is_staff={user.is_staff}, is_superuser={user.is_superuser}, role={user.role}")
except User.DoesNotExist:
    print(f"User '{username}' not found.")
