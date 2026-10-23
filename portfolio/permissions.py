"""
Who may change what, now that the site has more than one account.

Everyone may read (portfolios are public pages). Changing anything needs a
signed-in user who owns it: every object leads back to one Profile, and only
that profile's user may change it. Nothing here trusts ids sent by the client
for ownership - the owner is always worked out from the database.
"""
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import About, Goal, Portfolio, PortfolioTrack, Proficiency, Profile, Resume, School


def is_site_owner(user):
    """The account whose portfolios live at the site's root (/full-stack and so on)."""
    return bool(user and user.is_authenticated and user.username == settings.SITE_OWNER_USERNAME)


def owner_of(obj):
    """The User an object belongs to, or None when it cannot be told (treated as nobody's)."""
    if isinstance(obj, Profile):
        return obj.user
    if isinstance(obj, PortfolioTrack):
        return obj.profile.user
    if isinstance(obj, About):
        return obj.track.profile.user
    if isinstance(obj, (Resume, School, Proficiency)):
        return obj.about.track.profile.user
    if isinstance(obj, Goal):
        return obj.profile.user
    if isinstance(obj, Portfolio):
        first = obj.tracks.first()
        return first.profile.user if first else None
    if getattr(obj, "_meta", None) and obj._meta.model_name == "user":
        return obj
    return None


def require_owner(request, user):
    """Stop the request unless `user` (the owner of what is being touched) is the one signed in."""
    if user is None or user.pk != request.user.pk:
        raise PermissionDenied("You can only change your own portfolio.")


class IsOwnerOrReadOnly(BasePermission):
    """Reads for everyone; writes only by the signed-in owner of the object."""
    message = "You can only change your own portfolio."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = owner_of(obj)
        return owner is not None and owner.pk == request.user.pk


class SiteOwnerOnlyWrites(BasePermission):
    """Old admin-style endpoints (creating users or profiles by hand): reads stay public, writes are the site owner's."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_site_owner(request.user)
