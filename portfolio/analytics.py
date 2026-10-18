import re
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import PageView, Visitor

# Coming back after this long without activity counts as a new visit.
SESSION_GAP = timedelta(minutes=30)

# Crawlers, link-preview fetchers and automated browsers aren't people.
BOT_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|preview|facebookexternalhit|embedly|lighthouse|headless|phantomjs|"
    r"python-requests|curl/|wget/|httpclient|monitor|uptime",
    re.IGNORECASE,
)


def is_bot(request):
    agent = request.META.get("HTTP_USER_AGENT", "")
    return not agent or bool(BOT_PATTERN.search(agent))


def is_owner(request):
    """True when the request carries a valid signed-in session (the site owner)."""
    raw = request.COOKIES.get("access_token")
    if not raw:
        return False
    auth = JWTAuthentication()
    try:
        auth.get_user(auth.get_validated_token(raw))
        return True
    except (InvalidToken, TokenError, exceptions.AuthenticationFailed):
        return False


def record_visit(visitor_uuid, track):
    """
    Register that this browser opened `track` (None = landing page).
    New browser -> new Visitor. Known browser -> the same Visitor, with
    visit_count +1 only when this is a fresh visit rather than the same session.
    """
    now = timezone.now()
    with transaction.atomic():
        visitor, created = Visitor.objects.select_for_update().get_or_create(
            visitor_id=visitor_uuid, defaults={"last_seen": now}
        )
        if not created:
            if now - visitor.last_seen >= SESSION_GAP:
                visitor.visit_count += 1
            visitor.last_seen = now
            visitor.save(update_fields=["visit_count", "last_seen"])
        try:
            with transaction.atomic():
                PageView.objects.get_or_create(visitor=visitor, visit_number=visitor.visit_count, track=track)
        except IntegrityError:
            pass  # two tabs reported the same page at once - already recorded
    return visitor
