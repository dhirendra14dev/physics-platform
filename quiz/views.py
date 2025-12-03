from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Quiz, Attempt, Question, Response, Option, QuizQuestion
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
    
    # Iterate over QuizQuestion to get marks/negative_marks
    quiz_questions = QuizQuestion.objects.filter(quiz=quiz).select_related('question')
    
    for qq in quiz_questions:
        question = qq.question
        user_answer = request.POST.getlist(f'question_{question.id}')
        
        is_correct = False
        answer_data = user_answer
        
        if question.question_type == Question.Type.MCQ_SINGLE:
            if user_answer:
                selected_option_id = user_answer[0]
                try:
                    option = Option.objects.get(id=selected_option_id)
                    if option.is_correct:
                        score += qq.marks
                        is_correct = True
                    else:
                        score -= qq.negative_marks
                except Option.DoesNotExist:
                    pass
                    
        elif question.question_type == Question.Type.MCQ_MULTI:
            # Simple logic: All correct options selected and no incorrect ones
            selected_ids = set(user_answer)
            correct_ids = set(str(o.id) for o in question.options.filter(is_correct=True))
            if selected_ids == correct_ids:
                score += qq.marks
                is_correct = True
            elif selected_ids: # If attempted but wrong
                score -= qq.negative_marks

        elif question.question_type == Question.Type.NUMERICAL:
            if user_answer and user_answer[0]:
                try:
                    val = float(user_answer[0])
                    correct_val = question.numerical_answer
                    tolerance = question.numerical_tolerance
                    if correct_val is not None and abs(val - correct_val) <= tolerance:
                        score += qq.marks
                        is_correct = True
                    else:
                        score -= qq.negative_marks
                except ValueError:
                    pass

        elif question.question_type == Question.Type.MATRIX:
            # Matrix Match Logic
            # Expected answer format: {"A": ["p", "q"], "B": ["r"]}
            # User submission: question_{id}_row_{row_id} -> [col_id, ...]
            
            if question.matrix_config and 'rows' in question.matrix_config and 'correct' in question.matrix_config:
                user_matrix_answer = {}
                rows_correct_count = 0
                
                for row in question.matrix_config['rows']:
                    row_id = row['id']
                    # Get user selected cols for this row
                    user_selected_cols = request.POST.getlist(f'question_{question.id}_row_{row_id}')
                    user_matrix_answer[row_id] = user_selected_cols
                    
                    correct_cols = set(question.matrix_config['correct'].get(row_id, []))
                    user_cols = set(user_selected_cols)
                    
                    if correct_cols == user_cols:
                        rows_correct_count += 1
                
                answer_data = user_matrix_answer
                
                # Scoring: +2 for each correct row
                score += (rows_correct_count * 2.0)
                
                # Determine if the question is "fully" correct for is_correct flag
                # (Optional, but good for stats)
                if rows_correct_count == len(question.matrix_config['rows']):
                    is_correct = True
                else:
                    is_correct = False
                    
                # No negative marking for Matrix Match as per requirement

        # TODO: Implement Comprehension logic
        
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
