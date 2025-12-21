from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import Quiz, Attempt, Question, Response, Option, QuizQuestion, Passage
from django.db.models import Subquery, OuterRef
import json, random

@login_required
def dashboard(request):
    quizzes = Quiz.objects.all()
    attempts = Attempt.objects.filter(user=request.user).select_related('quiz').order_by('-started_at')
    
    # Grouping attempts by quiz while maintaining recent order
    grouped = {}
    for a in attempts:
        if a.quiz not in grouped:
            grouped[a.quiz] = []
        grouped[a.quiz].append(a)
    
    # Convert to list for template iteration
    performance_data = [{'quiz': q, 'attempts': atts} for q, atts in grouped.items()]
    
    return render(request, 'quiz/dashboard.html', {
        'quizzes': quizzes, 
        'performance_data': performance_data
    })

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
def take_quiz_single(request, quiz_id, question_index=1):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    attempt = Attempt.objects.filter(user=request.user, quiz=quiz, completed_at__isnull=True).first()
    
    if not attempt:
        attempt = Attempt.objects.create(user=request.user, quiz=quiz)
    
    # Calculate remaining time
    elapsed_seconds = (timezone.now() - attempt.started_at).total_seconds()
    total_seconds = quiz.time_limit_minutes * 60
    remaining_seconds = max(0, int(total_seconds - elapsed_seconds))
    
    if remaining_seconds <= 0:
        attempt.completed_at = timezone.now()
        attempt.save()
        return redirect('result', attempt_id=attempt.id)
    
    all_questions = list(quiz.questions.all().order_by('quizquestion__order', 'id'))
    total_questions = len(all_questions)
    
    if total_questions == 0:
        return render(request, 'quiz/result.html', {'attempt': attempt, 'error': 'This quiz has no questions.'})

    if question_index < 1: question_index = 1
    if question_index > total_questions: question_index = total_questions
    
    current_question = all_questions[question_index - 1]
    
    # Get or create response for the current question to track status
    response, created = Response.objects.get_or_create(attempt=attempt, question=current_question)
    
    # If it was not visited, mark it as not answered now that we are here
    if response.status == Response.QuestionStatus.NOT_VISITED:
        response.status = Response.QuestionStatus.NOT_ANSWERED
        response.save()

    if request.method == 'POST':
        action = request.POST.get('action')
        answer = request.POST.getlist(f'question_{current_question.id}')
        
        # Matrix Row handling
        matrix_data = {}
        if current_question.question_type in [Question.Type.MATRIX, Question.Type.MATRIX_SINGLE]:
            for key in request.POST:
                if key.startswith(f'question_{current_question.id}_row_'):
                    row_label = key.replace(f'question_{current_question.id}_row_', '')
                    matrix_data[row_label] = request.POST.getlist(key)
            if matrix_data:
                answer = matrix_data

        if action == 'clear':
            response.answer_data = None
            response.status = Response.QuestionStatus.NOT_ANSWERED
            response.save()
            return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index)
            
        elif action == 'save_next':
            if answer:
                response.answer_data = answer
                response.status = Response.QuestionStatus.ANSWERED
                response.save()
            if question_index < total_questions:
                return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index + 1)
            else:
                return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index)

        elif action == 'save_mark':
            if answer:
                response.answer_data = answer
                response.status = Response.QuestionStatus.ANSWERED_MARKED
                response.save()
            return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index)

        elif action == 'mark_next':
            response.status = Response.QuestionStatus.MARKED_FOR_REVIEW
            response.save()
            if question_index < total_questions:
                return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index + 1)
            else:
                return redirect('take_quiz_single', quiz_id=quiz.id, question_index=question_index)

        elif action == 'submit':
            # Scoring logic for the whole attempt
            # We already have all Responses saved. We just need to calculate the final score.
            # Let's reuse part of submit_quiz logic or move it to a method.
            calculate_final_score(attempt)
            return redirect('result', attempt_id=attempt.id)

    # Prepare Palette and Stats
    responses = {r.question_id: r for r in Response.objects.filter(attempt=attempt)}
    palette = []
    stats = {
        'NOT_VISITED': 0,
        'NOT_ANSWERED': total_questions, # Start with total, then adjust
        'ANSWERED': 0,
        'MARKED_FOR_REVIEW': 0,
        'ANSWERED_MARKED': 0
    }
    
    # Re-count stats and build palette
    stats = {status: 0 for status, label in Response.QuestionStatus.choices}
    stats['NOT_VISITED'] = total_questions # Initially assumed all not visited
    
    for i, q in enumerate(all_questions, 1):
        resp = responses.get(q.id)
        status = resp.status if resp else Response.QuestionStatus.NOT_VISITED
        palette.append({
            'index': i,
            'status': status,
            'is_current': i == question_index
        })
        if resp:
            stats[status] += 1
            stats['NOT_VISITED'] -= 1
        else:
             stats['NOT_VISITED'] += 0 # Already counted

    return render(request, 'quiz/take_quiz_single.html', {
        'quiz': quiz,
        'question': current_question,
        'index': question_index,
        'total': total_questions,
        'palette': palette,
        'stats': stats,
        'attempt': attempt,
        'response': response,
        'remaining_seconds': remaining_seconds
    })

