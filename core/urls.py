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
]