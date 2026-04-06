from django.db import models
from django.contrib.auth.models import AbstractUser



# Defining user types
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        ASSISTANT = 'assistant', 'Classroom Assistant'
        LEARNER = 'learner', 'Learner'
        MENTOR = 'mentor', 'Mentor'

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.LEARNER
    )
    school = models.ForeignKey(
        'School', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"



# Separate schools
class School(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(
        max_length=200, default='Makhanda, South Africa'
    )

    def __str__(self):
        return self.name



# Creation of distinct subjects
class Subject(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='subjects'
    )

    class Meta:
        unique_together = ('name', 'school')

    def __str__(self):
        return f"{self.name} — {self.school.name}"



# Building off of roles
class Enrollment(models.Model):
    learner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='enrollments',
        limit_choices_to={'role': 'learner'}
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='enrollments'
    )

    class Meta:
        unique_together = ('learner', 'subject')

    def __str__(self):
        return f"{self.learner.get_full_name()} → {self.subject.name}"



# Giving mentors their specific subjects
class MentorAssignment(models.Model):
    mentor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mentees',
        limit_choices_to={'role': 'mentor'}
    )
    learner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mentors_assigned',
        limit_choices_to={'role': 'learner'}
    )

    class Meta:
        unique_together = ('mentor', 'learner')

    def __str__(self):
        return (
            f"{self.mentor.get_full_name()} mentors "
            f"{self.learner.get_full_name()}"
        )



# Attendance, used by teachers and students
class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'

    learner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'role': 'learner'}
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PRESENT
    )
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='attendance_marked'
    )

    class Meta:
        unique_together = ('learner', 'subject', 'date')
        ordering = ['-date']

    def __str__(self):
        return (
            f"{self.learner.get_full_name()} — "
            f"{self.subject.name} — {self.date} ({self.status})"
        )



# Marks
class Grade(models.Model):
    learner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='grades',
        limit_choices_to={'role': 'learner'}
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='grades'
    )
    assessment_name = models.CharField(max_length=200)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=100
    )
    grade_letter = models.CharField(max_length=2, blank=True)
    date = models.DateField()
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='grades_recorded'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        if self.max_score > 0:
            pct = (self.score / self.max_score) * 100
            if pct >= 80:
                self.grade_letter = 'A'
            elif pct >= 70:
                self.grade_letter = 'B'
            elif pct >= 60:
                self.grade_letter = 'C'
            elif pct >= 50:
                self.grade_letter = 'D'
            elif pct >= 40:
                self.grade_letter = 'E'
            else:
                self.grade_letter = 'F'
        super().save(*args, **kwargs)

    @property
    def percentage(self):
        if self.max_score > 0:
            return round((self.score / self.max_score) * 100, 1)
        return 0

    def __str__(self):
        return (
            f"{self.learner.get_full_name()} — "
            f"{self.subject.name} — {self.assessment_name}: "
            f"{self.grade_letter}"
        )

class ChatMessage(models.Model):
    """Stores chatbot conversation history per user."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='chat_messages'
    )
    message = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.timestamp:%Y-%m-%d %H:%M}"