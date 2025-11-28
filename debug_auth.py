import os
import django
from django.contrib.auth import authenticate

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = "admin_user"
password = "admin_password"

try:
    user = User.objects.get(username=username)
    print(f"User: {user.username}")
    print(f"Email: {user.email}")
    print(f"Is Staff: {user.is_staff}")
    print(f"Is Superuser: {user.is_superuser}")
    print(f"Is Active: {user.is_active}")
    print(f"Role: {user.role}")
    print(f"Password Valid: {user.check_password(password)}")
    
    auth_user = authenticate(username=username, password=password)
    if auth_user:
        print("Authentication successful!")
        print(f"Authenticated User Is Staff: {auth_user.is_staff}")
    else:
        print("Authentication failed via authenticate() function.")

except User.DoesNotExist:
    print(f"User '{username}' not found.")
