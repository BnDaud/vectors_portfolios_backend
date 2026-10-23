"""The site owner's view of the accounts people have made: how many, and enough to tell them
apart (username, when, how they sign in, how many portfolios) - never their contact details,
names or emails. The owner can delete an account; their own can never be deleted here."""
from django.contrib.auth.models import User
from django.db.models import Count
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import is_site_owner


class SiteOwnerOnly(BasePermission):
    def has_permission(self, request, view):
        return is_site_owner(request.user)


class AccountListView(APIView):
    name = "accounts"
    permission_classes = [SiteOwnerOnly]

    def get(self, request):
        users = (User.objects.select_related("profile").annotate(portfolios=Count("profile__tracks", distinct=True))
                 .order_by("-date_joined"))
        rows = []
        for user in users:
            profile = getattr(user, "profile", None)
            rows.append({
                "id": user.pk,
                "username": user.username,
                "joined": user.date_joined,
                "last_login": user.last_login,
                "portfolios": user.portfolios,
                "password": user.has_usable_password(),
                "google": bool(profile and profile.google_sub),
                "is_you": user.pk == request.user.pk,
                # the owner's own and the Django admin accounts cannot be deleted from here
                "protected": user.pk == request.user.pk or user.is_staff or user.is_superuser or is_site_owner(user),
            })
        return Response({"count": len(rows), "accounts": rows})


class AccountDeleteView(APIView):
    name = "account_delete"
    permission_classes = [SiteOwnerOnly]

    def delete(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response(status=404)
        if user.pk == request.user.pk or is_site_owner(user) or user.is_staff or user.is_superuser:
            raise PermissionDenied("The site owner's and admin accounts cannot be deleted here.")
        user.delete()          # takes the profile, its portfolios and their projects with it (shared ones only from this account)
        return Response(status=204)
