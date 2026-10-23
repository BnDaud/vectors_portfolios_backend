"""Many accounts on one site: sign-up, the one-portfolio limit, and - above all - that no
account can read-write, move into, download or count anything of another's."""
import uuid
from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle

from . import resume_builder
from .models import About, Goal, PageView, Portfolio, PortfolioTrack, Proficiency, Profile, Resume, ResumeView, School, Visitor

API = "/api_root"
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
STRONG = "Correct-Horse-Battery-9"


def account(username, *, limit=None):
    user = User.objects.create_user(username, password=STRONG, first_name=username.title())
    return Profile.objects.create(user=user, display_pic="https://img.example.com/p.png", max_portfolios=limit)


def portfolio(profile, name, slug):
    track = PortfolioTrack.objects.create(profile=profile, name=name, slug=slug, display_pic="https://img.example.com/p.png")
    About.objects.create(track=track, skill=f"{name} skill", description=f"{name} about")
    return track


@override_settings(SITE_OWNER_USERNAME="owner", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SignupTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(HTTP_HOST="localhost")
        roomy = mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"signup": "1000/hour"})   # the limit has its own test
        roomy.start()
        self.addCleanup(roomy.stop)

    def signup(self, **body):
        return self.client.post(f"{API}/auth/signup", {"username": "ada", "password": STRONG, "first_name": "Ada", "last_name": "Lovelace", **body}, format="json")

    def test_sign_up_makes_an_account_with_one_portfolio_and_signs_in(self):
        res = self.signup()
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json(), {"username": "ada"})
        self.assertIn("access_token", res.cookies)
        self.assertTrue(res.cookies["access_token"]["httponly"])
        profile = Profile.objects.get(user__username="ada")
        self.assertEqual((profile.max_portfolios, profile.user.first_name, profile.user.last_name), (1, "Ada", "Lovelace"))
        self.assertTrue(profile.user.check_password(STRONG))
        self.assertFalse(profile.user.is_staff or profile.user.is_superuser)
        me = self.client.get(f"{API}/auth/me").json()
        self.assertEqual(me, {"authenticated": True, "username": "ada"})

    def test_usernames_are_web_address_safe_unique_and_not_reserved(self):
        account("owner")
        for bad in ("ab", "a" * 31, "has space", "émile", "../x", "-lead", "a/b"):
            self.assertEqual(self.signup(username=bad).status_code, 400, bad)
        for taken in ("owner", "OWNER", "login", "U", "admin", "resume"):
            res = self.signup(username=taken)
            self.assertEqual(res.status_code, 400, taken)
            self.assertIn("username", res.json())
        self.assertEqual(self.signup(username="ok_name-2").status_code, 201)

    def test_weak_or_missing_details_are_refused(self):
        for body in ({"password": "123"}, {"password": "password"}, {"password": "ada"}, {"password": ""}, {"first_name": ""}):
            self.assertEqual(self.signup(**body).status_code, 400, body)
        self.assertEqual(User.objects.count(), 0, "nothing half-made")

    def test_signing_up_is_rate_limited(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"signup": "2/hour"}):
            codes = [self.signup(username=f"user{i}x").status_code for i in range(4)]
        self.assertEqual(codes, [201, 201, 429, 429])

    def test_the_new_account_then_logs_in_with_its_password(self):
        self.signup()
        fresh = APIClient(HTTP_HOST="localhost")
        self.assertEqual(fresh.post(f"{API}/auth/login", {"username": "ada", "password": STRONG}, format="json").status_code, 200)
        self.assertEqual(fresh.post(f"{API}/auth/login", {"username": "ada", "password": "wrong"}, format="json").status_code, 401)

    def test_the_payload_shows_the_limit_but_no_secrets(self):
        self.signup()
        body = APIClient(HTTP_HOST="localhost").get(f"{API}/profiles/?username=ada").json()[0]
        self.assertEqual(body["max_portfolios"], 1)
        self.assertNotIn("google_sub", body)
        self.assertNotIn("password", body["user"])


