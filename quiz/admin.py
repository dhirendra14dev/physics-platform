from django.contrib import admin
from .models import Question, Option, Quiz, Passage, Attempt

class OptionInline(admin.TabularInline):
    model = Option
    extra = 4

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question_type', 'marks')
    list_filter = ('question_type',)
    inlines = [OptionInline]
    search_fields = ('text',)

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'time_limit_minutes', 'created_at')
    filter_horizontal = ('questions',)

@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ('title', 'text')

@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'started_at')
    list_filter = ('quiz',)
