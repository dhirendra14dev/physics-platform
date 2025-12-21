from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Quiz, QuizQuestion

@receiver(m2m_changed, sender=Quiz.passages.through)
def add_passage_questions_to_quiz(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Signal to automatically add questions from a selected Passage to the Quiz.
    """
    if action == "post_add":
        # instance is the Quiz object
        if not reverse:
            passages = model.objects.filter(pk__in=pk_set)
            for passage in passages:
                questions = passage.questions.all()
                for question in questions:
                    # Check if already added
                    if not QuizQuestion.objects.filter(quiz=instance, question=question).exists():
                        QuizQuestion.objects.create(
                            quiz=instance,
                            question=question,
                            marks=4.0, # Default marks
                            negative_marks=1.0 # Default negative marks
                        )
    elif action == "post_remove":
        # Remove questions associated with the removed passage
        if not reverse:
            passages = model.objects.filter(pk__in=pk_set)
            for passage in passages:
                questions = passage.questions.all()
                QuizQuestion.objects.filter(quiz=instance, question__in=questions).delete()
