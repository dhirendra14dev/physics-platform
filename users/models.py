from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(max_length=50, choices=Role.choices, default=Role.STUDENT)

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_student(self):
        return self.role == self.Role.STUDENT