@override_settings(SITE_OWNER_USERNAME="owner", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PortfolioLimitTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = account("owner")
        cls.ada = account("ada", limit=1)

    def as_(self, profile):
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user=profile.user)
        return client

    def new(self, client, username, **extra):
        return client.post(f"{API}/tracks/", {"username": username, "name": extra.pop("name", "Mine"), **extra}, format="json")

    def test_a_new_account_gets_one_portfolio(self):
        client = self.as_(self.ada)
        self.assertEqual(self.new(client, "ada").status_code, 201)
        second = self.new(client, "ada", name="Another")
        self.assertEqual(second.status_code, 400)
        self.assertIn("1 portfolio", str(second.json()))
        self.assertEqual(self.ada.tracks.count(), 1)

    def test_copying_or_a_goal_cannot_get_round_the_limit(self):
        client = self.as_(self.ada)
        first = PortfolioTrack.objects.get(pk=self.new(client, "ada").json()["id"])
        self.assertEqual(self.new(client, "ada", name="Copy", copy_from=first.id, copy_portfolio_items=True).status_code, 400)
        goal = Goal.objects.create(profile=self.ada, title="Learn")
        res = client.patch(f"{API}/goals/{goal.id}/complete", {"entry_type": "skill", "entry_data": {"skill_name": "Go", "skill_range": 50},
                                                              "new_track": {"name": "Via goal"}}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.ada.tracks.count(), 1)

    def test_deleting_it_frees_the_slot(self):
        client = self.as_(self.ada)
        first = self.new(client, "ada").json()["id"]
        self.assertEqual(client.delete(f"{API}/tracks/{first}").status_code, 204)
        self.assertEqual(self.new(client, "ada", name="Fresh start").status_code, 201)

    def test_the_site_owner_has_no_limit(self):
        client = self.as_(self.owner)
        for i in range(4):
            self.assertEqual(self.new(client, "owner", name=f"Track {i}").status_code, 201)


