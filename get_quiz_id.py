import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from quiz.models import Quiz

try:
    quiz = Quiz.objects.get(title="Math Test")
    print(f"Quiz ID: {quiz.id}")
except Quiz.DoesNotExist:
    print("Quiz not found.")
