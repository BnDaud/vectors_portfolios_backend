import uuid
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.conf import settings

from .analytics import is_bot, is_owner, page_from_path, record_resume_view, record_visit
from .permissions import is_site_owner
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

        if is_bot(request):
            return Response(status=204)

        username, slug = page_from_path(path)
        if username is None:
            return Response(status=204)
        if slug is None:
            # the site's landing page counts; another account's own front page is not tracked
            if username != settings.SITE_OWNER_USERNAME or is_owner(request):
                return Response(status=204)
            record_visit(visitor_uuid, None)
            return Response(status=204)

        track = PortfolioTrack.objects.select_related("profile__user").filter(slug=slug, profile__user__username=username).first()
        if track is None or is_owner(request, track.profile.user):
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
        username = request.data.get("username") or settings.SITE_OWNER_USERNAME
        if not isinstance(slug, str) or not isinstance(username, str) or is_bot(request):
            return Response(status=204)

        track = PortfolioTrack.objects.select_related("profile__user").filter(slug=slug, profile__user__username=username).first()
        if track is not None and not is_owner(request, track.profile.user):
            record_resume_view(visitor_uuid, track)
        return Response(status=204)


class VisitorSummaryView(APIView):
    """Owner-only: how many people came, who came back, and what they looked at."""
    name = "analytics_summary"
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Only this account's own portfolios (and, for the site owner, the landing page): one user never sees
        another's traffic."""
        week_ago = timezone.now() - timedelta(days=7)
        mine = PortfolioTrack.objects.filter(profile__user=request.user).order_by("order", "id")
        with_landing = is_site_owner(request.user)
        page_views = PageView.objects.filter(Q(track__in=mine) | Q(track__isnull=True)) if with_landing else PageView.objects.filter(track__in=mine)
        resume_rows = ResumeView.objects.select_related("track").filter(track__in=mine)
        visitors = Visitor.objects.filter(
            Q(pk__in=page_views.values("visitor")) | Q(pk__in=resume_rows.values("visitor"))
        ).distinct()
        totals = visitors.aggregate(unique=Count("id", distinct=True), visits=Sum("visit_count"))

        def reach(views):
            counts = views.aggregate(viewers=Count("visitor", distinct=True), visits=Count("id"))
            return {"viewers": counts["viewers"], "visits": counts["visits"]}

        portfolios = [{"slug": track.slug, "name": track.name, **reach(page_views.filter(track=track))} for track in mine]
        mine_ids = {track.pk for track in mine}

        recent = []
        for visitor in visitors.prefetch_related("views__track", "resume_views__track")[:RECENT_LIMIT]:
            per_track, landing = {}, 0
            resumes = {}
            for opened in visitor.resume_views.all():
                if opened.track_id not in mine_ids:
                    continue
                entry = resumes.setdefault(opened.track.slug, {"slug": opened.track.slug, "name": opened.track.name, "views": 0, "last": opened.created_at})
                entry["views"] += 1
                entry["last"] = max(entry["last"], opened.created_at)
            for view in visitor.views.all():
                if view.track is None:
                    landing += 1 if with_landing else 0
                elif view.track_id in mine_ids:
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

        resume_by_portfolio = []
        for track in mine:
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
            "landing": reach(page_views.filter(track__isnull=True)) if with_landing else {"viewers": 0, "visits": 0},
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
