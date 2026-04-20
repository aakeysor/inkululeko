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
    display_id = models.CharField(max_length=10, unique=True, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    grade_level = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    parent_guardian_name = models.CharField(max_length=200, blank=True)
    parent_guardian_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # Assistant-specific fields
    subject_taught = models.CharField(max_length=100, blank=True)
    grade_levels_taught = models.CharField(max_length=100, blank=True)
    experience_years = models.PositiveIntegerField(null=True, blank=True)
    qualifications = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    specializations = models.TextField(blank=True)

    # Mentor-specific fields
    organization = models.CharField(max_length=200, blank=True)
    focus_areas = models.CharField(max_length=200, blank=True)
    background = models.CharField(max_length=200, blank=True)
    availability = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        if not self.display_id:
            prefix_map = {
                'admin': '0',
                'assistant': '1',
                'mentor': '2',
                'learner': '3',
            }
            prefix = prefix_map.get(self.role, '0')
            last_user = (
                User.objects.filter(display_id__startswith=prefix)
                .order_by('-display_id')
                .first()
            )
            if last_user and last_user.display_id:
                last_num = int(last_user.display_id[1:])
                new_num = last_num + 1
            else:
                new_num = 1
            self.display_id = f"{prefix}{new_num:03d}"
        super().save(*args, **kwargs)

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
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name



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
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name='mentor_assignments',
        null=True, blank=True,
    )
    is_general = models.BooleanField(default=False)

    class Meta:
        unique_together = ('mentor', 'learner', 'subject')

    def __str__(self):
        subj = 'General' if self.is_general or not self.subject else self.subject.name
        return (
            f"{self.mentor.get_full_name()} mentors "
            f"{self.learner.get_full_name()} ({subj})"
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
                self.grade_letter = '7'
            elif pct >= 70:
                self.grade_letter = '6'
            elif pct >= 60:
                self.grade_letter = '5'
            elif pct >= 50:
                self.grade_letter = '4'
            elif pct >= 40:
                self.grade_letter = '3'
            elif pct >= 30:
                self.grade_letter = '2'
            else:
                self.grade_letter = '1'
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


class ActivityLog(models.Model):
    class ActionType(models.TextChoices):
        ATTENDANCE = 'attendance', 'Attendance'
        GRADE = 'grade', 'Grade'
        ENROLLMENT = 'enrollment', 'Enrollment'
        USER_CREATED = 'user_created', 'User Created'
        LOGIN = 'login', 'Login'

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='activity_logs'
    )
    action_type = models.CharField(
        max_length=20, choices=ActionType.choices
    )
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.description}"


class TutoringSession(models.Model):
    learner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='tutoring_sessions_as_learner',
        limit_choices_to={'role': 'learner'}
    )
    tutor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='tutoring_sessions_as_tutor',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name='tutoring_sessions'
    )
    date = models.DateField()
    duration_minutes = models.PositiveIntegerField(default=60)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return (
            f"{self.learner.get_full_name()} — {self.subject.name} "
            f"with {self.tutor.get_full_name()} on {self.date}"
        )


class MentorRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        DENIED = 'denied', 'Denied'

    learner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mentor_requests',
        limit_choices_to={'role': 'learner'}
    )
    mentor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='mentor_requests_received',
        limit_choices_to={'role': 'mentor'}
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE,
        related_name='mentor_requests',
        null=True, blank=True,
    )
    is_general = models.BooleanField(default=False)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        subj = 'General' if self.is_general else (self.subject.name if self.subject else '—')
        return f"{self.learner.get_full_name()} → {self.mentor.get_full_name()} ({subj}) [{self.status}]"


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