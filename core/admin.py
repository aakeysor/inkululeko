from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, School, Subject, Enrollment,
    MentorAssignment, Attendance, Grade, ChatMessage,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'first_name', 'last_name',
        'role', 'school', 'is_active'
    )
    list_filter = ('role', 'school', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Inkululeko Info', {
            'fields': ('role', 'school', 'phone'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Inkululeko Info', {
        'fields': ('role', 'school', 'phone'),
        }),
    )

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'location')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'school')
    list_filter = ('school',)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('learner', 'subject')
    list_filter = ('subject__school',)

@admin.register(MentorAssignment)
class MentorAssignmentAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'learner')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('learner', 'subject', 'date', 'status', 'marked_by')
    list_filter = ('status', 'date', 'marked_by')
    date_hierarchy = 'date'


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        'learner', 'subject', 'assessment_name',
        'score', 'max_score', 'grade_letter', 'date',
    )
    list_filter = ('subject', 'grade_letter', 'date')
    date_hierarchy = 'date'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp', 'message')
    list_filter = ('user', 'timestamp')
    readonly_fields = ('user', 'message', 'response', 'timestamp')