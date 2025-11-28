import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from quiz.models import Quiz, Question, Option

# Create a dummy quiz
quiz, created = Quiz.objects.get_or_create(
    title="Math Test",
    description="Testing LaTeX rendering",
    time_limit_minutes=10
)

# Create a question with LaTeX
question, created = Question.objects.get_or_create(
    quiz=quiz,
    text="Solve for x: $x^2 - 4 = 0$",
    question_type="SINGLE"
)

# Create options
Option.objects.get_or_create(question=question, text="$x = 2$", is_correct=True)
Option.objects.get_or_create(question=question, text="$x = 3$", is_correct=False)

print(f"Created quiz '{quiz.title}' with LaTeX question.")
