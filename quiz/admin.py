import nested_admin
from django.contrib import admin
from .models import Question, Option, Quiz, Passage, Attempt, QuizQuestion, MatrixRow, MatrixCol

class OptionInline(nested_admin.NestedTabularInline):
    model = Option
    extra = 4

class MatrixRowInline(nested_admin.NestedTabularInline):
    model = MatrixRow
    extra = 2
    fields = ('label', 'text', 'image', 'matches')

class MatrixColInline(nested_admin.NestedTabularInline):
    model = MatrixCol
    extra = 2
    fields = ('label', 'text', 'image')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question_type', 'chapter', 'difficulty')
    list_filter = ('question_type', 'chapter', 'difficulty')
    inlines = [MatrixRowInline, MatrixColInline, OptionInline]
    search_fields = ('text',)

class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 1

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'time_limit_minutes', 'created_at')
    inlines = [QuizQuestionInline]

class QuestionInline(nested_admin.NestedStackedInline):
    model = Question
    extra = 1
    inlines = [OptionInline]

@admin.register(Passage)
class PassageAdmin(nested_admin.NestedModelAdmin):
    list_display = ('title', 'text')
    inlines = [QuestionInline]

@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'started_at')
    list_filter = ('quiz',)
