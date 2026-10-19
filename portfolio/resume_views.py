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


def _template(request, default):
    """The ?template= choice, or a 400 for a design that does not exist."""
    key = request.query_params.get("template", default)
    if key not in resume_builder.TEMPLATES:
        return None, Response({"template": [f"Unknown design. Choose one of: {', '.join(resume_builder.TEMPLATES)}."]}, status=400)
    return key, None


class ResumeTemplatesView(APIView):
    """Public: the resume designs on offer (the site builds its picker from this)."""
    name = "resume_templates"
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response([
            {"key": key, "default": key == resume_builder.DEFAULT_TEMPLATE, **info}
            for key, info in resume_builder.TEMPLATES.items()
        ])


class ResumeDownloadView(APIView):
    """Owner only: the editable PDF / Word resume of one portfolio, in the chosen design."""
    name = "resume_download"
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, kind):
        if kind not in CONTENT_TYPES:
            raise Http404("Unknown resume format")
        template, error = _template(request, resume_builder.DEFAULT_TEMPLATE)
        if error:
            return error
        if kind not in resume_builder.TEMPLATES[template]["formats"]:
            return Response({"template": [f"The {resume_builder.TEMPLATES[template]['label']} design is only available as: {', '.join(resume_builder.TEMPLATES[template]['formats'])}."]}, status=400)
        track = _track_or_404(slug)
        data = resume_builder.collect(track, settings.SITE_URL)
        response = HttpResponse(resume_builder.cached(kind, track, data, template), content_type=CONTENT_TYPES[kind])
        # the name comes from the owner's name and the portfolio's name, reduced to safe characters
        response["Content-Disposition"] = f'attachment; filename="{resume_builder.file_stem(data, template)}.{kind}"'
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
        template, error = _template(request, resume_builder.VIEWER_TEMPLATE)
        if error:
            return error
        track = _track_or_404(slug)
        data = resume_builder.collect(track, settings.SITE_URL)
        pages = resume_builder.cached("pages", track, data, template)
        response = Response({"name": data["name"], "portfolio": data["portfolio"], "pages": len(pages), "version": resume_builder.digest(data), "template": template})
        response["Cache-Control"] = "no-store"
        return response


class ResumePageImageView(APIView):
    """Public: one page of the read-only resume as an image (no text to copy);
    ?thumb=1 gives a small picture of the first page, for the design picker."""
    name = "resume_page_image"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resume_view"

    def get(self, request, slug, page):
        template, error = _template(request, resume_builder.VIEWER_TEMPLATE)
        if error:
            return error
        track = _track_or_404(slug)
        data = resume_builder.collect(track, settings.SITE_URL)
        if request.query_params.get("thumb"):
            if page != 1:
                raise Http404("Thumbnails are of the first page")
            image = resume_builder.cached("thumb", track, data, template)
        else:
            pages = resume_builder.cached("pages", track, data, template)
            if not 1 <= page <= len(pages):
                raise Http404("No such page")
            image = pages[page - 1]
        response = HttpResponse(image, content_type="image/png")
        response["Cache-Control"] = "no-store"
        response["Content-Disposition"] = 'inline; filename="resume-preview.png"'
        response["X-Content-Type-Options"] = "nosniff"
        return response
