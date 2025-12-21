from django.db import models
from django.conf import settings

class Passage(models.Model):
    title = models.CharField(max_length=200, blank=True)
    text = models.TextField(help_text="Content of the passage (LaTeX supported)")
    image = models.ImageField(upload_to='passages/', blank=True, null=True)

    def __str__(self):
        return self.title or self.text[:50]

class Question(models.Model):
    class Type(models.TextChoices):
        MCQ_SINGLE = 'MCQ_SINGLE', 'Single Correct MCQ'
        MCQ_MULTI = 'MCQ_MULTI', 'Multi Correct MCQ'
        NUMERICAL = 'NUMERICAL', 'Numerical'
        MATRIX = 'MATRIX', 'Matrix Match'
        MATRIX_SINGLE = 'MATRIX_SINGLE', 'Matrix Single'
        TRUE_FALSE = 'TRUE_FALSE', 'True/False'
        ASSERTION_REASON = 'ASSERTION_REASON', 'Assertion-Reason'

    CHAPTER_CHOICES = [
        ('VECTORS', 'Vectors'),
        ('KINEMATICS_1D', 'Kinematics - 1D'),
        ('KINEMATICS_2D', 'Kinematics - 2D'),
        ('NEWTONS_LAWS', "Newton's Laws of Motion"),
        ('FRICTION', 'Friction'),
        ('CIRCULAR_MOTION', 'Circular Motion'),
        ('WORK_POWER_ENERGY', 'Work, Power and Energy'),
        ('COM_MOMENTUM', 'Center of Mass and Conservation of Linear Momentum'),
        ('ROTATIONAL_MOTION', 'Rotational Motion'),
        ('GRAVITATION', 'Gravitation'),
        ('FLUID_DYNAMICS', 'Fluid Dynamics'),
        ('MECHANICAL_PROPERTIES', 'Mechanical Properties of Matter'),
        ('SHM', 'Simple Harmonic Motion'),
        ('WAVE_MOTION', 'Wave Motion'),
        ('HEAT_THERMODYNAMICS', 'Heat and Thermodynamics'),
        ('ELECTROSTATICS', 'Electrostatics'),
        ('CURRENT_ELECTRICITY', 'Current Electricity'),
        ('CAPACITANCE', 'Capacitance'),
        ('MAGNETISM', 'Magnetism'),
        ('EMI', 'Electromagnetic Induction'),
        ('AC', 'Alternating Current'),
        ('GEOMETRICAL_OPTICS', 'Geometrical Optics'),
        ('WAVE_OPTICS', 'Wave Optics'),
        ('MODERN_PHYSICS', 'Modern Physics'),
    ]

    DIFFICULTY_CHOICES = [
        ('VERY_EASY', 'Very Easy'),
        ('EASY', 'Easy'),
        ('MODERATE', 'Moderate'),
        ('DIFFICULT', 'Difficult'),
        ('VERY_DIFFICULT', 'Very Difficult'),
    ]

    text = models.TextField(help_text="Question text (LaTeX supported)", blank=True)
    assertion = models.TextField(blank=True, null=True, help_text="Assertion text (for Assertion-Reason questions)")
    reason = models.TextField(blank=True, null=True, help_text="Reason text (for Assertion-Reason questions)")
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    question_type = models.CharField(max_length=20, choices=Type.choices)
    allow_partial_marking = models.BooleanField(default=True, help_text="For MCQ Multi: If true, partial marks are awarded. If false, only full marks or negative marks.")
    
    # New Fields
    chapter = models.CharField(max_length=50, choices=CHAPTER_CHOICES, blank=True, null=True)
    subtopic = models.CharField(max_length=200, blank=True, null=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='MODERATE')
    
    # For Numerical
    numerical_answer = models.FloatField(blank=True, null=True)
    numerical_tolerance = models.FloatField(default=0.0, help_text="Allowed range (+/-)")

    # For Comprehension (Questions linked to a passage)
    passage = models.ForeignKey(Passage, on_delete=models.CASCADE, blank=True, null=True, related_name='questions')

    # For Matrix Match
    # Expected JSON format:
    # {
    #   "rows": [{"id": "A", "text": "Row A"}, ...],
    #   "cols": [{"id": "p", "text": "Col p"}, ...],
    #   "correct": {"A": ["p", "q"], "B": ["r"]}
    # }
    matrix_config = models.JSONField(blank=True, null=True, help_text="DEPRECATED: Use MatrixRow/MatrixCol models instead")

    def __str__(self):
        return f"{self.get_question_type_display()}: {self.text[:50]}"

class MatrixRow(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='matrix_rows')
    label = models.CharField(max_length=10, help_text="e.g. A, B, C")
    text = models.CharField(max_length=1000, blank=True)
    image = models.ImageField(upload_to='matrix_rows/', blank=True, null=True)
    # Comma separated correct matches for this row (e.g. "p,q") - mostly for MATRIX type
    matches = models.CharField(max_length=50, blank=True, help_text="Comma-separated IDs of correct columns (e.g. p,q)")

    def __str__(self):
        return f"{self.label}: {self.text}"

class MatrixCol(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='matrix_cols')
    label = models.CharField(max_length=10, help_text="e.g. p, q, r")
    text = models.CharField(max_length=1000, blank=True)
    image = models.ImageField(upload_to='matrix_cols/', blank=True, null=True)

    def __str__(self):
        return f"{self.label}: {self.text}"

class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=1000, blank=True)
    image = models.ImageField(upload_to='options/', blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    questions = models.ManyToManyField(Question, through='QuizQuestion')
    passages = models.ManyToManyField('Passage', blank=True, help_text="Select passages to add all their questions to the quiz automatically.")
    assigned_groups = models.ManyToManyField('auth.Group', related_name='quizzes', blank=True, help_text="Batches/Groups this quiz is assigned to")
    assigned_students = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_quizzes', blank=True, help_text="Individual students this quiz is assigned to")
    is_public = models.BooleanField(default=False, help_text="If true, visible to everyone; otherwise only assigned students/groups.")
    time_limit_minutes = models.IntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Attempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField(default=0.0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title}"

class Response(models.Model):
    class QuestionStatus(models.TextChoices):
        NOT_VISITED = 'NOT_VISITED', 'Not Visited'
        NOT_ANSWERED = 'NOT_ANSWERED', 'Not Answered'
        ANSWERED = 'ANSWERED', 'Answered'
        MARKED_FOR_REVIEW = 'MARKED_FOR_REVIEW', 'Marked for Review'
        ANSWERED_MARKED = 'ANSWERED_MARKED', 'Answered & Marked for Review'

    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    # Store answer as JSON to handle multiple options, numerical values, or matrix matches
    answer_data = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=QuestionStatus.choices, default=QuestionStatus.NOT_VISITED)

    class Meta:
        unique_together = ('attempt', 'question')

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    marks = models.FloatField(default=4.0)
    negative_marks = models.FloatField(default=1.0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - {self.question}"

class SolutionBlock(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='solution_blocks')
    text = models.TextField(blank=True, help_text="Text content (LaTeX supported)")
    image = models.ImageField(upload_to='solutions/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Solution Block {self.order} for {self.question}"
