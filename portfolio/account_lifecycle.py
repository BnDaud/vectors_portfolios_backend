"""
Accounts that nobody visits are deleted after a year.

"Visited" means a visitor (never the account's own owner, never a bot) opened one of
its portfolios or its read-only resume. The year counts from the latest such visit, or
from sign-up when there has been none. The site owner's and admin accounts are never
deleted this way. Deletion leaves a DeletedAccount note (username, date, reason only).

There is no scheduler on the host, so the sweep runs at most once a day, started by
ordinary traffic (sweep_daily), or by hand: `python manage.py delete_inactive_accounts`.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import DeletedAccount, PageView, Profile, ResumeView
from .permissions import is_site_owner

INACTIVE_AFTER = timedelta(days=365)
SWEEP_KEY = "account-sweep"
SWEEP_EVERY_SECONDS = 24 * 3600


def is_protected(user):
    return is_site_owner(user) or user.is_staff or user.is_superuser


def last_visited(user):
    """The latest visitor view of any of the account's portfolios or resumes, or None."""
    page = PageView.objects.filter(track__profile__user=user).aggregate(at=Max("created_at"))["at"]
    resume = ResumeView.objects.filter(track__profile__user=user).aggregate(at=Max("created_at"))["at"]
    return max((d for d in (page, resume) if d), default=None)


def deletes_on(user):
    """When this account would be deleted if nobody visits before then; None for protected accounts."""
    if is_protected(user):
        return None
    return (last_visited(user) or user.date_joined) + INACTIVE_AFTER


def remove_account(user, reason):
    """Delete the account (profile, portfolios, their projects) and leave the note behind."""
    profile = Profile.objects.filter(user=user).first()
    with transaction.atomic():
        DeletedAccount.objects.update_or_create(
            username=user.username.lower(),
            defaults={"reason": reason, "deleted_at": timezone.now(), "google_sub": profile.google_sub if profile else None},
        )
        user.delete()


def sweep(now=None):
    """Delete every unprotected account with no visit (or, without visits, no sign-up) within the year. Returns how many."""
    now = now or timezone.now()
    cutoff = now - INACTIVE_AFTER
    removed = 0
    candidates = User.objects.filter(is_staff=False, is_superuser=False, date_joined__lt=cutoff).annotate(
        last_page=Max("profile__tracks__views__created_at"), last_resume=Max("profile__tracks__resume_views__created_at"))
    for user in candidates:
        if is_protected(user):
            continue
        latest = max((d for d in (user.last_page, user.last_resume) if d), default=None)
        if latest is None or latest < cutoff:
            remove_account(user, DeletedAccount.Reason.INACTIVE)
            removed += 1
    return removed


def sweep_daily():
    """Run the sweep if it has not run in the last day (cheap to call on every request)."""
    if cache.add(SWEEP_KEY, True, SWEEP_EVERY_SECONDS):
        try:
            sweep()
        except Exception:      # never let housekeeping break a page view
            cache.delete(SWEEP_KEY)


def deletion_note(username=None, google_sub=None):
    note = None
    if username:
        note = DeletedAccount.objects.filter(username=username.lower()).first()
    if note is None and google_sub:
        note = DeletedAccount.objects.filter(google_sub=google_sub).order_by("-deleted_at").first()
    return note


def describe(note):
    when = note.deleted_at.strftime("%-d %B %Y")
    why = ("because no one visited its portfolio for a year" if note.reason == DeletedAccount.Reason.INACTIVE
           else "by the site owner")
    return f"This account was deleted on {when} {why}. You can sign up again to start a new one."
