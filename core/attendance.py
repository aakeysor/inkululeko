"""Attendance calculations shared by the register, dashboards and reports.

Attendance is recorded per learner per day. An Attendance row means the
learner was present that day. Absence is worked out rather than stored:

* A session day is a weekday, up to and including today, that is not a
  Closure (school holiday, public holiday or other day with no session).
* A learner's session days start on their start date: the earlier of the day
  their account was created and the first day they were ever marked present.
  This way learners who join mid-year aren't counted absent for days before
  they joined, while attendance entered for earlier days still counts.
* Each session day without an Attendance row counts as an absence.

The register page (templates/core/mark_attendance.html) repeats these rules in
JavaScript so its totals update instantly. Keep the two in step.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Min

from .models import Attendance, Closure

PROGRAMME_TZ = ZoneInfo('Africa/Johannesburg')


def programme_today():
    """Today's date in Makhanda, whatever the server's time zone."""
    return datetime.now(PROGRAMME_TZ).date()


def year_bounds(year):
    return date(year, 1, 1), date(year, 12, 31)


def weekdays_between(start, end):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def session_days(start, end):
    """Weekdays from start to end that are not closures, capped at today."""
    end = min(end, programme_today())
    if start > end:
        return []
    closed = set(
        Closure.objects.filter(date__range=(start, end))
        .values_list('date', flat=True)
    )
    return [d for d in weekdays_between(start, end) if d not in closed]


def joined_date(learner):
    if not learner.date_joined:
        return None
    return learner.date_joined.astimezone(PROGRAMME_TZ).date()


def first_marks(learner_ids):
    """{learner_id: first date ever marked present}."""
    return dict(
        Attendance.objects.filter(learner_id__in=learner_ids)
        .values('learner_id')
        .annotate(first=Min('date'))
        .values_list('learner_id', 'first')
    )


def learner_start(learner, first_mark=None):
    candidates = [d for d in (joined_date(learner), first_mark) if d]
    return min(candidates) if candidates else None


def attendance_stats(learners, start=None, end=None):
    """Attendance figures for each learner over a period.

    Defaults to the current calendar year up to today. Returns
    {learner_id: {'total', 'present', 'absent', 'rate'}}, where rate is a
    percentage rounded to one decimal place (0 when there were no sessions).
    """
    today = programme_today()
    if start is None:
        start = date(today.year, 1, 1)
    if end is None:
        end = date(today.year, 12, 31)

    learners = list(learners)
    ids = [l.id for l in learners]
    days = session_days(start, end)

    present_days = defaultdict(set)
    for learner_id, day in (
        Attendance.objects.filter(learner_id__in=ids, date__range=(start, end))
        .values_list('learner_id', 'date')
    ):
        present_days[learner_id].add(day)

    firsts = first_marks(ids)
    stats = {}
    for learner in learners:
        begin = learner_start(learner, firsts.get(learner.id))
        counted = [d for d in days if begin is None or d >= begin]
        present = sum(1 for d in counted if d in present_days[learner.id])
        total = len(counted)
        stats[learner.id] = {
            'total': total,
            'present': present,
            'absent': total - present,
            'rate': round(present / total * 100, 1) if total else 0,
        }
    return stats


def learner_attendance(learner, start=None, end=None):
    return attendance_stats([learner], start, end)[learner.id]


def recent_days(learner, count=10):
    """The learner's most recent session days, newest first.

    Returns a list of {'date': date, 'status': 'present' or 'absent'}.
    """
    today = programme_today()
    begin = learner_start(learner, first_marks([learner.id]).get(learner.id))
    window_start = today - timedelta(days=180)
    if begin and begin > window_start:
        window_start = begin
    days = session_days(window_start, today)[-count:]
    present = set(
        Attendance.objects.filter(learner=learner, date__in=days)
        .values_list('date', flat=True)
    )
    return [
        {'date': d, 'status': 'present' if d in present else 'absent'}
        for d in reversed(days)
    ]


def present_learner_ids(day, learner_ids=None):
    qs = Attendance.objects.filter(date=day)
    if learner_ids is not None:
        qs = qs.filter(learner_id__in=learner_ids)
    return set(qs.values_list('learner_id', flat=True))


def is_session_day(day):
    return (
        day.weekday() < 5
        and day <= programme_today()
        and not Closure.objects.filter(date=day).exists()
    )
