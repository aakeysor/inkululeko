import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Avg
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import date
from .models import (
User, School, Subject, Enrollment, Attendance, Grade, MentorAssignment, ChatMessage,
ActivityLog, TutoringSession, MentorRequest,
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
        ctx['total_learners']   = User.objects.filter(role='learner').count()
        ctx['total_assistants'] = User.objects.filter(role='assistant').count()
        ctx['total_mentors']    = User.objects.filter(role='mentor').count()
        ctx['total_schools']    = School.objects.count()
        ctx['recent_activity'] = ActivityLog.objects.select_related('user').order_by('-timestamp')[:10]
        return render(request, 'core/admin_dashboard.html', ctx)

    elif user.role == User.Role.ASSISTANT:
        from django.db.models import Max, Min

        subjects = (
            Subject.objects.filter(school=user.school)
            if user.school else Subject.objects.none()
        )

        selected_subject_id = request.GET.get('subject', '')
        selected_subject = None

        if selected_subject_id:
            selected_subject = Subject.objects.filter(pk=selected_subject_id).first()
        elif subjects.exists():
            selected_subject = subjects.first()

        # Build subject list with enrollment counts
        subject_list = []
        for subj in subjects:
            count = Enrollment.objects.filter(subject=subj).count()
            subject_list.append({'subject': subj, 'count': count})

        enrolled = User.objects.none()
        enrolled_count = 0
        current_avg = 0
        passing_count = 0
        honor_count = 0
        top_performers = []
        needs_support = []
        monthly_avgs = []
        assessment_stats = []
        level_distribution = []
        today_present = 0
        today_absent = 0

        if selected_subject:
            enrolled = User.objects.filter(
                role='learner', enrollments__subject=selected_subject,
            )
            enrolled_count = enrolled.count()

            # Current class average
            avg = Grade.objects.filter(
                subject=selected_subject, learner__in=enrolled,
            ).aggregate(avg=Avg('score'))['avg']
            current_avg = round(avg, 1) if avg else 0

            # Per-learner stats
            learner_stats = []
            for learner in enrolled:
                lavg = Grade.objects.filter(
                    learner=learner, subject=selected_subject,
                ).aggregate(avg=Avg('score'))['avg']
                if lavg:
                    lavg = round(lavg, 1)
                    learner_stats.append({'learner': learner, 'avg': lavg})
                    if lavg >= 50:
                        passing_count += 1
                    if lavg >= 80:
                        honor_count += 1

            # Sort for top performers and needs support
            learner_stats.sort(key=lambda x: x['avg'], reverse=True)
            top_performers = learner_stats[:5]
            needs_support = [s for s in learner_stats if s['avg'] < 70]

            # Monthly class averages for line chart
            monthly = (
                Grade.objects.filter(
                    subject=selected_subject, learner__in=enrolled,
                )
                .annotate(month=TruncMonth('date'))
                .values('month')
                .annotate(avg=Avg('score'))
                .order_by('month')
            )
            monthly_avgs = [{
                'month': m['month'].strftime('%B'),
                'avg': round(m['avg'], 1),
            } for m in monthly]

            # Per-assessment stats for bar chart
            assessments = (
                Grade.objects.filter(
                    subject=selected_subject, learner__in=enrolled,
                )
                .values('assessment_name')
                .annotate(
                    avg=Avg('score'),
                    highest=Max('score'),
                    lowest=Min('score'),
                )
                .order_by('assessment_name')
            )
            assessment_stats = [{
                'name': a['assessment_name'],
                'avg': round(float(a['avg']), 1),
                'highest': round(float(a['highest']), 1),
                'lowest': round(float(a['lowest']), 1),
            } for a in assessments]

            # Level distribution
            level_ranges = [
                ('7 (80-100%)', 80, 101),
                ('6 (70-79%)', 70, 80),
                ('5 (60-69%)', 60, 70),
                ('4 (50-59%)', 50, 60),
                ('3 (40-49%)', 40, 50),
                ('2 (30-39%)', 30, 40),
                ('1 (0-29%)', 0, 30),
            ]
            for label, lo, hi in level_ranges:
                count = 0
                for ls in learner_stats:
                    if lo <= ls['avg'] < hi:
                        count += 1
                level_distribution.append({'label': label, 'count': count})

            # Today's attendance
            today_present = Attendance.objects.filter(
                subject=selected_subject, date=date.today(), status='present',
            ).count()
            today_absent = Attendance.objects.filter(
                subject=selected_subject, date=date.today(), status='absent',
            ).count()

        import json
        ctx.update({
            'subjects': subjects,
            'subject_list': subject_list,
            'selected_subject': selected_subject,
            'enrolled_count': enrolled_count,
            'current_avg': current_avg,
            'passing_count': passing_count,
            'honor_count': honor_count,
            'top_performers': top_performers,
            'needs_support': needs_support,
            'monthly_avgs_json': json.dumps(monthly_avgs, default=str),
            'assessment_stats_json': json.dumps(assessment_stats, default=str),
            'level_distribution_json': json.dumps(level_distribution, default=str),
            'today_present': today_present,
            'today_absent': today_absent,
            'mentors': User.objects.filter(role='mentor').order_by('last_name'),
        })
        return render(request, 'core/assistant_dashboard.html', ctx)


    elif user.role == User.Role.LEARNER:

        import json as json_lib

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

        present = Attendance.objects.filter(

            learner=user, status='present',

        ).count()

        ctx['attendance_rate'] = (

            round((present / total) * 100, 1) if total > 0 else 0

        )

        avg = Grade.objects.filter(learner=user).aggregate(

            avg=Avg('score'),

        )['avg']

        ctx['avg_score'] = round(avg, 1) if avg else 0

        # Monthly grades for graph

        monthly = (

            Grade.objects.filter(learner=user)

            .annotate(month=TruncMonth('date'))

            .values('month')

            .annotate(avg=Avg('score'))

            .order_by('month')

        )

        monthly_avgs = [{

            'month': m['month'].strftime('%B'),

            'avg': round(float(m['avg']), 1),

        } for m in monthly]

        ctx['monthly_avgs_json'] = json_lib.dumps(monthly_avgs, default=str)

        # Per-subject monthly for dropdown

        subjects = Subject.objects.filter(enrollments__learner=user)

        subject_monthly = {}

        for subj in subjects:
            sm = (

                Grade.objects.filter(learner=user, subject=subj)

                .annotate(month=TruncMonth('date'))

                .values('month')

                .annotate(avg=Avg('score'))

                .order_by('month')

            )

            subject_monthly[subj.name] = [{

                'month': m['month'].strftime('%B'),

                'avg': round(float(m['avg']), 1),

            } for m in sm]

        ctx['subject_monthly_json'] = json_lib.dumps(subject_monthly, default=str)

        ctx['subject_names_json'] = json_lib.dumps([s.name for s in subjects])

        # Available mentors and pending requests

        ctx['mentors'] = User.objects.filter(role='mentor').order_by('last_name')

        ctx['subjects'] = subjects

        ctx['pending_requests'] = MentorRequest.objects.filter(

            learner=user, status='pending',

        ).select_related('mentor', 'subject')

        return render(request, 'core/learner_dashboard.html', ctx)



    elif user.role == User.Role.MENTOR:

        assignments = (

            MentorAssignment.objects.filter(mentor=user)

            .select_related('learner', 'subject')

        )

        mentee_stats = []

        seen_learners = set()

        for a in assignments:

            if a.learner.id in seen_learners:
                continue

            seen_learners.add(a.learner.id)

            l = a.learner

            total = Attendance.objects.filter(learner=l).count()

            present = Attendance.objects.filter(

                learner=l, status='present',

            ).count()

            att_rate = (

                round((present / total) * 100, 1) if total > 0 else 0

            )

            avg = Grade.objects.filter(learner=l).aggregate(

                avg=Avg('score'),

            )['avg']

            mentee_stats.append({

                'learner': l,

                'attendance_rate': att_rate,

                'avg_score': round(avg, 1) if avg else 0,

            })

        pending_requests = MentorRequest.objects.filter(

            mentor=user, status='pending',

        ).select_related('learner', 'subject')

        ctx['mentee_stats'] = mentee_stats

        ctx['pending_requests'] = pending_requests

        return render(request, 'core/mentor_dashboard.html', ctx)


# ---------------------------------------------------------
# Attendance
# ---------------------------------------------------------

@login_required
@role_required('admin', 'assistant')
def mark_attendance_view(request):
    form = AttendanceFilterForm()
    form.fields['subject'].queryset = Subject.objects.all().order_by('name')

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
                enrollments=selected_subject,
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
            enrollments=subject,
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
            ActivityLog.objects.create(
                user=request.user,
                action_type='attendance',
                description=f'{request.user.get_full_name()} marked attendance for {subject.name}',
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

    form.fields['learner'].queryset = (
        User.objects.filter(role='learner').order_by('last_name')
    )
    form.fields['subject'].queryset = Subject.objects.all().order_by('name')

    if request.method == 'POST':
        form = GradeForm(request.POST)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.recorded_by = request.user
            grade.save()
            ActivityLog.objects.create(
                user=request.user,
                action_type='grade',
                description=f'{request.user.get_full_name()} updated marks for {grade.subject.name}',
            )
            messages.success(
                request,
                f'Grade recorded for {grade.learner.get_full_name()}.',
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
    from .forms import (
        LearnerCreateForm, AssistantCreateForm,
        MentorCreateForm, AdminCreateForm,
    )

    add_role = request.GET.get('add', '')
    show_form = add_role in ('learner', 'assistant', 'mentor', 'admin')

    role_labels = {
        'learner': 'Learner',
        'assistant': 'Classroom Assistant',
        'mentor': 'Mentor',
        'admin': 'Admin',
    }

    form_classes = {
        'learner': LearnerCreateForm,
        'assistant': AssistantCreateForm,
        'mentor': MentorCreateForm,
        'admin': AdminCreateForm,
    }

    FormClass = form_classes.get(add_role, AdminCreateForm)
    form = FormClass()

    # Calculate next ID preview
    next_id = ''
    if add_role:
        prefix_map = {'admin': '0', 'assistant': '1', 'mentor': '2', 'learner': '3'}
        prefix = prefix_map.get(add_role, '0')
        last_user = (
            User.objects.filter(display_id__startswith=prefix)
            .order_by('-display_id').first()
        )
        if last_user and last_user.display_id:
            next_num = int(last_user.display_id[1:]) + 1
        else:
            next_num = 1
        next_id = f"{prefix}{next_num:03d}"

    if show_form:
        form.fields['role'].initial = add_role

    if request.method == 'POST':
        role_preset = request.POST.get('role_preset', '')
        FormClass = form_classes.get(role_preset, AdminCreateForm)
        form = FormClass(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            if role_preset in role_labels:
                user.role = role_preset
            user.save()
            ActivityLog.objects.create(
                user=request.user,
                action_type='user_created',
                description=f'New {user.get_role_display().lower()} enrolled: {user.get_full_name()}',
            )
            messages.success(
                request, f'User {user.username} created. ID: {user.display_id}',
            )
            return redirect('manage_users')
        else:
            show_form = True
            add_role = role_preset
            # Recalculate next_id
            prefix = {'admin': '0', 'assistant': '1', 'mentor': '2', 'learner': '3'}.get(add_role, '0')
            last_user = User.objects.filter(display_id__startswith=prefix).order_by('-display_id').first()
            next_num = int(last_user.display_id[1:]) + 1 if last_user and last_user.display_id else 1
            next_id = f"{prefix}{next_num:03d}"

    return render(request, 'core/manage_users.html', {
        'form': form,
        'show_form': show_form,
        'form_role': add_role,
        'form_role_label': role_labels.get(add_role, ''),
        'next_id': next_id,
    })


@login_required
@role_required('admin')
def user_list_view(request):
    role_filter = request.GET.get('role', '')
    users = User.objects.all().order_by('last_name', 'first_name')

    labels = {
        'learner': 'Learners',
        'assistant': 'Classroom Assistants',
        'mentor': 'Mentors',
        'admin': 'Admins',
    }

    if role_filter in labels:
        users = users.filter(role=role_filter)

    search = request.GET.get('search', '').strip()
    if search:
        users = users.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(username__icontains=search)
        )

    label = labels.get(role_filter, 'All Users')

    return render(request, 'core/user_list.html', {
        'users': users,
        'label': label,
        'role_filter': role_filter,
        'search': search,
    })


@login_required
def user_detail_api(request, user_id):
    """Returns user details as JSON for the popup. Accessible by admin and assistant."""
    if request.user.role not in ('admin', 'assistant'):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    u = get_object_or_404(User, pk=user_id)

    # Assistants can only view learners
    if request.user.role == 'assistant' and u.role != 'learner':
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = {
        'id': u.display_id or u.id,
        'full_name': u.get_full_name() or u.username,
        'username': u.username,
        'email': u.email or '—',
        'phone': u.phone or '—',
        'role': u.get_role_display(),
        'role_key': u.role,
        'school': u.school.name if u.school else '—',
        'is_active': u.is_active,
        'date_joined': u.date_joined.strftime('%Y-%m-%d'),
        'date_of_birth': u.date_of_birth.strftime('%Y-%m-%d') if u.date_of_birth else '—',
        'grade_level': u.grade_level or '—',
        'address': u.address or '—',
        'parent_guardian_name': u.parent_guardian_name or '—',
        'parent_guardian_phone': u.parent_guardian_phone or '—',
        'emergency_contact_name': u.emergency_contact_name or '—',
        'emergency_contact_phone': u.emergency_contact_phone or '—',
    }

    if u.role == 'learner':
        total = Attendance.objects.filter(learner=u).count()
        present = Attendance.objects.filter(learner=u, status='present').count()
        data['attendance_rate'] = round((present / total) * 100, 1) if total > 0 else 0
        data['attendance_present'] = present
        data['attendance_total'] = total

        avg = Grade.objects.filter(learner=u).aggregate(avg=Avg('score'))['avg']
        data['avg_score'] = round(avg, 1) if avg else 0

        # Per-subject current marks
        data['enrolled_subjects'] = []
        subjects = Subject.objects.filter(enrollments__learner=u)
        for subj in subjects:
            subj_avg = Grade.objects.filter(
                learner=u, subject=subj
            ).aggregate(avg=Avg('score'))['avg']
            data['enrolled_subjects'].append({
                'id': subj.id,
                'name': subj.name,
                'avg_score': round(subj_avg, 1) if subj_avg else 0,
            })

        # Monthly grade averages for the graph (grouped by month)
        monthly = (
            Grade.objects.filter(learner=u)
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(avg=Avg('score'))
            .order_by('month')
        )
        data['monthly_grades'] = [{
            'month': m['month'].strftime('%b %Y'),
            'avg': round(m['avg'], 1),
        } for m in monthly]

        # Per-subject monthly for graph dropdown
        data['subject_monthly'] = {}
        for subj in subjects:
            subj_monthly = (
                Grade.objects.filter(learner=u, subject=subj)
                .annotate(month=TruncMonth('date'))
                .values('month')
                .annotate(avg=Avg('score'))
                .order_by('month')
            )
            data['subject_monthly'][subj.name] = [{
                'month': m['month'].strftime('%b %Y'),
                'avg': round(m['avg'], 1),
            } for m in subj_monthly]

        # Recent attendance
        data['recent_attendance'] = list(
            Attendance.objects.filter(learner=u)
            .order_by('-date')[:10]
            .values('date', 'status')
        )
        for r in data['recent_attendance']:
            r['date'] = r['date'].strftime('%Y-%m-%d')

        # Tutoring sessions
        sessions = TutoringSession.objects.filter(
            learner=u
        ).select_related('subject', 'tutor').order_by('-date')[:5]
        data['tutoring_sessions'] = [{
            'subject': s.subject.name,
            'tutor': s.tutor.get_full_name(),
            'date': s.date.strftime('%Y-%m-%d'),
            'duration': f"{s.duration_minutes} mins" if s.duration_minutes < 60 else f"{s.duration_minutes // 60} hour{'s' if s.duration_minutes >= 120 else ''}",
            'notes': s.notes,
        } for s in sessions]
        data['total_tutoring_sessions'] = TutoringSession.objects.filter(learner=u).count()

    elif u.role == 'assistant':
        data['subject_taught'] = u.subject_taught or '—'
        data['grade_levels_taught'] = u.grade_levels_taught or '—'
        data['experience_years'] = u.experience_years or 0
        data['qualifications'] = u.qualifications or '—'
        data['certifications'] = u.certifications or '—'
        data['specializations'] = u.specializations or '—'

        # Stats
        data['students_taught'] = User.objects.filter(
            role='learner', school=u.school
        ).count() if u.school else 0

        data['recent_activity'] = list(
            ActivityLog.objects.filter(user=u)
            .order_by('-timestamp')[:5]
            .values('description', 'timestamp')
        )
        for a in data['recent_activity']:
            a['timestamp'] = a['timestamp'].strftime('%Y-%m-%d %H:%M')

    elif u.role == 'mentor':
        data['organization'] = u.organization or '—'
        data['focus_areas'] = u.focus_areas or '—'
        data['background'] = u.background or '—'
        data['availability'] = u.availability or '—'

        # Stats
        mentee_ids = MentorAssignment.objects.filter(
            mentor=u
        ).values_list('learner_id', flat=True)
        data['students_mentored'] = len(mentee_ids)

        total_sessions = TutoringSession.objects.filter(tutor=u)
        data['total_hours'] = round(
            sum(s.duration_minutes for s in total_sessions) / 60
        )

        from django.utils import timezone
        from datetime import timedelta
        month_ago = timezone.now() - timedelta(days=30)
        data['sessions_this_month'] = TutoringSession.objects.filter(
            tutor=u, date__gte=month_ago
        ).count()

        months_active = 0
        if u.date_joined:
            diff = timezone.now() - u.date_joined
            months_active = max(1, diff.days // 30)
        data['months_active'] = months_active

        data['mentees'] = list(
            MentorAssignment.objects.filter(mentor=u)
            .values_list('learner__first_name', 'learner__last_name')
        )
        data['mentees'] = [f"{f} {l}" for f, l in data['mentees']]

        # Recent tutoring sessions
        sessions = TutoringSession.objects.filter(
            tutor=u
        ).select_related('subject', 'learner').order_by('-date')[:5]
        data['recent_sessions'] = [{
            'learner': s.learner.get_full_name(),
            'subject': s.subject.name,
            'date': s.date.strftime('%Y-%m-%d'),
            'duration': f"{s.duration_minutes} mins" if s.duration_minutes < 60 else f"{s.duration_minutes // 60} hour{'s' if s.duration_minutes >= 120 else ''}",
        } for s in sessions]

        data['recent_activity'] = list(
            ActivityLog.objects.filter(user=u)
            .order_by('-timestamp')[:5]
            .values('description', 'timestamp')
        )
        for a in data['recent_activity']:
            a['timestamp'] = a['timestamp'].strftime('%Y-%m-%d %H:%M')

    return JsonResponse(data)


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

    subjects = Subject.objects.filter(enrollments__learner=learner)
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


@login_required
@role_required('admin')
def manage_schools_view(request):
    from .forms import SchoolForm
    schools = School.objects.all().order_by('name')
    form = SchoolForm()

    school_data = []
    for school in schools:
        school_data.append({
            'school': school,
            'learner_count': User.objects.filter(school=school, role='learner').count(),
            'assistant_count': User.objects.filter(school=school, role='assistant').count(),
        })

    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'School "{form.cleaned_data["name"]}" created.',
            )
            return redirect('manage_schools')

    return render(request, 'core/manage_schools.html', {
        'school_data': school_data, 'form': form,
    })


@login_required
@role_required('admin')
def school_members_view(request, school_id, member_type):
    school = get_object_or_404(School, pk=school_id)
    members = User.objects.filter(school=school, role=member_type)

    # Filtering
    search = request.GET.get('search', '').strip()
    if search:
        members = members.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(username__icontains=search)
        )

    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        members = members.filter(is_active=True)
    elif status_filter == 'inactive':
        members = members.filter(is_active=False)

    members = members.order_by('last_name', 'first_name')

    labels = {
        'learner': 'Learners',
        'assistant': 'Classroom Assistants',
        'mentor': 'Mentors',
    }
    label = labels.get(member_type, 'Users')

    return render(request, 'core/school_members.html', {
        'school': school,
        'members': members,
        'member_type': member_type,
        'label': label,
        'search': search,
        'status_filter': status_filter,
    })


@login_required
@role_required('admin')
def reports_view(request):
    learners = User.objects.filter(role='learner').order_by('last_name')
    return render(request, 'core/reports.html', {'learners': learners})


@login_required
@role_required('assistant')
def student_directory_view(request):
    learners = User.objects.filter(role='learner')
    if request.user.school:
        learners = learners.filter(school=request.user.school)

    search = request.GET.get('search', '').strip()
    if search:
        learners = learners.filter(
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(username__icontains=search)
        )

    learners = learners.order_by('last_name', 'first_name')

    return render(request, 'core/student_directory.html', {
        'learners': learners,
        'search': search,
    })


@login_required
@role_required('admin')
@require_POST
def delete_user_view(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    if u.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('manage_users')
    if u.is_superuser:
        messages.error(request, "Cannot delete a superuser.")
        return redirect('manage_users')
    name = u.get_full_name() or u.username
    u.delete()
    messages.success(request, f'User "{name}" has been deleted.')
    return redirect('user_list')


@login_required
@role_required('admin')
@require_POST
def delete_school_view(request, school_id):
    school = get_object_or_404(School, pk=school_id)
    name = school.name
    school.delete()
    messages.success(request, f'School "{name}" has been deleted.')
    return redirect('manage_schools')


@login_required
@role_required('admin', 'assistant')
@require_POST
def assign_tutor_view(request):
    learner_id = request.POST.get('learner_id')
    mentor_id = request.POST.get('mentor_id')
    subject_ids = request.POST.getlist('subject_ids')

    if not learner_id or not mentor_id:
        messages.error(request, 'Please select both a learner and a mentor.')
        return redirect('dashboard')

    learner = get_object_or_404(User, pk=learner_id, role='learner')
    mentor = get_object_or_404(User, pk=mentor_id, role='mentor')

    # Get all subjects the learner is enrolled in
    enrolled_subjects = Subject.objects.filter(enrollments__learner=learner)
    enrolled_ids = set(enrolled_subjects.values_list('id', flat=True))

    if not subject_ids or set(int(s) for s in subject_ids) >= enrolled_ids:
        # All subjects selected or none selected — assign as general
        MentorAssignment.objects.filter(mentor=mentor, learner=learner).delete()
        MentorAssignment.objects.create(
            mentor=mentor, learner=learner, subject=None, is_general=True,
        )
        messages.success(
            request,
            f'{mentor.get_full_name()} assigned as general mentor for {learner.get_full_name()}.',
        )
    else:
        for sid in subject_ids:
            subject = get_object_or_404(Subject, pk=sid)
            MentorAssignment.objects.get_or_create(
                mentor=mentor, learner=learner, subject=subject,
                defaults={'is_general': False},
            )
        subject_names = ', '.join(
            Subject.objects.filter(pk__in=subject_ids).values_list('name', flat=True)
        )
        messages.success(
            request,
            f'{mentor.get_full_name()} assigned for {subject_names} for {learner.get_full_name()}.',
        )

    return redirect('dashboard')



@login_required
@role_required('admin', 'assistant')
def learner_mentors_api(request, learner_id):
    """Returns current mentor assignments for a learner as JSON."""
    learner = get_object_or_404(User, pk=learner_id, role='learner')
    assignments = MentorAssignment.objects.filter(
        learner=learner
    ).select_related('mentor', 'subject')

    data = []
    for a in assignments:
        data.append({
            'mentor_name': a.mentor.get_full_name(),
            'subject': 'General' if a.is_general or not a.subject else a.subject.name,
        })

    return JsonResponse({'assignments': data})


@login_required
@role_required('learner')
@require_POST
def request_mentor_view(request):
    mentor_id = request.POST.get('mentor_id')
    subject_ids = request.POST.getlist('subject_ids')
    message = request.POST.get('message', '').strip()

    if not mentor_id:
        messages.error(request, 'Please select a mentor.')
        return redirect('dashboard')

    mentor = get_object_or_404(User, pk=mentor_id, role='mentor')
    learner = request.user

    enrolled_subjects = Subject.objects.filter(enrollments__learner=learner)
    enrolled_ids = set(enrolled_subjects.values_list('id', flat=True))

    if not subject_ids or set(int(s) for s in subject_ids) >= enrolled_ids:
        MentorRequest.objects.create(
            learner=learner, mentor=mentor,
            subject=None, is_general=True, message=message,
        )
    else:
        for sid in subject_ids:
            subject = get_object_or_404(Subject, pk=sid)
            MentorRequest.objects.create(
                learner=learner, mentor=mentor,
                subject=subject, is_general=False, message=message,
            )

    messages.success(request, f'Mentor request sent to {mentor.get_full_name()}.')
    return redirect('dashboard')



@login_required
@role_required('mentor')
@require_POST
def respond_mentor_request_view(request, request_id):
    mentor_request = get_object_or_404(
        MentorRequest, pk=request_id, mentor=request.user
    )
    action = request.POST.get('action')

    if action == 'approve':
        mentor_request.status = 'approved'
        mentor_request.save()
        # Create the actual assignment
        if mentor_request.is_general:
            MentorAssignment.objects.get_or_create(
                mentor=request.user,
                learner=mentor_request.learner,
                subject=None,
                defaults={'is_general': True},
            )
        else:
            MentorAssignment.objects.get_or_create(
                mentor=request.user,
                learner=mentor_request.learner,
                subject=mentor_request.subject,
                defaults={'is_general': False},
            )
        messages.success(
            request,
            f'Approved mentoring request from {mentor_request.learner.get_full_name()}.',
        )
    elif action == 'deny':
        mentor_request.status = 'denied'
        mentor_request.save()
        messages.success(
            request,
            f'Denied mentoring request from {mentor_request.learner.get_full_name()}.',
        )

    return redirect('dashboard')


@login_required
@role_required('admin', 'assistant')
def manage_enrollments_view(request):
    learners = User.objects.filter(role='learner').order_by('last_name')
    subjects = Subject.objects.all().order_by('name')

    selected_learner = None
    enrolled_subjects = []

    if request.GET.get('learner'):
        selected_learner = get_object_or_404(
            User, pk=request.GET['learner'], role='learner'
        )
        enrolled_subjects = list(
            Enrollment.objects.filter(learner=selected_learner)
            .values_list('subject_id', flat=True)
        )

    if request.method == 'POST':
        learner_id = request.POST.get('learner_id')
        learner = get_object_or_404(User, pk=learner_id, role='learner')
        selected_subject_ids = request.POST.getlist('subjects')

        Enrollment.objects.filter(learner=learner).delete()

        for sid in selected_subject_ids:
            subject = get_object_or_404(Subject, pk=sid)
            Enrollment.objects.create(learner=learner, subject=subject)

        messages.success(
            request,
            f'Updated class registrations for {learner.get_full_name()}.',
        )
        return redirect(f'/enrollments/?learner={learner.id}')

    return render(request, 'core/manage_enrollments.html', {
        'learners': learners,
        'subjects': subjects,
        'selected_learner': selected_learner,
        'enrolled_subjects': enrolled_subjects,
    })


@login_required
def learner_subjects_api(request, learner_id):
    learner = get_object_or_404(User, pk=learner_id, role='learner')
    subjects = Subject.objects.filter(
        enrollments__learner=learner
    ).order_by('name')
    data = [{'id': s.id, 'name': s.name} for s in subjects]
    return JsonResponse({'subjects': data})



# --------------------------------------------------
# Reports
# --------------------------------------------------

@login_required
@role_required('admin')
def attendance_report_view(request):
    subjects = Subject.objects.all().order_by('name')
    selected_subject = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    records = Attendance.objects.select_related(
        'learner', 'subject', 'marked_by'
    ).order_by('-date')

    if selected_subject:
        records = records.filter(subject_id=selected_subject)
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)

    total = records.count()
    present = records.filter(status='present').count()
    absent = records.filter(status='absent').count()
    late = records.filter(status='late').count()

    return render(request, 'core/report_attendance.html', {
        'subjects': subjects,
        'records': records[:100],
        'selected_subject': selected_subject,
        'date_from': date_from,
        'date_to': date_to,
        'total': total,
        'present': present,
        'absent': absent,
        'late': late,
    })


@login_required
@role_required('admin')
def mark_report_view(request):
    subjects = Subject.objects.all().order_by('name')
    selected_subject = request.GET.get('subject', '')

    learner_data = []
    learners = User.objects.filter(role='learner').order_by('last_name')

    if selected_subject:
        learners = learners.filter(enrollments__subject_id=selected_subject)

    for learner in learners:
        grades = Grade.objects.filter(learner=learner)
        if selected_subject:
            grades = grades.filter(subject_id=selected_subject)
        avg = grades.aggregate(avg=Avg('score'))['avg']
        if avg is not None:
            avg = round(float(avg), 1)
            level = (
                7 if avg >= 80 else 6 if avg >= 70 else 5 if avg >= 60
                else 4 if avg >= 50 else 3 if avg >= 40 else 2 if avg >= 30
                else 1
            )
            learner_data.append({
                'learner': learner,
                'avg': avg,
                'level': level,
                'grade_count': grades.count(),
            })

    learner_data.sort(key=lambda x: x['avg'], reverse=True)

    overall_avg = round(
        sum(d['avg'] for d in learner_data) / len(learner_data), 1
    ) if learner_data else 0

    return render(request, 'core/report_marks.html', {
        'subjects': subjects,
        'selected_subject': selected_subject,
        'learner_data': learner_data,
        'overall_avg': overall_avg,
    })


@login_required
@role_required('admin')
def mentor_hours_report_view(request):
    mentors = User.objects.filter(role='mentor').order_by('last_name')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    mentor_data = []
    for mentor in mentors:
        sessions = TutoringSession.objects.filter(tutor=mentor)
        if date_from:
            sessions = sessions.filter(date__gte=date_from)
        if date_to:
            sessions = sessions.filter(date__lte=date_to)

        total_mins = sum(s.duration_minutes for s in sessions)
        mentee_count = (
            MentorAssignment.objects.filter(mentor=mentor)
            .values('learner').distinct().count()
        )

        mentor_data.append({
            'mentor': mentor,
            'session_count': sessions.count(),
            'total_hours': round(total_mins / 60, 1),
            'total_mins': total_mins,
            'mentee_count': mentee_count,
        })

    mentor_data.sort(key=lambda x: x['total_mins'], reverse=True)
    total_hours = round(sum(d['total_mins'] for d in mentor_data) / 60, 1)

    return render(request, 'core/report_mentor_hours.html', {
        'mentor_data': mentor_data,
        'date_from': date_from,
        'date_to': date_to,
        'total_hours': total_hours,
    })


@login_required
@role_required('admin', 'assistant')
def learner_report_view(request, learner_id):
    """Generate a formal report card for a learner."""
    learner = get_object_or_404(User, pk=learner_id, role='learner')

    # Get all enrolled subjects
    subjects = Subject.objects.filter(enrollments__learner=learner).order_by('name')

    # Get term filter
    selected_term = request.GET.get('term', '')

    # Build per-subject data
    subject_data = []
    total_score = 0
    total_count = 0

    for subj in subjects:
        grades = Grade.objects.filter(learner=learner, subject=subj)
        if selected_term:
            grades = grades.filter(assessment_name__icontains=selected_term)

        avg = grades.aggregate(avg=Avg('score'))['avg']
        if avg is not None:
            avg = round(float(avg), 1)
        else:
            avg = 0

        level = (
            7 if avg >= 80 else 6 if avg >= 70 else 5 if avg >= 60
            else 4 if avg >= 50 else 3 if avg >= 40 else 2 if avg >= 30
            else 1
        )

        subject_data.append({
            'subject': subj,
            'avg': avg,
            'level': level,
        })

        if avg > 0:
            total_score += avg
            total_count += 1

    overall_avg = round(total_score / total_count, 1) if total_count > 0 else 0
    overall_level = (
        7 if overall_avg >= 80 else 6 if overall_avg >= 70
        else 5 if overall_avg >= 60 else 4 if overall_avg >= 50
        else 3 if overall_avg >= 40 else 2 if overall_avg >= 30
        else 1
    )

    if overall_avg >= 50:
        result = 'Achieved'
    else:
        result = 'Not Achieved'

    # Attendance
    total_att = Attendance.objects.filter(learner=learner).count()
    absent_count = Attendance.objects.filter(
        learner=learner, status='absent'
    ).count()
    present_count = Attendance.objects.filter(
        learner=learner, status='present'
    ).count()

    # Get unique term names from grades
    terms = (
        Grade.objects.filter(learner=learner)
        .values_list('assessment_name', flat=True)
        .distinct()
        .order_by('assessment_name')
    )

    return render(request, 'core/learner_report.html', {
        'learner': learner,
        'subject_data': subject_data,
        'overall_avg': overall_avg,
        'overall_level': overall_level,
        'result': result,
        'total_att': total_att,
        'absent_count': absent_count,
        'present_count': present_count,
        'terms': terms,
        'selected_term': selected_term,
    })