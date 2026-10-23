import re
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Profile

ACCESS_COOKIE = "access_token"
# what a new account's page shows until its owner adds a photo
DEFAULT_DISPLAY_PIC = "https://jeuuxtzqlrzaqslthhxx.supabase.co/storage/v1/object/public/branding/logo-icon-light.png"
# usernames become web addresses (/u/<username>), so: letters, digits, - and _ only
USERNAME_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,29}$")
RESERVED_USERNAMES = {"u", "admin", "api", "login", "logout", "signup", "resume", "addprofile", "static", "media", "root"}
REFRESH_COOKIE = "refresh_token"


def _cookie_kwargs():
    return {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/",
    }


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfPrimeView(APIView):
    """
    Plants the csrftoken cookie and returns its value in the body, since
    the frontend runs on a different domain and can't read the cookie
    itself via document.cookie.
    """
    name = "auth_csrf"
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


def _signed_in(response, user):
    refresh = RefreshToken.for_user(user)
    response.set_cookie(ACCESS_COOKIE, str(refresh.access_token), **_cookie_kwargs())
    response.set_cookie(REFRESH_COOKIE, str(refresh), **_cookie_kwargs())
    return response


class SignupView(APIView):
    """
    Creates a new account and signs it in. A new account gets its own page at
    /u/<username>/ and may have one portfolio (the site owner has no limit).
    Body: username, password, first_name, last_name.
    """
    name = "auth_signup"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"

    def post(self, request):
        data = request.data
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "")
        first_name = str(data.get("first_name") or "").strip()[:150]
        last_name = str(data.get("last_name") or "").strip()[:150]
        errors = {}

        if not USERNAME_RULE.match(username):
            errors["username"] = ["3-30 characters: letters, numbers, - and _ (it becomes your web address)."]
        elif username.lower() in RESERVED_USERNAMES or User.objects.filter(username__iexact=username).exists():
            errors["username"] = ["That username is taken."]
        if not first_name:
            errors["first_name"] = ["This field is required."]
        if not password:
            errors["password"] = ["This field is required."]
        else:
            try:
                validate_password(password, User(username=username, first_name=first_name, last_name=last_name))
            except DjangoValidationError as exc:
                errors["password"] = list(exc.messages)
        if errors:
            return Response(errors, status=400)

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password, first_name=first_name, last_name=last_name)
            Profile.objects.create(user=user, display_pic=DEFAULT_DISPLAY_PIC, max_portfolios=1)
        return _signed_in(Response({"username": user.username}, status=201), user)


def _free_username(given, family):
    """A web-address-friendly username from the person's name (never their email), made unique."""
    base = (slugify(f"{given} {family}") or "user")[:20].strip("-") or "user"
    while True:
        candidate = f"{base}-{secrets.token_hex(2)}"
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate


def _google_claims(request):
    """(claims, None) for a genuine Google ID token in request.data["credential"], else (None, error response)."""
    if not settings.GOOGLE_CLIENT_ID:
        return None, Response({"detail": "Google sign-in is not set up."}, status=503)
    credential = request.data.get("credential")
    if not isinstance(credential, str) or not credential:
        return None, Response({"credential": ["This field is required."]}, status=400)
    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except ValueError:
        return None, Response({"detail": "Google sign-in failed. Please try again."}, status=401)
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com") or not claims.get("sub"):
        return None, Response({"detail": "Google sign-in failed. Please try again."}, status=401)
    if not claims.get("email_verified"):
        return None, Response({"detail": "Your Google email address is not verified."}, status=403)
    return claims, None