def calculate_final_score(attempt):
    quiz = attempt.quiz
    score = 0.0
    quiz_questions = QuizQuestion.objects.filter(quiz=quiz).select_related('question')
    responses = {r.question_id: r for r in Response.objects.filter(attempt=attempt)}
    
    for qq in quiz_questions:
        question = qq.question
        resp = responses.get(question.id)
        if not resp or not resp.answer_data:
            continue
            
        user_answer = resp.answer_data
        q_marks = qq.marks if qq.marks > 0 else 4.0
        q_neg = qq.negative_marks if qq.negative_marks > 0 else 1.0
        
        if question.question_type in [Question.Type.MCQ_SINGLE, Question.Type.ASSERTION_REASON]:
            selected_option_id = user_answer[0]
            try:
                option = Option.objects.get(id=selected_option_id)
                if option.is_correct:
                    score += q_marks
                else:
                    score -= q_neg
            except: pass
        elif question.question_type == Question.Type.MCQ_MULTI:
            selected_ids = set(str(x) for x in user_answer)
            correct_ids = set(str(o.id) for o in question.options.filter(is_correct=True))
            if any(sid not in correct_ids for sid in selected_ids):
                score -= q_neg
            else:
                if len(correct_ids) > 0:
                    if question.allow_partial_marking:
                        score += len(selected_ids) * (q_marks / len(correct_ids))
                    elif selected_ids == correct_ids:
                        score += q_marks
                    else:
                        score -= q_neg
        elif question.question_type == Question.Type.NUMERICAL:
            try:
                val = float(user_answer[0])
                correct = question.numerical_answer
                tol = question.numerical_tolerance or 0.0
                if abs(val - correct) <= tol: score += q_marks
                else: score -= q_neg
            except: pass
        elif question.question_type == Question.Type.MATRIX:
            if question.matrix_config:
                rows = question.matrix_config.get('rows', [])
                num_rows = len(rows)
                marks_per_row = q_marks / num_rows if num_rows > 0 else 0
                for row in rows:
                    rid = row['id']
                    if set(user_answer.get(rid, [])) == set(question.matrix_config.get('correct', {}).get(rid, [])):
                        score += marks_per_row
    
    attempt.score = score
    attempt.completed_at = timezone.now()
    attempt.save()

