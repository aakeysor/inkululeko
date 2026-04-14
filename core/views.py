import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import date
from .models import (
User, School, Subject, Enrollment, Attendance, Grade, MentorAssignment, ChatMessage
)
from .forms import (
LoginForm, UserCreateForm, AttendanceFilterForm, GradeForm, ReportCardUploadForm
)
from .decorators import role_required
from .chatbot import get_chat_response
from .ocr import extract_grades_from_image


# ---------------------------------------------------------
# Landing & Authentication
# ---------------------------------------------------------

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/landing.html')


def login_view(request):
    role = request.GET.get('role', '')
    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')

    role_config = {
        'admin': {'label': 'Admin',
                  'bg': 'bg-slate-700',
                  'hover': 'hover:bg-slate-800'},
        'assistant': {'label': 'Classroom Assistant',
                      'bg': 'bg-blue-700',
                      'hover': 'hover:bg-blue-800'},
        'learner': {'label': 'Learner',
                    'bg': 'bg-emerald-700',
                    'hover': 'hover:bg-emerald-800'},
        'mentor': {'label': 'Mentor',
                   'bg': 'bg-amber-700',
                   'hover': 'hover:bg-amber-800'},
    }

    return render(request, 'core/login.html', {
        'form': form,
        'role': role,
        'config': role_config.get(role, role_config['learner']),
    })


def logout_view(request):
    logout(request)
    return redirect('landing')


# ---------------------------------------------------------
# Dashboard Router
# ---------------------------------------------------------

@login_required
def dashboard_view(request):
    user = request.user
    ctx = {}

    if user.role == User.Role.ADMIN:
        ctx['total_learners'] = User.objects.filter(role='learner').count()
        ctx['total_assistants'] = User.objects.filter(role='assistant').count()
        ctx['total_mentors'] = User.objects.filter(role='mentor').count()
        ctx['total_schools'] = School.objects.count()
        ctx['recent_attendance'] = (
            Attendance.objects.select_related('learner', 'subject').order_by('-date')[:10]
        )
        return render(request, 'core/admin_dashboard.html', ctx)

    elif user.role == User.Role.ASSISTANT:
        ctx['subjects'] = (
            Subject.objects.filter(school=user.school)
            if user.school else Subject.objects.none()
        )
        ctx['today_attendance_count'] = Attendance.objects.filter(
            date=date.today(), marked_by=user,
        ).count()
        ctx['recent_grades'] = (
            Grade.objects.filter(recorded_by=user)
            .order_by('-date')[:10]
        )
        return render(request, 'core/assistant_dashboard.html', ctx)

    elif user.role == User.Role.LEARNER:
        ctx['enrollments'] = (
            Enrollment.objects.filter(learner=user)
            .select_related('subject')
        )
        ctx['grades'] = (
            Grade.objects.filter(learner=user)
            .select_related('subject').order_by('-date')[:10]
        )
        ctx['attendance'] = (
            Attendance.objects.filter(learner=user)
            .order_by('-date')[:10]
        )
        total = Attendance.objects.filter(learner=user).count()
        present = Attendance.objects.filter(learner=user, status='present').count()
        ctx['attendance_rate'] = (
            round((present / total) * 100, 1)
            if total > 0 else 0
        )
        avg = Grade.objects.filter(learner=user).aggregate(
            avg=Avg('score'),
        )['avg']
        ctx['avg_score'] = round(avg, 1) if avg else 0
        return render(request, 'core/learner_dashboard.html', ctx)

    elif user.role == User.Role.MENTOR:
        assignments = (
            MentorAssignment.objects.filter(mentor=user)
            .select_related('learner')
        )
        mentee_stats = []
        for a in assignments:
            l = a.learner
            total = Attendance.objects.filter(learner=l).count()
            present = Attendance.objects.filter(
                learner=l, status='present'
            ).count()
            att_rate = (
                round((present / total) * 100, 1)
                if total > 0 else 0
            )
            avg = Grade.objects.filter(learner=l).aggregate(
                avg=Avg('score'),
            )['avg']
            mentee_stats.append({
                'learner': l,
                'attendance_rate': att_rate,
                'avg_score': round(avg, 1) if avg else 0,
            })
        ctx['mentee_stats'] = mentee_stats
        return render(request, 'core/mentor_dashboard.html', ctx)

    return redirect('landing')


