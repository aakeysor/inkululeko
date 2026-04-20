from django.urls import path
from . import views

urlpatterns = [
    # Landing & Authentication
    path('', views.landing_view, name='landing'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboards
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Attendance & Grades
    path('attendance/', views.mark_attendance_view, name='mark_attendance'),
    path('grades/', views.record_grades_view, name='record_grades'),

    # Report Card Scanning
    path('grades/scan/', views.scan_report_card_view, name='scan_report_card'),
    path('grades/scan/save/', views.save_scanned_grades_view, name='save_scanned_grades'),

    # User Management
    path('users/', views.manage_users_view, name='manage_users'),

    # Learner Progress
    path('progress/<int:learner_id>/', views.learner_progress_view, name='learner_progress'),

    # Chatbot API
    path('api/chat/', views.chatbot_api_view, name='chatbot_api'),

    # Manage Schools
    path('schools/', views.manage_schools_view, name='manage_schools'),

    # View Learners
    path('schools/<int:school_id>/learners/', views.school_members_view, {'member_type': 'learner'}, name='school_learners'),

    # View Assistants
    path('schools/<int:school_id>/assistants/', views.school_members_view, {'member_type': 'assistant'}, name='school_assistants'),

    path('users/list/', views.user_list_view, name='user_list'),
    path('api/user/<int:user_id>/', views.user_detail_api, name='user_detail_api'),
    path('reports/', views.reports_view, name='reports'),
    path('directory/', views.student_directory_view, name='student_directory'),
    path('users/<int:user_id>/delete/', views.delete_user_view, name='delete_user'),
    path('schools/<int:school_id>/delete/', views.delete_school_view, name='delete_school'),
    path('assign-tutor/', views.assign_tutor_view, name='assign_tutor'),
    path('api/learner/<int:learner_id>/mentors/', views.learner_mentors_api, name='learner_mentors_api'),
    path('request-mentor/', views.request_mentor_view, name='request_mentor'),
    path('mentor-request/<int:request_id>/respond/', views.respond_mentor_request_view, name='respond_mentor_request'),
    path('enrollments/', views.manage_enrollments_view, name='manage_enrollments'),
    path('api/learner/<int:learner_id>/subjects/', views.learner_subjects_api, name='learner_subjects_api'),
    path('reports/attendance/', views.attendance_report_view, name='report_attendance'),
    path('reports/marks/', views.mark_report_view, name='report_marks'),
    path('reports/mentor-hours/', views.mentor_hours_report_view, name='report_mentor_hours'),
    path('reports/learner/<int:learner_id>/', views.learner_report_view, name='learner_report'),
]