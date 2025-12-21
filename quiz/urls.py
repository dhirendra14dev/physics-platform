from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('quiz/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('quiz/<int:quiz_id>/single/', views.take_quiz_single, name='take_quiz_single'),
    path('quiz/<int:quiz_id>/single/<int:question_index>/', views.take_quiz_single, name='take_quiz_single'),
    path('quiz/<int:quiz_id>/submit/', views.submit_quiz, name='submit_quiz'),
    path('result/<int:attempt_id>/', views.result, name='result'),
    path('question-bank/', views.question_bank, name='question_bank'),
    path('create-test/', views.create_test, name='create_test'),
]