# ---------------------------------------------------------
# Attendance
# ---------------------------------------------------------

@login_required
@role_required('admin', 'assistant')
def mark_attendance_view(request):
    form = AttendanceFilterForm()
    if request.user.school:
        form.fields['subject'].queryset = Subject.objects.filter(
            school=request.user.school,
        )

    learners = []
    selected_subject = None
    selected_date = None

    if (request.method == 'GET'
        and 'subject' in request.GET
        and 'date' in request.GET):
        selected_subject = get_object_or_404(
            Subject, pk=request.GET['subject']
        )
        selected_date = request.GET['date']
        learners = (
            User.objects.filter(
                role='learner',
                enrollments_subject=selected_subject,
            ).order_by('last_name', 'first_name')
        )
        existing = dict(
            Attendance.objects.filter(
                subject=selected_subject,
                date=selected_date,
            ).values_list(
                'learner_id',
                'status'
            )
        )
        for l in learners:
            l.att_status = existing.get(l.id, '')

    if request.method == 'POST':
        subject = get_object_or_404(
            Subject, pk=request.POST.get('subject_id'),
        )
        att_date = request.POST.get('date')
        enrolled = User.objects.filter(
            role='learner',
            enrollments_subject=subject,
        )
        for learner in enrolled:
            status = request.POST.get(f'status_{learner.id}', 'absent')
            Attendance.objects.update_or_create(
                learner=learner,
                subject=subject,
                date=att_date,
                defaults={
                    'status': status,
                    'marked_by': request.user,
                },
            )
        messages.success(
            request,
            f'Attendance recorded for {subject.name} on {att_date}.',
        )
        return redirect('mark_attendance')

    return render(request, 'core/mark_attendance.html', {
        'form': form,
        'learners': learners,
        'selected_subject': selected_subject,
        'selected_date': selected_date,
    })


# ---------------------------------------------------------
# Grades
# ---------------------------------------------------------

@login_required
@role_required('admin', 'assistant')
def record_grades_view(request):
    form = GradeForm()
    upload_form = ReportCardUploadForm()

    if request.user.school:
        form.fields['subject'].queryset = Subject.objects.filter(
            school=request.user.school,
        )
    form.fields['learner'].queryset = (
        User.objects.filter(role='learner').order_by('last_name')
    )

    if request.method == 'POST':
        form = GradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.recorded_by = request.user
            grade.save()
            messages.success(
                request,
                f'Grade recorded for {grade.learner.get_full_name()} on {grade.date}.',
            )
            return redirect('record_grades')

    return render(request, 'core/record_grades.html', {
        'form': form,
        'upload_form': upload_form,
    })


# ---------------------------------------------------------
# Report Card Scanning
# ---------------------------------------------------------

@login_required
@role_required('admin', 'assistant')
def scan_report_card_view(request):
    """
    Accepts a photo upload of learner report.
    Uses Ollama to extract grades, then returns the extracted data.
    """
    if request.method != 'POST':
        return redirect('record_grades')

    upload_form = ReportCardUploadForm(request.POST, request.FILES)
    if not upload_form.is_valid():
        messages.error(request, 'Invalid form.')
        return redirect('record_grades')

    learner = upload_form.cleaned_data['learner']
    image = upload_form.cleaned_data['image']

    # Extract grades
    extracted = extracted_grades_from_image(image)

    if not extracted:
        messages.error(
            request,
            'Could not extract grades from image. Please try again, or enter manually.'
        )
        return redirect('record_grades')

    # Try to match extracted subject names to database subjects
    learner_school = learner.school
    matched_grades = []
    for entry in extracted:
        subject_name = entry.get('subject', '')
        subject = Subject.objects.filter(
            name_icontains=subject_name,
            school=learner_school,
        ).first()
        matched_grades.append({
            'subject_name': subject_name,
            'subject_id': subject.id if subject else None,
            'score': entry.get('score', 0),
            'max_score': entry.get('max_score', 100),
            'matched': subject is not None,
        })

    return render(request, 'core/confirm_scanned_grades.html', {
        'learner': learner,
        'matched_grades': matched_grades,
        'subjects': Subject.objects.filter(school=learner_school),
    })