class GoogleLinkView(APIView):
    """
    The signed-in account's Google connection.
      POST {credential}: connect this Google account, so it can sign in with Google too.
      DELETE: disconnect it - only while the account has a password, so it can never be locked out.
    """
    name = "auth_google_link"
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"

    def post(self, request):
        claims, problem = _google_claims(request)
        if problem:
            return problem
        profile = Profile.objects.filter(user=request.user).first()
        if profile is None:
            return Response({"detail": "This account has no profile."}, status=400)
        taken = Profile.objects.filter(google_sub=claims["sub"]).exclude(pk=profile.pk).exists()
        if taken:
            return Response({"detail": "That Google account is already connected to another account."}, status=409)
        profile.google_sub = claims["sub"]
        profile.save(update_fields=["google_sub"])
        return Response({"google": True})

    def delete(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        if profile is None or not profile.google_sub:
            return Response({"google": False})
        if not request.user.has_usable_password():
            return Response({"detail": "Set a password first, or you would have no way to sign in."}, status=400)
        profile.google_sub = None
        profile.save(update_fields=["google_sub"])
        return Response({"google": False})


class SetPasswordView(APIView):
    """A first password for an account made with Google (one that has none). Changing an existing
    password stays with auth/change-password, which asks for the current one."""
    name = "auth_set_password"
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    def post(self, request):
        user = request.user
        if user.has_usable_password():
            return Response({"detail": "This account already has a password - change it instead."}, status=400)
        new = str(request.data.get("new_password") or "")
        if not new:
            return Response({"new_password": ["This field is required."]}, status=400)
        try:
            validate_password(new, user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=400)
        user.set_password(new)
        user.save(update_fields=["password"])
        return _signed_in(Response({"password": True}), user)    # the old tokens stop working once a password exists


class GoogleLoginView(APIView):
    """
    "Continue with Google": the browser gets a signed ID token from Google and sends it
    here as `credential`. Google's signature, the audience (our client id), the expiry and
    a verified email are all checked. A Google account seen for the first time becomes a
    new account (one portfolio, like any sign-up); after that it simply signs in.
    """
    name = "auth_google"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signup"

    def post(self, request):
        claims, problem = _google_claims(request)
        if problem:
            return problem

        profile = Profile.objects.select_related("user").filter(google_sub=claims["sub"]).first()
        created = profile is None
        if created:
            given, family = str(claims.get("given_name") or claims.get("name") or "")[:150], str(claims.get("family_name") or "")[:150]
            with transaction.atomic():
                user = User(username=_free_username(given, family), first_name=given, last_name=family, email=str(claims.get("email") or ""))
                user.set_unusable_password()      # signs in through Google only
                user.save()
                picture = str(claims.get("picture") or "")
                profile = Profile.objects.create(user=user, display_pic=picture if picture.startswith("https://") else DEFAULT_DISPLAY_PIC,
                                                 max_portfolios=1, google_sub=claims["sub"])
        user = profile.user
        if not user.is_active:
            return Response({"detail": "This account is switched off."}, status=403)
        return _signed_in(Response({"username": user.username, "created": created}, status=201 if created else 200), user)


class LoginView(APIView):
    name = "auth_login"
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response({"detail": "Invalid credentials"}, status=401)
        return _signed_in(Response({"username": user.username}), user)


class LogoutView(APIView):
    name = "auth_logout"
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"detail": "logged out"})
        response.delete_cookie(ACCESS_COOKIE, path="/")
        response.delete_cookie(REFRESH_COOKIE, path="/")
        return response


class RefreshView(APIView):
    name = "auth_refresh"
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not raw_refresh:
            return Response({"detail": "No refresh token"}, status=401)

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError:
            return Response({"detail": "Invalid refresh token"}, status=401)

        response = Response({"detail": "refreshed"})
        response.set_cookie(ACCESS_COOKIE, str(refresh.access_token), **_cookie_kwargs())
        return response


class ChangePasswordView(APIView):
    """
    Changes the signed-in user's password. The current password is required
    (a stolen session alone can't lock the owner out), the new one goes
    through Django's password validators, and the response re-issues this
    session's cookies since every older token stops working.
    """
    name = "auth_change_password"
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    def post(self, request):
        current = request.data.get("current_password") or ""
        new = request.data.get("new_password") or ""
        user = request.user
        errors = {}

        if not user.check_password(current):
            errors["current_password"] = ["Current password is incorrect."]

        if not new:
            errors["new_password"] = ["This field is required."]
        elif new == current:
            errors["new_password"] = ["The new password must be different from the current one."]
        else:
            try:
                validate_password(new, user)
            except DjangoValidationError as exc:
                errors["new_password"] = list(exc.messages)

        if errors:
            return Response(errors, status=400)

        user.set_password(new)
        user.save(update_fields=["password"])

        refresh = RefreshToken.for_user(user)
        response = Response({"detail": "Password changed"})
        response.set_cookie(ACCESS_COOKIE, str(refresh.access_token), **_cookie_kwargs())
        response.set_cookie(REFRESH_COOKIE, str(refresh), **_cookie_kwargs())
        return response


class MeView(APIView):
    name = "auth_me"
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user and request.user.is_authenticated:
            profile = Profile.objects.filter(user=request.user).first()
            return Response({
                "authenticated": True,
                "username": request.user.username,
                # which ways this account can sign in
                "has_password": request.user.has_usable_password(),
                "google": bool(profile and profile.google_sub),
            })
        return Response({"authenticated": False})
