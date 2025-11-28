from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Quiz, Attempt, Question, Response, Option
import json

@login_required
def dashboard(request):
    quizzes = Quiz.objects.all()
    attempts = Attempt.objects.filter(user=request.user)
    return render(request, 'quiz/dashboard.html', {'quizzes': quizzes, 'attempts': attempts})

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    # Get or create an active attempt for this user and quiz
    attempt = Attempt.objects.filter(
        user=request.user, 
        quiz=quiz, 
        completed_at__isnull=True
    ).first()
    
    if not attempt:
        # Create new attempt
        attempt = Attempt.objects.create(user=request.user, quiz=quiz)
    
    # Calculate remaining time
    elapsed_seconds = (timezone.now() - attempt.started_at).total_seconds()
    total_seconds = quiz.time_limit_minutes * 60
    remaining_seconds = max(0, int(total_seconds - elapsed_seconds))
    
    # If time has expired, auto-submit
    if remaining_seconds <= 0:
        attempt.completed_at = timezone.now()
        attempt.save()
        return redirect('result', attempt_id=attempt.id)
    
    questions = quiz.questions.all().prefetch_related('options')
    return render(request, 'quiz/take_quiz.html', {
        'quiz': quiz, 
        'questions': questions,
        'attempt': attempt,
        'remaining_seconds': remaining_seconds
    })

@login_required
def submit_quiz(request, quiz_id):
    if request.method != 'POST':
        return redirect('dashboard')
        
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.all()
    
    # Get the active attempt
    attempt = Attempt.objects.filter(
        user=request.user,
        quiz=quiz,
        completed_at__isnull=True
    ).first()
    
    if not attempt:
        # If no active attempt, redirect to dashboard
        return redirect('dashboard')
    
    score = 0
    
    for question in questions:
        user_answer = request.POST.getlist(f'question_{question.id}')
        # For Matrix, it might be different keys, e.g. question_{id}_row_{row_id}
        # But let's assume we handle that in frontend to submit a JSON or structured data
        # For MVP, let's handle basic types first.
        
        is_correct = False
        answer_data = user_answer
        
        if question.question_type == Question.Type.MCQ_SINGLE:
            if user_answer:
                selected_option_id = user_answer[0]
                try:
                    option = Option.objects.get(id=selected_option_id)
                    if option.is_correct:
                        score += question.marks
                        is_correct = True
                    else:
                        score -= question.negative_marks
                except Option.DoesNotExist:
                    pass
                    
        elif question.question_type == Question.Type.MCQ_MULTI:
            # Simple logic: All correct options selected and no incorrect ones
            selected_ids = set(user_answer)
            correct_ids = set(str(o.id) for o in question.options.filter(is_correct=True))
            if selected_ids == correct_ids:
                score += question.marks
                is_correct = True
            elif selected_ids: # If attempted but wrong
                score -= question.negative_marks

        elif question.question_type == Question.Type.NUMERICAL:
            if user_answer and user_answer[0]:
                try:
                    val = float(user_answer[0])
                    correct_val = question.numerical_answer
                    tolerance = question.numerical_tolerance
                    if correct_val is not None and abs(val - correct_val) <= tolerance:
                        score += question.marks
                        is_correct = True
                    else:
                        score -= question.negative_marks
                except ValueError:
                    pass

        # TODO: Implement Matrix and Comprehension logic
        
        Response.objects.create(
            attempt=attempt,
            question=question,
            answer_data=answer_data
        )

    attempt.score = score
    attempt.completed_at = timezone.now()
    attempt.save()
    
    return redirect('result', attempt_id=attempt.id)

@login_required
def result(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    return render(request, 'quiz/result.html', {'attempt': attempt})