@login_required
@role_required('admin', 'assistant')
def save_scanned_grades_view(request):
    """
    Save confirmed grades from a scanned learner report.
    """
    if request.method != 'POST':
        return redirect('record_grades')

    learner_id = request.POST.get('learner_id')
    learner = get_object_or_404(User, pk=learner_id, role='learner')
    grade_count = int(request.POST.get('grade_count', 0))
    saved = 0

    for i in range(grade_count):
        subject_id = request.POST.get(f'subject_id_{i}')
        score = request.POST.get(f'score_{i}')
        max_score = request.POST.get(f'max_score_{i}')
        include = request.POST.get(f'include_{i}')

        if include and subject_id and score:
            subject = get_object_or_404(Subject, pk=subject_id)
            Grade.objects.create(
                learner=learner,
                subject=subject,
                assessment_name='Report Card',
                score=float(score),
                max_score=float(max_score or 100),
                date=date.today(),
                recorded_by=request.user,
                notes='Extracted from uploaded learner report',
            )
            saved += 1

    messages.success(
        request,
        f'{saved} grade(s) saved for {learner.get_full_name()} on {date.today()}.',
    )
    return redirect('record_grades')


# ---------------------------------------------------------
# Chatbot API
# ---------------------------------------------------------

@login_required
@require_POST
def chatbot_api_view(request):
    """
    AJAX endpoint for chatbot.
    Accepts a JSON message, returns a JSON response.
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    if not user_message:
        return JsonResponse({'error': 'Empty message.'}, status=400)

    # Get recent conversation history for context
    recent = ChatMessage.objects.filter(
        user=request.user,
    ).order_by('-timestamp')[:5]
    history = [
        {'message': m.message, 'response': m.response}
        for m in reversed(recent)
    ]

    # AI Response
    bot_response = get_chat_response(
        user_message=user_message,
        user_role=request.user.get_role_display(),
        conversation_history=history,
    )

    # Save to database
    ChatMessage.objects.create(
        user=request.user,
        message=user_message,
        response=bot_response,
    )

    return JsonResponse({'response': bot_response})


# ---------------------------------------------------------
# User Management (Admin Only)
# ---------------------------------------------------------

@login_required
@role_required('admin')
def manage_users_view(request):
    users = User.objects.all().order_by('role', 'last_name')
    form = UserCreateForm()

    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(
                request, f'User {user.username} created successfully.',
            )
            return redirect('manage_users')

    return redirect(request, 'core/manage_users.html', {
        'users': users,
        'form': form,
    })


# ---------------------------------------------------------
# Learner Progress
# ---------------------------------------------------------

@login_required
def learner_progress_view(request, learner_id):
    learner = get_object_or_404(User, pk=learner_id, role='learner')
    user = request.user

    allowed = (
        user.role in ('admin', 'assistant')
        or user.id == learner.id
        or (
            user.role == 'mentor'
            and MentorAssignment.objects.filter(
                mentor=user,
                learner=learner,
            ).exists()
        )
    )
    if not allowed:
        return redirect('dashboard')

    grades = (
        Grade.objects.filter(learner=learner)
        .select_related('subject').order_by('date')
    )
    attendance = (
        Attendance.objects.filter(learner=learner)
        .order_by('-date')[:30]
    )

    subjects = Subject.objects.filter(enrollments_learner=learner)
    subject_stats = []
    for subj in subjects:
        avg = (
            Grade.objects.filter(learner=learner, subject=subj)
            .aggregate(avg=Avg('score'))['avg'] or 0
        )
        total_att = Attendance.objects.filter(
            learner=learner, subject=subj
        ).count()
        present_att = Attendance.objects.filter(
            learner=learner, subject=subj, status='present',
        ).count()
        att_rate = (
            round((present_att / total_att) * 100, 1)
            if total_att > 0 else 0
        )
        subject_stats.append({
            'subject': subj,
            'avg_score': round(avg, 1),
            'attendance_rate': att_rate,
        })

    return render(request, 'core/learner_progress.html', {
        'learner': learner,
        'grades': grades,
        'attendance': attendance,
        'subject_stats': subject_stats,
    })


