import uuid
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .analytics import is_bot, is_owner, record_resume_view, record_visit
from .models import PageView, PortfolioTrack, ResumeView, Visitor

RECENT_LIMIT = 50
RECENT_RESUME_LIMIT = 15


class RecordVisitView(APIView):
    """
    Public beacon the site sends when a page is opened. It always answers 204
    - whether or not anything was counted - so it can't be used to probe which
    portfolios exist or whether a visit was ignored. Owners (signed in), bots
    and unknown portfolios are silently not counted.
    """
    name = "analytics_visit"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "visit"

    def post(self, request):
        try:
            visitor_uuid = uuid.UUID(str(request.data.get("visitor_id", "")))
        except ValueError:
            return Response({"visitor_id": ["A valid visitor id is required."]}, status=400)

        path = request.data.get("path", "/")
        if not isinstance(path, str):
            return Response(status=204)

        if is_bot(request) or is_owner(request):
            return Response(status=204)

        track = None
        if path != "/":
            track = PortfolioTrack.objects.filter(slug=path.strip("/")).first()
            if track is None:
                return Response(status=204)

        record_visit(visitor_uuid, track)
        return Response(status=204)


class RecordResumeViewView(APIView):
    """
    Public beacon the read-only resume page sends when it opens. Same rules as the
    visit beacon: always 204, and the owner, bots and unknown portfolios are
    silently not counted.
    """
    name = "analytics_resume_view"
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "visit"

    def post(self, request):
        try:
            visitor_uuid = uuid.UUID(str(request.data.get("visitor_id", "")))
        except ValueError:
            return Response({"visitor_id": ["A valid visitor id is required."]}, status=400)

        slug = request.data.get("slug", "")
        if not isinstance(slug, str) or is_bot(request) or is_owner(request):
            return Response(status=204)

        track = PortfolioTrack.objects.filter(slug=slug).first()
        if track is not None:
            record_resume_view(visitor_uuid, track)
        return Response(status=204)


class VisitorSummaryView(APIView):
    """Owner-only: how many people came, who came back, and what they looked at."""
    name = "analytics_summary"
    permission_classes = [IsAuthenticated]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)
        visitors = Visitor.objects
        totals = visitors.aggregate(unique=Count("id"), visits=Sum("visit_count"))

        def reach(views):
            counts = views.aggregate(viewers=Count("visitor", distinct=True), visits=Count("id"))
            return {"viewers": counts["viewers"], "visits": counts["visits"]}

        portfolios = [
            {"slug": track.slug, "name": track.name, **reach(PageView.objects.filter(track=track))}
            for track in PortfolioTrack.objects.order_by("order", "id")
        ]

        recent = []
        for visitor in visitors.prefetch_related("views__track", "resume_views__track")[:RECENT_LIMIT]:
            per_track, landing = {}, 0
            resumes = {}
            for opened in visitor.resume_views.all():
                entry = resumes.setdefault(opened.track.slug, {"slug": opened.track.slug, "name": opened.track.name, "views": 0, "last": opened.created_at})
                entry["views"] += 1
                entry["last"] = max(entry["last"], opened.created_at)
            for view in visitor.views.all():
                if view.track is None:
                    landing += 1
                else:
                    entry = per_track.setdefault(view.track.slug, {"slug": view.track.slug, "name": view.track.name, "visits": 0})
                    entry["visits"] += 1
            recent.append({
                "id": visitor.pk,
                "first_seen": visitor.first_seen,
                "last_seen": visitor.last_seen,
                "visits": visitor.visit_count,
                "returning": visitor.visit_count > 1,
                "landing_visits": landing,
                "viewed": list(per_track.values()),
                "resume_views": list(resumes.values()),
            })

        resume_rows = ResumeView.objects.select_related("track")
        resume_by_portfolio = []
        for track in PortfolioTrack.objects.order_by("order", "id"):
            rows = resume_rows.filter(track=track)
            latest = rows.first()
            resume_by_portfolio.append({
                "slug": track.slug, "name": track.name, "views": rows.count(),
                "viewers": rows.values("visitor").distinct().count(),
                "last_viewed": latest.created_at if latest else None,
            })

        return Response({
            "unique_visitors": totals["unique"],
            "returning_visitors": visitors.filter(visit_count__gt=1).count(),
            "total_visits": totals["visits"] or 0,
            "new_last_7_days": visitors.filter(first_seen__gte=week_ago).count(),
            "landing": reach(PageView.objects.filter(track__isnull=True)),
            "portfolios": portfolios,
            "recent": recent,
            "resume": {
                "total_views": resume_rows.count(),
                "viewers": resume_rows.values("visitor").distinct().count(),
                "portfolios": resume_by_portfolio,
                "recent": [
                    {"visitor": row.visitor_id, "slug": row.track.slug, "name": row.track.name, "at": row.created_at}
                    for row in resume_rows[:RECENT_RESUME_LIMIT]
                ],
            },
        })