@override_settings(SITE_OWNER_USERNAME="owner", SITE_URL="https://site.example", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IsolationTests(APITestCase):
    """Bea (a second account) tries everything against Ada's portfolio. Every attempt must fail
    and leave Ada's data exactly as it was."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = account("owner")
        cls.ada, cls.bea = account("ada", limit=1), account("bea", limit=1)
        cls.a_track = portfolio(cls.ada, "Full Stack", "full-stack")
        cls.b_track = portfolio(cls.bea, "Full Stack", "full-stack")       # same slug as Ada's on purpose
        cls.o_track = portfolio(cls.owner, "Full Stack", "full-stack")
        a_about = cls.a_track.about
        cls.a_job = Resume.objects.create(about=a_about, post="Dev", company_name="Co", start_year=date(2020, 1, 1), end_year=date(2021, 1, 1))
        cls.a_school = School.objects.create(about=a_about, school_name="Uni", start_year=date(2015, 1, 1), end_year=date(2019, 1, 1))
        cls.a_skill = Proficiency.objects.create(about=a_about, skill_name="Rust", skill_range=80)
        cls.a_goal = Goal.objects.create(profile=cls.ada, title="Ada's goal")
        cls.a_project = Portfolio.objects.create(category="WebDev", name="Ada site", thumbnail="https://a.com/t.png", project_link="https://ada.example.com")
        cls.a_project.tracks.add(cls.a_track)
        cls.b_project = Portfolio.objects.create(category="WebDev", name="Bea site", thumbnail="https://a.com/b.png", project_link="https://bea.example.com")
        cls.b_project.tracks.add(cls.b_track)

    def setUp(self):
        cache.clear()
        self.bea_client = APIClient(HTTP_HOST="localhost")
        self.bea_client.force_authenticate(user=self.bea.user)
        self.ada_client = APIClient(HTTP_HOST="localhost")
        self.ada_client.force_authenticate(user=self.ada.user)

    def snapshot(self):
        return {
            "track": PortfolioTrack.objects.filter(pk=self.a_track.pk).values("name", "email", "display_pic").first(),
            "about": About.objects.filter(pk=self.a_track.about.pk).values("skill", "description", "track").first(),
            "job": Resume.objects.filter(pk=self.a_job.pk).values("post", "about").first(),
            "school": School.objects.filter(pk=self.a_school.pk).values("school_name", "about").first(),
            "skill": Proficiency.objects.filter(pk=self.a_skill.pk).values("skill_name", "about").first(),
            "goal": Goal.objects.filter(pk=self.a_goal.pk).values("title", "status").first(),
            "project": (Portfolio.objects.filter(pk=self.a_project.pk).values("name").first(), sorted(self.a_project.tracks.values_list("pk", flat=True))),
            "profile": Profile.objects.filter(pk=self.ada.pk).values("display_pic", "email").first(),
            "user": User.objects.filter(pk=self.ada.user.pk).values("username", "first_name", "password").first(),
            "ada_counts": (self.a_track.about.resume.count(), self.a_track.about.school.count(), self.a_track.about.proficiency.count(), self.a_track.items.count(), self.ada.tracks.count()),
        }

    def assert_refused(self, res, label):
        self.assertIn(res.status_code, (400, 403, 404), f"{label}: {res.status_code} {res.content[:200]}")
        if res.status_code == 400:   # acceptable only as a refusal (permission, or a rule that blocks it anyway) - data is checked separately
            body = res.content.decode().lower()
            self.assertTrue(any(w in body for w in ("own", "already exists", "not found")), f"{label}: {body}")

    def test_bea_cannot_change_or_delete_anything_of_adas(self):
        before = self.snapshot()
        c = self.bea_client
        attempts = [
            ("edit Ada's portfolio", c.patch(f"{API}/tracks/{self.a_track.id}", {"name": "Hacked", "email": "x@x.com"}, format="json")),
            ("delete Ada's portfolio", c.delete(f"{API}/tracks/{self.a_track.id}")),
            ("edit Ada's about", c.patch(f"{API}/about/{self.a_track.about.id}", {"skill": "Hacked"}, format="json")),
            ("delete Ada's about", c.delete(f"{API}/about/{self.a_track.about.id}")),
            ("edit Ada's job", c.patch(f"{API}/resume/{self.a_job.id}", {"post": "Hacked"}, format="json")),
            ("delete Ada's job", c.delete(f"{API}/resume/{self.a_job.id}")),
            ("edit Ada's school", c.patch(f"{API}/school/{self.a_school.id}", {"school_name": "Hacked"}, format="json")),
            ("delete Ada's school", c.delete(f"{API}/school/{self.a_school.id}")),
            ("edit Ada's skill", c.patch(f"{API}/proficiency/{self.a_skill.id}", {"skill_name": "Hacked"}, format="json")),
            ("delete Ada's skill", c.delete(f"{API}/proficiency/{self.a_skill.id}")),
            ("edit Ada's project", c.patch(f"{API}/portfolio/{self.a_project.id}", {"name": "Hacked"}, format="json")),
            ("delete Ada's project", c.delete(f"{API}/portfolio/{self.a_project.id}?from={self.a_track.id}")),
            ("take Ada's project into her own portfolio", c.patch(f"{API}/portfolio/{self.a_project.id}", {"tracks": [self.b_track.id]}, format="json")),
            ("edit Ada's goal", c.patch(f"{API}/goals/{self.a_goal.id}", {"title": "Hacked"}, format="json")),
            ("delete Ada's goal", c.delete(f"{API}/goals/{self.a_goal.id}")),
            ("complete Ada's goal", c.patch(f"{API}/goals/{self.a_goal.id}/complete", {"entry_type": "skill", "entry_data": {"skill_name": "X"}, "track_ids": [self.a_track.id]}, format="json")),
            ("edit Ada's profile", c.patch(f"{API}/profiles/{self.ada.id}", {"display_pic": "https://evil.example/x.png", "email": "x@x.com"}, format="json")),
            ("change Ada's login details", c.patch(f"{API}/profiles/{self.ada.id}", {"user": {"username": "ada", "password": "Taken-over-123"}}, format="json")),
            ("delete Ada's profile", c.delete(f"{API}/profiles/{self.ada.id}")),
            ("edit Ada's user", c.patch(f"{API}/edit_user/{self.ada.user.id}", {"first_name": "Hacked", "password": "Taken-over-123", "username": "ada"}, format="json")),
        ]
        for label, res in attempts:
            self.assert_refused(res, label)
        self.assertEqual(self.snapshot(), before)

    def test_bea_cannot_add_anything_to_adas_portfolio(self):
        before = self.snapshot()
        c = self.bea_client
        attempts = [
            ("add a job to Ada", c.post(f"{API}/resume/", {"about": self.a_track.about.id, "post": "Spam", "company_name": "X", "start_year": "2020-01-01", "end_year": "2021-01-01"}, format="json")),
            ("add a school to Ada", c.post(f"{API}/school/", {"about": self.a_track.about.id, "school_name": "Spam", "start_year": "2020-01-01", "end_year": "2021-01-01"}, format="json")),
            ("add a skill to Ada", c.post(f"{API}/proficiency/", {"about": self.a_track.about.id, "skill_name": "Spam", "skill_range": 5}, format="json")),
            ("add an about to Ada", c.post(f"{API}/about/", {"track": self.a_track.id, "skill": "Spam", "description": "x"}, format="json")),
            ("add a project to Ada", c.post(f"{API}/portfolio/", {"track": self.a_track.id, "category": "WebDev", "name": "Spam", "thumbnail": "https://a.com/s.png", "project_link": "https://spam.example.com"}, format="json")),
            ("share her own new project into Ada's", c.post(f"{API}/portfolio/", {"track": self.b_track.id, "share_with": [self.a_track.id], "category": "WebDev", "name": "Spam", "thumbnail": "https://a.com/s.png", "project_link": "https://spam.example.com"}, format="json")),
            ("share her existing project into Ada's", c.patch(f"{API}/portfolio/{self.b_project.id}", {"tracks": [self.b_track.id, self.a_track.id]}, format="json")),
            ("make a portfolio in Ada's name", c.post(f"{API}/tracks/", {"username": "ada", "name": "Spam"}, format="json")),
            ("copy Ada's portfolio", c.post(f"{API}/tracks/", {"username": "bea", "name": "Copy", "copy_from": self.a_track.id}, format="json")),
            ("make a goal in Ada's name", c.post(f"{API}/goals/", {"username": "ada", "title": "Spam"}, format="json")),
            ("make a user", c.post(f"{API}/createuser", {"username": "minion", "password": "Whatever-123", "first_name": "M"}, format="json")),
            ("make a profile", c.post(f"{API}/profiles/", {"user": {"username": "minion2", "password": "Whatever-123"}, "display_pic": "https://a.com/x.png"}, format="json")),
        ]
        for label, res in attempts:
            self.assert_refused(res, label)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(User.objects.filter(username__in=["minion", "minion2"]).exists())
        self.assertEqual(sorted(self.b_project.tracks.values_list("pk", flat=True)), [self.b_track.pk])

    def test_bea_cannot_move_her_own_entries_into_adas_portfolio(self):
        b_job = Resume.objects.create(about=self.b_track.about, post="Mine", company_name="Co", start_year=date(2020, 1, 1), end_year=date(2021, 1, 1))
        before = self.snapshot()
        for path, body in ((f"resume/{b_job.id}", {"about": self.a_track.about.id}),
                           (f"about/{self.b_track.about.id}", {"track": self.a_track.id})):
            self.assert_refused(self.bea_client.patch(f"{API}/{path}", body, format="json"), path)
        b_job.refresh_from_db()
        self.assertEqual(b_job.about_id, self.b_track.about.id)
        self.assertEqual(self.snapshot(), before)

    def test_each_account_can_still_change_its_own(self):
        self.assertEqual(self.ada_client.patch(f"{API}/resume/{self.a_job.id}", {"post": "Senior Dev"}, format="json").status_code, 200)
        self.assertEqual(self.bea_client.patch(f"{API}/portfolio/{self.b_project.id}", {"name": "Bea's new name"}, format="json").status_code, 200)
        self.assertEqual(self.bea_client.post(f"{API}/resume/", {"about": self.b_track.about.id, "post": "Mine", "company_name": "X", "start_year": "2020-01-01", "end_year": "2021-01-01"}, format="json").status_code, 201)

    def test_nobody_signed_out_can_change_anything(self):
        anon = APIClient(HTTP_HOST="localhost")
        for res in (anon.patch(f"{API}/tracks/{self.a_track.id}", {"name": "x"}, format="json"), anon.post(f"{API}/resume/", {"about": self.a_track.about.id}, format="json"),
                    anon.delete(f"{API}/portfolio/{self.a_project.id}"), anon.post(f"{API}/createuser", {"username": "x", "password": "y"}, format="json")):
            self.assertIn(res.status_code, (401, 403))

    # --- resumes ---------------------------------------------------------------------------------

    def test_each_account_downloads_only_its_own_resume(self):
        mine = self.bea_client.get(f"{API}/resume-export/full-stack/download/pdf?u=bea")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(self.bea_client.get(f"{API}/resume-export/full-stack/download/pdf?u=ada").status_code, 403)
        self.assertEqual(self.bea_client.get(f"{API}/resume-export/full-stack/download/docx?u=ada").status_code, 403)
        self.assertEqual(self.bea_client.get(f"{API}/resume-export/full-stack/download/pdf").status_code, 403, "the site owner's, without ?u=")

    def test_the_same_portfolio_name_in_two_accounts_gives_two_resumes(self):
        anon = APIClient(HTTP_HOST="localhost")
        self.assertEqual(anon.get(f"{API}/resume-export/full-stack/pages?u=ada").json()["name"], "Ada")
        self.assertEqual(anon.get(f"{API}/resume-export/full-stack/pages?u=bea").json()["name"], "Bea")
        self.assertEqual(anon.get(f"{API}/resume-export/full-stack/pages").json()["name"], "Owner", "no ?u= means the site owner")
        self.assertEqual(anon.get(f"{API}/resume-export/full-stack/pages?u=nobody").status_code, 404)

    def test_resume_links_point_at_the_right_address(self):
        self.assertEqual(resume_builder.collect(self.a_track, "https://site.example")["links"][0], ("Portfolio", "https://site.example/u/ada/full-stack"))
        self.assertEqual(resume_builder.collect(self.o_track, "https://site.example")["links"][0], ("Portfolio", "https://site.example/full-stack"))

    # --- visitor stats ------------------------------------------------------------------------------

    def beacon(self, path, client=None):
        return (client or APIClient(HTTP_HOST="localhost", HTTP_USER_AGENT=BROWSER)).post(f"{API}/analytics/visit", {"visitor_id": str(uuid.uuid4()), "path": path}, format="json")

    def test_visits_are_counted_against_the_right_account(self):
        self.beacon("/u/ada/full-stack"); self.beacon("/u/bea/full-stack"); self.beacon("/full-stack"); self.beacon("/")
        self.beacon("/u/ada"); self.beacon("/u/nobody/full-stack"); self.beacon("/u/ada/nope"); self.beacon("/a/b/c")
        self.assertEqual(sorted((v.track.profile.user.username if v.track else "landing") for v in PageView.objects.select_related("track__profile__user")),
                         ["ada", "bea", "landing", "owner"])

    def test_an_owner_viewing_their_own_page_is_not_counted_but_another_user_is(self):
        ada_browser = APIClient(HTTP_HOST="localhost", HTTP_USER_AGENT=BROWSER)
        ada_browser.post(f"{API}/auth/login", {"username": "ada", "password": STRONG}, format="json")
        self.beacon("/u/ada/full-stack", client=ada_browser)
        self.assertEqual(PageView.objects.count(), 0)
        self.beacon("/u/bea/full-stack", client=ada_browser)
        self.assertEqual(PageView.objects.get().track, self.b_track)

    def test_each_account_sees_only_its_own_stats(self):
        self.beacon("/u/ada/full-stack"); self.beacon("/u/ada/full-stack"); self.beacon("/u/bea/full-stack"); self.beacon("/")
        anon = APIClient(HTTP_HOST="localhost", HTTP_USER_AGENT=BROWSER)
        anon.post(f"{API}/analytics/resume-view", {"visitor_id": str(uuid.uuid4()), "slug": "full-stack", "username": "bea"}, format="json")
        ada = self.ada_client.get(f"{API}/analytics/summary").json()
        bea = self.bea_client.get(f"{API}/analytics/summary").json()
        self.assertEqual((ada["unique_visitors"], [p["slug"] for p in ada["portfolios"]], ada["landing"]["visits"]), (2, ["full-stack"], 0))
        self.assertEqual((bea["unique_visitors"], bea["resume"]["total_views"], ada["resume"]["total_views"]), (2, 1, 0))
        owner = APIClient(HTTP_HOST="localhost"); owner.force_authenticate(user=self.owner.user)
        mine = owner.get(f"{API}/analytics/summary").json()
        self.assertEqual((mine["unique_visitors"], mine["landing"]["visits"]), (1, 1), "the site owner sees the landing page and only their own")
        self.assertEqual(ResumeView.objects.get().track, self.b_track)


@override_settings(SITE_OWNER_USERNAME="owner", GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com")
class GoogleSignInTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(HTTP_HOST="localhost")

    def claims(self, **extra):
        return {"iss": "https://accounts.google.com", "sub": "1234567890", "email": "ada.lovelace@gmail.com", "email_verified": True,
                "given_name": "Ada", "family_name": "Lovelace", "picture": "https://lh3.googleusercontent.com/a/pic", **extra}

    def google(self, claims=None, error=None, credential="signed.jwt.token"):
        with mock.patch("portfolio.auth_views.id_token.verify_oauth2_token", side_effect=error, return_value=claims or self.claims()) as verify:
            res = self.client.post(f"{API}/auth/google", {"credential": credential}, format="json")
        return res, verify

    def test_first_time_makes_an_account_then_signs_in_the_same_one(self):
        res, verify = self.google()
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(res.json()["created"])
        self.assertEqual(verify.call_args.args[2], "test-client.apps.googleusercontent.com", "checked against our client id")
        username = res.json()["username"]
        self.assertRegex(username, r"^ada-lovelace-[0-9a-f]{4}$")
        self.assertNotIn("gmail", username, "never the email")
        profile = Profile.objects.get(user__username=username)
        self.assertEqual((profile.max_portfolios, profile.display_pic, profile.user.has_usable_password()), (1, "https://lh3.googleusercontent.com/a/pic", False))
        self.assertIn("access_token", res.cookies)
        again, _ = self.google()
        self.assertEqual((again.status_code, again.json()), (200, {"username": username, "created": False}))
        self.assertEqual(User.objects.count(), 1)

    def test_bad_tokens_and_unverified_emails_are_refused(self):
        res, _ = self.google(error=ValueError("bad signature"))
        self.assertEqual(res.status_code, 401)
        res, _ = self.google(self.claims(email_verified=False))
        self.assertEqual(res.status_code, 403)
        res, _ = self.google(self.claims(iss="https://evil.example"))
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.client.post(f"{API}/auth/google", {}, format="json").status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_a_google_account_never_takes_over_an_existing_one(self):
        account("ada")
        res, _ = self.google(self.claims(given_name="ada", family_name=""))
        self.assertEqual(res.status_code, 201)
        self.assertNotEqual(res.json()["username"], "ada")
        self.assertEqual(User.objects.count(), 2)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_switched_off_without_a_client_id(self):
        res, _ = self.google()
        self.assertEqual(res.status_code, 503)
