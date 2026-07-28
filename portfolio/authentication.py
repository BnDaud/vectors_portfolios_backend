from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication


def _enforce_csrf(request):
    """
    DRF's APIView disables Django's CsrfViewMiddleware for every view and
    only re-enables it for SessionAuthentication (see enforce_csrf there).
    Since auth here also rides on an ambient cookie (not a header the
    browser wouldn't send automatically), it needs the same protection -
    this mirrors SessionAuthentication.enforce_csrf() exactly.
    """
    def dummy_get_response(request):
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied("CSRF Failed: %s" % reason)


class CookieJWTAuthentication(JWTAuthentication):
    """
    Reads the access token from the httpOnly 'access_token' cookie instead
    of the Authorization header, since the frontend runs on a different
    domain and can't attach headers a browser wouldn't otherwise send.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        _enforce_csrf(request)
        return self.get_user(validated_token), validated_token
