from django.conf import settings
from django.http import Http404, HttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import resume_builder
from .models import PortfolioTrack

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _track_or_404(slug):
    track = (
        PortfolioTrack.objects.select_related("profile__user")
        .prefetch_related("items")
        .filter(slug=slug)
        .first()
    )
    if track is None:
        raise Http404("No such portfolio")
    return track


class ResumeDownloadView(APIView):
    """Owner only: the editable PDF / Word resume of one portfolio."""
    name = "resume_download"
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, kind):
        if kind not in CONTENT_TYPES:
            raise Http404("Unknown resume format")
        track = _track_or_404(slug)
        data = resume_builder.collect(track, settings.SITE_URL)
        response = HttpResponse(resume_builder.cached(kind, track, data), content_type=CONTENT_TYPES[kind])
        # the name comes from the owner's name and the portfolio's name, reduced to safe characters
        response["Content-Disposition"] = f'attachment; filename="{resume_builder.file_stem(data)}.{kind}"'
        response["Cache-Control"] = "no-store"
        return response


class ResumePagesView(APIView):
    """Public: how many page images the read-only viewer should show."""
    name = "resume_pages"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resume_view"

    def get(self, request, slug):
        track = _track_or_404(slug)
        data = resume_builder.collect(track, settings.SITE_URL)
        pages = resume_builder.cached("pages", track, data)
        response = Response({"name": data["name"], "portfolio": data["portfolio"], "pages": len(pages), "version": resume_builder.digest(data)})
        response["Cache-Control"] = "no-store"
        return response


class ResumePageImageView(APIView):
    """Public: one page of the read-only resume, as an image (no text to copy)."""
    name = "resume_page_image"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resume_view"

    def get(self, request, slug, page):
        track = _track_or_404(slug)
        pages = resume_builder.cached("pages", track, resume_builder.collect(track, settings.SITE_URL))
        if not 1 <= page <= len(pages):
            raise Http404("No such page")
        response = HttpResponse(pages[page - 1], content_type="image/png")
        response["Cache-Control"] = "no-store"
        response["Content-Disposition"] = 'inline; filename="resume-preview.png"'
        response["X-Content-Type-Options"] = "nosniff"
        return response
