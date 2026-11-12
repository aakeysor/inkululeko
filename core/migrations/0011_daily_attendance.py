# Switches attendance from per-subject (present/absent/late) to per-day.
#
# Existing records are converted: any day a learner was marked present or late
# in at least one subject becomes a single "present" record for that day.
# Absent records are dropped, because absence is now worked out from the
# calendar (a session day with no record counts as absent).
#
# Also creates the Closure table and pre-fills the 2026 school holidays,
# weekday public holidays, and January and December as programme closures.

from datetime import date, timedelta

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def convert_to_daily(apps, schema_editor):
    Attendance = apps.get_model('core', 'Attendance')
    Attendance.objects.exclude(status__in=['present', 'late']).delete()

    seen = set()
    duplicates = []
    rows = (
        Attendance.objects.order_by('learner_id', 'date', 'pk')
        .values_list('pk', 'learner_id', 'date')
    )
    for pk, learner_id, day in rows:
        key = (learner_id, day)
        if key in seen:
            duplicates.append(pk)
        else:
            seen.add(key)
    for i in range(0, len(duplicates), 500):
        Attendance.objects.filter(pk__in=duplicates[i:i + 500]).delete()


# Department of Basic Education 2026 public school calendar
SCHOOL_HOLIDAYS_2026 = [
    (date(2026, 3, 28), date(2026, 4, 7), 'School holidays after term 1'),
    (date(2026, 6, 15), date(2026, 6, 15), 'Special school holiday'),
    (date(2026, 6, 27), date(2026, 7, 20), 'School holidays after term 2'),
    (date(2026, 9, 24), date(2026, 10, 5), 'School holidays after term 3'),
]

PUBLIC_HOLIDAYS_2026 = {
    date(2026, 4, 3): 'Good Friday',
    date(2026, 4, 6): 'Family Day',
    date(2026, 4, 27): 'Freedom Day',
    date(2026, 5, 1): 'Workers\u2019 Day',
    date(2026, 6, 16): 'Youth Day',
    date(2026, 8, 10): 'National Women\u2019s Day (observed)',
    date(2026, 9, 24): 'Heritage Day',
    date(2026, 12, 16): 'Day of Reconciliation',
    date(2026, 12, 25): 'Christmas Day',
}


def seed_2026_closures(apps, schema_editor):
    Closure = apps.get_model('core', 'Closure')
    day = date(2026, 1, 1)
    while day.year == 2026:
        if day.weekday() < 5:
            reason = None
            if day.month in (1, 12):
                reason = 'Programme closed'
            for start, end, label in SCHOOL_HOLIDAYS_2026:
                if start <= day <= end:
                    reason = label
            if reason is None and day in PUBLIC_HOLIDAYS_2026:
                reason = 'Public holiday: ' + PUBLIC_HOLIDAYS_2026[day]
            if reason:
                Closure.objects.get_or_create(date=day, defaults={'reason': reason})
        day += timedelta(days=1)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0010_alter_subject_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Closure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('reason', models.CharField(default='No session', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='closures_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['date'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together=set(),
        ),
        migrations.RunPython(convert_to_daily, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='attendance',
            name='subject',
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='status',
        ),
        migrations.AlterField(
            model_name='attendance',
            name='marked_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_marked', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='attendance',
            name='marked_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('learner', 'date'), name='unique_attendance_per_learner_per_day'),
        ),
        migrations.RunPython(seed_2026_closures, migrations.RunPython.noop),
    ]