@login_required
def submit_quiz(request, quiz_id):
    if request.method != 'POST':
        return redirect('dashboard')
        
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    # Get the active attempt
    attempt = Attempt.objects.filter(
        user=request.user,
        quiz=quiz,
        completed_at__isnull=True
    ).first()
    
    if not attempt:
        # If no active attempt, redirect to dashboard or result of last attempt
        last_attempt = Attempt.objects.filter(user=request.user, quiz=quiz).last()
        if last_attempt:
            return redirect('result', attempt_id=last_attempt.id)
        return redirect('dashboard')
    
    score = 0.0
    
    # Iterate over QuizQuestion to get marks/negative_marks
    quiz_questions = QuizQuestion.objects.filter(quiz=quiz).select_related('question')
    
    for qq in quiz_questions:
        question = qq.question
        user_answer = request.POST.getlist(f'question_{question.id}')
        
        # Determine marks and negative marks for this question
        # Default fallback if 0, though normally set in admin
        q_marks = qq.marks if qq.marks > 0 else 4.0
        q_neg = qq.negative_marks if qq.negative_marks > 0 else 1.0 # Typically +4/-1 or +4/-2
        
        answer_data = user_answer
        
        if question.question_type in [Question.Type.MCQ_SINGLE, Question.Type.ASSERTION_REASON]:
            if user_answer:
                selected_option_id = user_answer[0]
                try:
                    option = Option.objects.get(id=selected_option_id)
                    if option.is_correct:
                        score += q_marks
                    else:
                        score -= q_neg
                except Option.DoesNotExist:
                    pass
                    
        elif question.question_type == Question.Type.MCQ_MULTI:
            # Logic:
            # 1. If any wrong option is chosen -> -Negative Marks
            # 2. If NO wrong option is chosen -> (No. of selected correct) * (Total Marks / Total Correct Options)
            #    Note: If all correct are selected, this naturally equals Total Marks.

            selected_ids_str = set(user_answer)
            correct_options = question.options.filter(is_correct=True)
            correct_ids_str = set(str(o.id) for o in correct_options)
            
            if not selected_ids_str:
                # Unanswered
                pass
            else:
                # Check if any wrong option selected
                wrong_selected = False
                for sel_id in selected_ids_str:
                    if sel_id not in correct_ids_str:
                        wrong_selected = True
                        break
                
                if wrong_selected:
                    score -= q_neg
                else:
                    # Partial / Full Marks Formula
                    num_correct_options = len(correct_ids_str)
                    if num_correct_options > 0:
                        if question.allow_partial_marking:
                            score += len(selected_ids_str) * (q_marks / num_correct_options)
                        else:
                            # Non-partial: Only full marks if all correct are selected
                            if len(selected_ids_str) == num_correct_options:
                                score += q_marks
                            else:
                                # Not all correct selected and no wrong selected
                                # In strict JEE style without partial, this is usually 0 or negative.
                                # User said "scoring without partial marking", which usually means 0 unless it's wrong.
                                # But if ANY deviation from correct set, standard competitive exams give negative or 0.
                                # Let's assume negative if not perfectly correct, to be safe, or 0? 
                                # Usually, "No Partial" means you MUST get all right for +4, else -2.
                                score -= q_neg

        elif question.question_type == Question.Type.NUMERICAL:
            if user_answer and user_answer[0]:
                try:
                    val = float(user_answer[0])
                    correct_val = question.numerical_answer
                    tolerance = question.numerical_tolerance if question.numerical_tolerance is not None else 0.0
                    
                    if correct_val is not None and abs(val - correct_val) <= tolerance:
                        score += q_marks
                    else:
                        score -= q_neg
                except ValueError:
                    pass # Invalid input, treated as 0 or wrong? Usually 0 if not parsed, but here ignored.

        elif question.question_type == Question.Type.MATRIX:
            # Matrix Match Logic
            # Usually evaluated per Row.
            # Total Marks = q_marks.
            # Marks per row = q_marks / number_of_rows?
            # Or q_marks is per question?
            # Let's assume q_marks is TOTAL for the question.
            
            if question.matrix_config and 'rows' in question.matrix_config and 'correct' in question.matrix_config:
                answer_data = {}
                rows = question.matrix_config['rows']
                num_rows = len(rows)
                marks_per_row = q_marks / num_rows if num_rows > 0 else 0
                
                rows_correct_count = 0
                
                for row in rows:
                    row_id = row['id']
                    user_selected_cols = request.POST.getlist(f'question_{question.id}_row_{row_id}')
                    answer_data[row_id] = user_selected_cols
                    
                    # Logic: "Correct" if the set of selected matches the set of correct
                    correct_cols = set(question.matrix_config['correct'].get(row_id, []))
                    user_cols = set(user_selected_cols)
                    
                    if correct_cols == user_cols:
                        score += marks_per_row
                        rows_correct_count += 1
                    else:
                        # Incorrect row? Usually 0, sometimes negative.
                        # Assuming 0 for now unless defined.
                        pass
                
                # No overall negative for Matrix unless specified.

        elif question.question_type == Question.Type.MATRIX_SINGLE:
             # Treat as multiple MCQ_SINGLE questions joined?
             # For now, let's skip complex logic or treat similar to MATRIX
             pass

        # Save Response
        Response.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={'answer_data': answer_data}
        )

    attempt.score = score
    attempt.completed_at = timezone.now()
    attempt.save()
    
    return redirect('result', attempt_id=attempt.id)

