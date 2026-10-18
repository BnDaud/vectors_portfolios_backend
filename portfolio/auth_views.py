from django.conf import settings
from django.contrib.auth import authenticate
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

ACCESS_COOKIE = "access_token"
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


class LoginView(APIView):
    name = "auth_login"
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)

        if user is None:
            return Response({"detail": "Invalid credentials"}, status=401)

        refresh = RefreshToken.for_user(user)

        response = Response({"username": user.username})
        response.set_cookie(ACCESS_COOKIE, str(refresh.access_token), **_cookie_kwargs())
        response.set_cookie(REFRESH_COOKIE, str(refresh), **_cookie_kwargs())
        return response


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
            return Response({"authenticated": True, "username": request.user.username})
        return Response({"authenticated": False})
