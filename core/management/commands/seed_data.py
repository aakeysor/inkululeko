from datetime import date, timedelta
import random
from django.core.management.base import BaseCommand
from core.models import (
    User, School, Subject, Enrollment,
    MentorAssignment, Attendance, Grade,
    ActivityLog, TutoringSession,
)


class Command(BaseCommand):
    help = 'Seed the database with schools, subjects, test users, and sample data'

    def handle(self, *args, **options):
        # --- Schools ---
        school_data = [
            ('Ntsika Secondary School', 'Makhanda, South Africa'),
            ('Andrew Moyakhe', 'Makhanda, South Africa'),
            ('Nathaniel Nyaluza High School', 'Makhanda, South Africa'),
        ]
        schools = []
        for name, loc in school_data:
            s, created = School.objects.get_or_create(
                name=name, defaults={'location': loc},
            )
            schools.append(s)
            self.stdout.write(f"  {'Created' if created else 'Exists'}: {name}")

        # --- Subjects (programme-wide) ---
        subject_names = [
            'Mathematics', 'Physical Science', 'Life Sciences',
            'English', 'Afrikaans', 'isiXhosa',
            'Geography', 'History', 'Accounting',
        ]
        for sname in subject_names:
            Subject.objects.get_or_create(name=sname)
        self.stdout.write(self.style.SUCCESS(
            f'  Subjects seeded: {len(subject_names)}'
        ))

        # --- Helper ---
        def make_user(uname, first, last, role, school=None, **extra):
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    'first_name': first, 'last_name': last,
                    'role': role, 'school': school, **extra,
                },
            )
            if created:
                u.set_password('inkululeko2026')
                u.save()
            return u

        # --- Admin ---
        make_user('admin1', 'Programme', 'Admin', 'admin')

        # --- Assistants ---
        assistant1 = make_user(
            'assistant1', 'Thandi', 'Nkosi', 'assistant', schools[0],
            email='thandi.nkosi@inkululeko.org',
            phone='082-345-6789',
            date_of_birth=date(1985, 4, 15),
            address='123 Main Street, Makhanda',
            emergency_contact_name='John Nkosi',
            emergency_contact_phone='083-456-7890',
            subject_taught='Mathematics',
            grade_levels_taught='8th-9th Grade',
            experience_years=8,
            qualifications='Bachelor of Education (Rhodes University)',
            certifications='SACE Registered, First Aid Certified',
            specializations='Differentiated Instruction',
        )
        assistant2 = make_user(
            'assistant2', 'James', 'Smith', 'assistant', schools[2],
            email='james.smith@inkululeko.org',
            phone='082-567-8901',
            subject_taught='Physical Science',
            grade_levels_taught='10th-12th Grade',
            experience_years=5,
            qualifications='BSc Chemistry (Nelson Mandela University)',
        )

        # --- Learners ---
        learner1 = make_user(
            'learner1', 'Sipho', 'Dlamini', 'learner', schools[0],
            email='sipho.d@example.com',
            phone='082-111-2222',
            date_of_birth=date(2010, 5, 15),
            grade_level='8th',
            address='45 Township Road, Makhanda',
            parent_guardian_name='Nomsa Dlamini',
            parent_guardian_phone='082-333-4444',
            emergency_contact_name='Bongani Dlamini',
            emergency_contact_phone='082-555-6666',
        )
        learner2 = make_user(
            'learner2', 'Amahle', 'Zulu', 'learner', schools[0],
            email='amahle.z@example.com',
            phone='082-222-3333',
            date_of_birth=date(2009, 8, 22),
            grade_level='9th',
            address='12 Hope Street, Makhanda',
            parent_guardian_name='Zanele Zulu',
            parent_guardian_phone='082-444-5555',
            emergency_contact_name='Thabo Zulu',
            emergency_contact_phone='082-666-7777',
        )
        learner3 = make_user(
            'learner3', 'Liam', 'van der Merwe', 'learner', schools[2],
            email='liam.vdm@example.com',
            date_of_birth=date(2010, 3, 10),
            grade_level='8th',
            address='78 Church Street, Makhanda',
            parent_guardian_name='Pieter van der Merwe',
            parent_guardian_phone='082-777-8888',
            emergency_contact_name='Anna van der Merwe',
            emergency_contact_phone='082-888-9999',
        )

        # --- Mentors ---
        mentor1 = make_user(
            'mentor1', 'Sarah', 'Mitchell', 'mentor',
            email='sarah.mitchell@email.com',
            phone='555-123-4567',
            date_of_birth=date(1998, 8, 22),
            address='456 University Ave, Makhanda',
            emergency_contact_name='Jane Smith',
            emergency_contact_phone='555-234-5678',
            organization='Rhodes University',
            focus_areas='Mathematics, Physics',
            background='Senior, Mathematics & Physics Major',
            availability='Monday-Wednesday, 3:00-6:00 PM',
        )

        self.stdout.write(self.style.SUCCESS('  Test users seeded'))

        # --- Enrollments ---
        all_subjects = Subject.objects.all().order_by('name')
        for subj in all_subjects[:5]:
            Enrollment.objects.get_or_create(learner=learner1, subject=subj)
            Enrollment.objects.get_or_create(learner=learner2, subject=subj)
        for subj in all_subjects[5:9]:
            Enrollment.objects.get_or_create(learner=learner3, subject=subj)
        self.stdout.write(self.style.SUCCESS('  Enrolments seeded'))

        # --- Mentor Assignments ---
        MentorAssignment.objects.get_or_create(
            mentor=mentor1, learner=learner1,
            defaults={'is_general': True},
        )
        MentorAssignment.objects.get_or_create(
            mentor=mentor1, learner=learner2,
            defaults={'is_general': True},
        )

        # --- Sample Grades ---
        today = date.today()
        learners_to_grade = [
            (learner1, list(all_subjects[:5])),
            (learner2, list(all_subjects[:5])),
            (learner3, list(all_subjects[5:9])),
        ]

        for learner, subjects in learners_to_grade:
            for subj in subjects:
                for months_ago in range(6, 0, -1):
                    grade_date = today - timedelta(days=months_ago * 30)
                    base_score = 55 + (6 - months_ago) * 4
                    score = min(100, max(30, base_score + random.randint(-10, 10)))
                    Grade.objects.get_or_create(
                        learner=learner,
                        subject=subj,
                        assessment_name=f'Term {7 - months_ago} Test',
                        date=grade_date,
                        defaults={
                            'score': score,
                            'max_score': 100,
                            'recorded_by': assistant1,
                        },
                    )
        self.stdout.write(self.style.SUCCESS('  Sample grades seeded'))

        # --- Sample Attendance ---
        for learner, subjects in learners_to_grade:
            for subj in subjects[:2]:
                for days_ago in range(30, 0, -1):
                    att_date = today - timedelta(days=days_ago)
                    if att_date.weekday() >= 5:
                        continue
                    status = random.choices(
                        ['present', 'absent', 'late'],
                        weights=[85, 10, 5],
                    )[0]
                    Attendance.objects.get_or_create(
                        learner=learner, subject=subj, date=att_date,
                        defaults={'status': status, 'marked_by': assistant1},
                    )
        self.stdout.write(self.style.SUCCESS('  Sample attendance seeded'))

        # --- Sample Tutoring Sessions ---
        math_subj = Subject.objects.filter(name='Mathematics').first()
        science_subj = Subject.objects.filter(name='Physical Science').first()

        if math_subj and science_subj:
            sessions_data = [
                (learner1, mentor1, math_subj, 5, 60, 'Worked on algebra problems'),
                (learner1, mentor1, science_subj, 8, 45, 'Chemistry concepts review'),
                (learner1, mentor1, math_subj, 12, 60, 'Geometry practice'),
                (learner1, mentor1, science_subj, 15, 60, 'Biology cell structures'),
                (learner1, mentor1, math_subj, 19, 60, 'Trigonometry basics'),
                (learner2, mentor1, math_subj, 6, 60, 'Fractions and decimals'),
                (learner2, mentor1, math_subj, 13, 45, 'Word problems'),
                (learner2, mentor1, science_subj, 16, 60, 'Lab report writing'),
            ]
            for learner, tutor, subj, days_ago, duration, notes in sessions_data:
                TutoringSession.objects.get_or_create(
                    learner=learner, tutor=tutor, subject=subj,
                    date=today - timedelta(days=days_ago),
                    defaults={'duration_minutes': duration, 'notes': notes},
                )
        self.stdout.write(self.style.SUCCESS('  Tutoring sessions seeded'))

        # --- Activity Log ---
        activity_data = [
            (assistant1, 'attendance', 'Thandi Nkosi marked attendance for Grade 8 Mathematics Support'),
            (assistant1, 'grade', 'Thandi Nkosi updated marks for Science Support'),
            (learner1, 'login', 'Sipho Dlamini clocked in'),
            (assistant1, 'user_created', 'New student enrolled: Thabo Dlamini'),
        ]
        for user, atype, desc in activity_data:
            ActivityLog.objects.get_or_create(
                user=user, action_type=atype,
                defaults={'description': desc},
            )
        self.stdout.write(self.style.SUCCESS('  Activity log seeded'))

        self.stdout.write(self.style.SUCCESS(
            '\nDone! All test credentials use password: inkululeko2026'
        ))
        self.stdout.write(self.style.SUCCESS(
            'Usernames: admin1, assistant1, assistant2, '
            'learner1, learner2, learner3, mentor1'
        ))