@login_required
def result(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    
    # Get all questions in the correct order
    quiz_questions = QuizQuestion.objects.filter(quiz=attempt.quiz).select_related(
        'question', 'question__passage'
    ).prefetch_related(
        'question__options',
        'question__matrix_rows',
        'question__matrix_cols',
        'question__solution_blocks'
    ).order_by('order', 'question__id')

    # Get existing responses
    existing_responses = Response.objects.filter(attempt=attempt).select_related('question')
    response_map = {r.question_id: r for r in existing_responses}

    final_responses_list = []

    for qq in quiz_questions:
        question = qq.question
        # Get response or create a temporary dummy one for display
        response = response_map.get(question.id)
        
        if not response:
            response = Response(question=question, attempt=attempt, status=Response.QuestionStatus.NOT_VISITED)
            # Default styling for unvisited
            response.status = 'unattempted'
            response.css_class = 'border-secondary'
            response.status_color = '#6c757d'
            response.user_display_options = []
        else:
            # Helper logic for status/styling (copied from previous implementation)
            user_data = response.answer_data
            response.user_display_options = []
            response.status = 'unattempted'
            response.css_class = 'border-warning'
            
            if not user_data:
                 response.status = 'unattempted'
                 response.css_class = 'border-secondary'
                 response.status_color = '#6c757d'
            else:
                if question.question_type in [Question.Type.MCQ_SINGLE, Question.Type.MCQ_MULTI, Question.Type.ASSERTION_REASON]:
                    try:
                        selected_ids = set(str(x) for x in user_data)
                        options = question.options.all()
                        
                        response.user_display_options = [opt for opt in options if str(opt.id) in selected_ids]
                        
                        correct_ids = set(str(opt.id) for opt in options if opt.is_correct)
                        
                        if selected_ids == correct_ids:
                            response.status = 'correct'
                            response.css_class = 'border-success'
                            response.status_color = '#28a745'
                        else:
                            wrong_selection = any(sid not in correct_ids for sid in selected_ids)
                            if wrong_selection:
                                response.status = 'incorrect'
                                response.css_class = 'border-danger'
                                response.status_color = '#dc3545'
                            else:
                                if len(selected_ids) < len(correct_ids):
                                    response.status = 'partial' 
                                    response.css_class = 'border-warning'
                                    response.status_color = '#ffc107'
                                else:
                                    response.status = 'correct'
                                    response.css_class = 'border-success'
                                    response.status_color = '#28a745'
                    except Exception:
                        response.status = 'error'

                elif question.question_type == Question.Type.NUMERICAL:
                    user_val = user_data[0] if user_data else None
                    response.user_text_answer = user_val
                    
                    if user_val:
                        try:
                            val = float(user_val)
                            correct = question.numerical_answer
                            tol = question.numerical_tolerance if question.numerical_tolerance else 0.0
                            if correct is not None and abs(val - correct) <= tol:
                                response.status = 'correct'
                                response.css_class = 'border-success'
                                response.status_color = '#28a745'
                            else:
                                response.status = 'incorrect'
                                response.css_class = 'border-danger'
                                response.status_color = '#dc3545'
                        except:
                            response.status = 'incorrect'
                            response.css_class = 'border-danger'

                elif question.question_type == Question.Type.MATRIX:
                    is_correct = True
                    rows = question.matrix_rows.all()
                    user_dict = user_data if isinstance(user_data, dict) else {}
                    
                    if not rows:
                        response.status = 'error'
                    else:
                        for row in rows:
                            # Correct matches are stored as CSV e.g "p,q"
                            correct_cols = set(x.strip() for x in row.matches.split(',') if x.strip())
                            user_chosen = set(user_dict.get(row.label, []))
                            
                            if user_chosen != correct_cols:
                                is_correct = False
                                break
                        
                        if is_correct:
                            response.status = 'correct'
                            response.css_class = 'border-success'
                            response.status_color = '#28a745'
                        else:
                            response.status = 'incorrect'
                            response.css_class = 'border-danger'
                            response.status_color = '#dc3545'

        final_responses_list.append(response)

    return render(request, 'quiz/result.html', {
        'attempt': attempt,
        'responses': final_responses_list
    })

@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def question_bank(request):
    # Filter Choices
    types = dict(Question.Type.choices)
    chapters = dict(Question.CHAPTER_CHOICES)
    difficulties = dict(Question.DIFFICULTY_CHOICES)
    
    # Get Params
    selected_type = request.GET.get('type')
    selected_chapter = request.GET.get('chapter')
    selected_difficulty = request.GET.get('difficulty')
    
    # Query
    questions = Question.objects.all().order_by('-id')
    
    if selected_type:
        questions = questions.filter(question_type=selected_type)
    if selected_chapter:
        questions = questions.filter(chapter=selected_chapter)
    if selected_difficulty:
        questions = questions.filter(difficulty=selected_difficulty)
        
    questions = questions.select_related('passage').prefetch_related(
        'options', 
        'matrix_rows', 
        'matrix_cols', 
        'solution_blocks'
    )
    
    return render(request, 'quiz/question_bank.html', {
        'questions': questions,
        'types': types,
        'chapters': chapters,
        'difficulties': difficulties,
        'selected_type': selected_type,
        'selected_chapter': selected_chapter,
        'selected_difficulty': selected_difficulty,
    })
@login_required
def create_test(request):
    if request.method == 'POST':
        # Get parameters
        syllabus_type = request.POST.get('syllabus_type') # 'FULL' or 'PART'
        chapters = request.POST.getlist('chapters')
        difficulties = request.POST.getlist('difficulties')
        num_questions = int(request.POST.get('num_questions', 10))
        time_limit = int(request.POST.get('time_limit', 30))
        
        # Base Query
        questions_pool = Question.objects.all()
        
        if syllabus_type == 'PART' and chapters:
            questions_pool = questions_pool.filter(chapter__in=chapters)
        
        if difficulties:
            questions_pool = questions_pool.filter(difficulty__in=difficulties)
            
        # Get unique IDs and sample them
        all_ids = list(questions_pool.values_list('id', flat=True))
        if not all_ids:
            return render(request, 'quiz/create_test.html', {
                'error': 'No questions found for the selected filters.',
                'chapters_choices': Question.CHAPTER_CHOICES,
                'difficulty_choices': Question.DIFFICULTY_CHOICES
            })
            
        selected_ids = random.sample(all_ids, min(len(all_ids), num_questions))
        
        # Passage Integrity: If we picked a question from a passage, ensure we pick ALL questions from that passage
        # to avoid orphans.
        initial_selection = Question.objects.filter(id__in=selected_ids).select_related('passage')
        final_ids = set(selected_ids)
        
        for q in initial_selection:
            if q.passage:
                # Find siblings
                siblings = Question.objects.filter(passage=q.passage).values_list('id', flat=True)
                final_ids.update(siblings)
        
        selected_questions = Question.objects.filter(id__in=final_ids).distinct()
        
        # Create a Quiz
        quiz_title = f"Custom Test: {'Full Syllabus' if syllabus_type == 'FULL' else 'Part Syllabus'}"
        new_quiz = Quiz.objects.create(
            title=quiz_title,
            description=f"Generated on {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            time_limit_minutes=time_limit
        )
        
        # Add questions to quiz
        for i, q in enumerate(selected_questions, 1):
            QuizQuestion.objects.create(quiz=new_quiz, question=q, order=i)
            
        # Redirect to take quiz (Single mode as requested in earlier steps as primary)
        return redirect('take_quiz_single', quiz_id=new_quiz.id, question_index=1)

    return render(request, 'quiz/create_test.html', {
        'chapters_choices': Question.CHAPTER_CHOICES,
        'difficulty_choices': Question.DIFFICULTY_CHOICES
    })
