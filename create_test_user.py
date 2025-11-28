import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = "testuser"
password = "testpass123"
email = "test@example.com"

# Delete if exists
User.objects.filter(username=username).delete()

# Create new user
user = User.objects.create_user(username=username, email=email, password=password, role="STUDENT")
print(f"Created test user '{username}' with password '{password}'")
