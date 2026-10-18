import importlib
from datetime import date
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from .models import (
    About, Portfolio, PortfolioTrack, Profile, Proficiency, Resume, School,
    TRACK_CONTACT_FIELDS,
)

API = "/api_root"


class TrackIndependenceTests(APITestCase):
    """Every portfolio (track) owns its dp, links and about; duplicating a
    track copies them once and the two evolve separately afterwards."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password="pw", first_name="O", last_name="W")
        cls.profile = Profile.objects.create(
            user=cls.user,
            display_pic="https://img.example.com/profile.png",
            github="https://github.com/owner",
            linkedin="https://linkedin.com/in/owner",
            whatapp="https://wa.me/111",
            facebook="https://facebook.com/owner",
            twitter="https://x.com/owner",
            email="owner@example.com",
            phone_number="+111",
        )
        cls.track_a = cls.make_track("Full Stack", "full-stack", dp="https://img.example.com/a.png")

    @classmethod
    def make_track(cls, name, slug, dp):
        track = PortfolioTrack.objects.create(
            profile=cls.profile, name=name, slug=slug, display_pic=dp,
            github="https://github.com/a", email="a@example.com",
        )
        about = About.objects.create(
            track=track, skill=f"{name} dev", description=f"about {name}",
            image_link="https://img.example.com/about-a.png", experience_since=date(2022, 1, 1),
        )
        Resume.objects.create(about=about, post="Dev", start_year=date(2022, 1, 1),
                              end_year=date(2023, 1, 1), company_name="Acme")
        School.objects.create(about=about, school_name="Uni", start_year=date(2018, 1, 1),
                              end_year=date(2022, 1, 1))
        Proficiency.objects.create(about=about, skill_name="Python", skill_range=80)
        Portfolio.objects.create(track=track, category="WebDev", name="Site",
                                 thumbnail="https://a.com/t.png", project_link="https://a.com")
        return track

    def setUp(self):
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(user=self.user)

    def duplicate(self, source, name="Copy", copy_items=True):
        res = self.client.post(f"{API}/tracks/", {
            "username": "owner", "name": name, "copy_from": source.id,
            "copy_portfolio_items": copy_items,
        }, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        return PortfolioTrack.objects.get(pk=res.json()["id"])

    # --- independence between tracks -------------------------------------

    def test_editing_one_tracks_dp_leaves_others_and_profile_untouched(self):
        track_b = self.make_track("CAD", "cad", dp="https://img.example.com/b.png")

        res = self.client.patch(f"{API}/tracks/{self.track_a.id}",
                                {"display_pic": "https://img.example.com/new-a.png"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)

        self.track_a.refresh_from_db(); track_b.refresh_from_db(); self.profile.refresh_from_db()
        self.assertEqual(self.track_a.display_pic, "https://img.example.com/new-a.png")
        self.assertEqual(track_b.display_pic, "https://img.example.com/b.png")
        self.assertEqual(self.profile.display_pic, "https://img.example.com/profile.png")

    def test_every_contact_field_is_editable_per_track(self):
        track_b = self.make_track("CAD", "cad", dp="https://img.example.com/b.png")
        payload = {
            "display_pic": "https://img.example.com/x.png", "github": "https://github.com/x",
            "linkedin": "https://linkedin.com/in/x", "whatapp": "https://wa.me/222",
            "facebook": "https://facebook.com/x", "twitter": "https://x.com/x",
            "email": "x@example.com", "phone_number": "+222",
        }
        self.assertEqual(set(payload), set(TRACK_CONTACT_FIELDS))
        res = self.client.patch(f"{API}/tracks/{self.track_a.id}", payload, format="json")
        self.assertEqual(res.status_code, 200, res.content)

        self.track_a.refresh_from_db(); track_b.refresh_from_db()
        for field, value in payload.items():
            self.assertEqual(getattr(self.track_a, field), value, field)
            self.assertNotEqual(getattr(track_b, field), value, field)

    def test_about_is_per_track(self):
        track_b = self.make_track("CAD", "cad", dp="https://img.example.com/b.png")
        res = self.client.patch(f"{API}/about/{self.track_a.about.id}",
                                {"description": "changed", "skill": "Changed skill"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        track_b.about.refresh_from_db()
        self.assertEqual(track_b.about.description, "about CAD")
        self.assertEqual(track_b.about.skill, "CAD dev")

    def test_tracks_endpoint_exposes_dp_for_each_landing_tile(self):
        track_b = self.make_track("CAD", "cad", dp="https://img.example.com/b.png")
        data = self.client.get(f"{API}/profiles/?username=owner").json()[0]
        dps = {t["id"]: t["display_pic"] for t in data["tracks"]}
        self.assertEqual(dps, {self.track_a.id: "https://img.example.com/a.png",
                               track_b.id: "https://img.example.com/b.png"})

    # --- duplicating -----------------------------------------------------

    def test_duplicate_carries_all_content_over(self):
        copy = self.duplicate(self.track_a)

        self.assertNotEqual(copy.id, self.track_a.id)
        self.assertNotEqual(copy.slug, self.track_a.slug)
        for field in TRACK_CONTACT_FIELDS:
            self.assertEqual(getattr(copy, field), getattr(self.track_a, field), field)
        self.assertEqual(copy.about.skill, self.track_a.about.skill)
        self.assertEqual(copy.about.description, self.track_a.about.description)
        self.assertEqual(copy.about.image_link, self.track_a.about.image_link)
        self.assertEqual(copy.about.experience_since, self.track_a.about.experience_since)
        self.assertEqual(copy.about.resume.count(), 1)
        self.assertEqual(copy.about.school.count(), 1)
        self.assertEqual(copy.about.proficiency.count(), 1)
        self.assertEqual(copy.items.count(), 1)
        self.assertEqual(copy.items.get().name, "Site")

    def test_duplicate_can_skip_portfolio_items(self):
        copy = self.duplicate(self.track_a, copy_items=False)
        self.assertEqual(copy.items.count(), 0)
        self.assertEqual(copy.about.resume.count(), 1)

    def test_editing_the_copy_never_changes_the_original(self):
        copy = self.duplicate(self.track_a)
        self.client.patch(f"{API}/tracks/{copy.id}",
                          {"display_pic": "https://img.example.com/copy.png", "github": ""}, format="json")
        self.client.patch(f"{API}/about/{copy.about.id}", {"description": "copy text"}, format="json")
        self.client.patch(f"{API}/resume/{copy.about.resume.get().id}", {"post": "Copy post"}, format="json")
        self.client.patch(f"{API}/portfolio/{copy.items.get().id}", {"name": "Copy site"}, format="json")

        self.track_a.refresh_from_db()
        self.assertEqual(self.track_a.display_pic, "https://img.example.com/a.png")
        self.assertEqual(self.track_a.github, "https://github.com/a")
        self.assertEqual(self.track_a.about.description, "about Full Stack")
        self.assertEqual(self.track_a.about.resume.get().post, "Dev")
        self.assertEqual(self.track_a.items.get().name, "Site")

    def test_editing_the_original_never_changes_the_copy(self):
        copy = self.duplicate(self.track_a)
        self.client.patch(f"{API}/tracks/{self.track_a.id}",
                          {"display_pic": "https://img.example.com/orig-new.png"}, format="json")
        self.client.patch(f"{API}/about/{self.track_a.about.id}", {"description": "orig text"}, format="json")

        copy.refresh_from_db()
        self.assertEqual(copy.display_pic, "https://img.example.com/a.png")
        self.assertEqual(copy.about.description, "about Full Stack")

    def test_deleting_the_copy_leaves_the_original_intact(self):
        copy = self.duplicate(self.track_a)
        res = self.client.delete(f"{API}/tracks/{copy.id}")
        self.assertEqual(res.status_code, 204)
        self.track_a.refresh_from_db()
        self.assertEqual(self.track_a.about.resume.count(), 1)
        self.assertEqual(self.track_a.items.count(), 1)

    def test_blank_track_starts_from_the_owner_profile_then_stands_alone(self):
        res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "Blank"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        blank = PortfolioTrack.objects.get(pk=res.json()["id"])
        for field in TRACK_CONTACT_FIELDS:
            self.assertEqual(getattr(blank, field), getattr(self.profile, field), field)
        self.assertEqual(blank.about.skill, "")

        self.client.patch(f"{API}/tracks/{blank.id}", {"display_pic": "https://img.example.com/blank.png"},
                          format="json")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_pic, "https://img.example.com/profile.png")

    def test_bad_copy_from_is_rejected_and_creates_nothing(self):
        before = PortfolioTrack.objects.count()
        res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "X", "copy_from": 99999},
                               format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(PortfolioTrack.objects.count(), before)

    def test_cannot_copy_from_another_owners_track(self):
        other_user = User.objects.create_user("other", password="pw")
        other_profile = Profile.objects.create(user=other_user, display_pic="https://img.example.com/o.png")
        foreign = PortfolioTrack.objects.create(profile=other_profile, name="Theirs", slug="theirs")
        before = PortfolioTrack.objects.count()
        res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "X", "copy_from": foreign.id},
                               format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(PortfolioTrack.objects.count(), before)

    def test_duplicating_twice_gives_unique_slugs(self):
        first = self.duplicate(self.track_a, name="Full Stack")
        second = self.duplicate(self.track_a, name="Full Stack")
        self.assertEqual(len({self.track_a.slug, first.slug, second.slug}), 3)

    # --- validation / auth -----------------------------------------------

    def test_track_dp_cannot_be_blanked_or_set_to_a_non_url(self):
        for payload in ({"display_pic": ""}, {"display_pic": "not a url"}, {"github": "github.com/x"},
                        {"email": "x" * 51}):
            res = self.client.patch(f"{API}/tracks/{self.track_a.id}", payload, format="json")
            self.assertEqual(res.status_code, 400, payload)
        self.track_a.refresh_from_db()
        self.assertEqual(self.track_a.display_pic, "https://img.example.com/a.png")

    def test_optional_links_can_be_cleared(self):
        res = self.client.patch(f"{API}/tracks/{self.track_a.id}",
                                {"github": "", "twitter": "", "phone_number": ""}, format="json")
        self.assertEqual(res.status_code, 200, res.content)

    def test_anonymous_cannot_edit_a_track(self):
        anon = APIClient(HTTP_HOST="localhost")
        res = anon.patch(f"{API}/tracks/{self.track_a.id}", {"display_pic": "https://x.com/y.png"},
                         format="json")
        self.assertIn(res.status_code, (401, 403))
        self.assertEqual(anon.get(f"{API}/tracks/").status_code, 200)

    def test_rename_still_works_and_keeps_contact_fields(self):
        res = self.client.patch(f"{API}/tracks/{self.track_a.id}", {"name": "Renamed"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.track_a.refresh_from_db()
        self.assertEqual(self.track_a.slug, "renamed")
        self.assertEqual(self.track_a.display_pic, "https://img.example.com/a.png")


class RecentChangesTests(APITestCase):
    """CAD category and the 1000 character About description."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password="pw")
        profile = Profile.objects.create(user=cls.user, display_pic="https://img.example.com/p.png")
        cls.track = PortfolioTrack.objects.create(profile=profile, name="T", slug="t")
        cls.about = About.objects.create(track=cls.track, skill="s", description="d")

    def setUp(self):
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(user=self.user)

    def test_cad_category_accepted_and_wrong_case_rejected(self):
        body = {"track": self.track.id, "name": "n", "thumbnail": "https://a.com/t.png",
                "project_link": "https://a.com"}
        ok = self.client.post(f"{API}/portfolio/", {**body, "category": "CAD"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        bad = self.client.post(f"{API}/portfolio/", {**body, "category": "cad"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_description_limit_is_1000(self):
        url = f"{API}/about/{self.about.id}"
        self.assertEqual(self.client.patch(url, {"description": "x" * 1000}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"description": "x" * 1001}, format="json").status_code, 400)

    def test_cleared_experience_date_can_be_saved_as_null(self):
        res = self.client.patch(f"{API}/about/{self.about.id}", {"experience_since": None}, format="json")
        self.assertEqual(res.status_code, 200, res.content)


class ExperienceYearsTests(APITestCase):
    """Years of experience are entered per portfolio and gain +1 every
    January 1 on their own."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password="pw")
        cls.profile = Profile.objects.create(user=cls.user, display_pic="https://img.example.com/p.png")

    def setUp(self):
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(user=self.user)

    def make_track(self, name, slug, years, entered_in=2026):
        track = PortfolioTrack.objects.create(profile=self.profile, name=name, slug=slug,
                                              display_pic="https://img.example.com/p.png")
        about = About.objects.create(track=track, skill=name, description="d",
                                     experience_base_years=years, experience_base_year=entered_in)
        return track, about

    @staticmethod
    def pretend_year(year):
        return mock.patch("portfolio.models.current_year", return_value=year)

    def api_years(self, about):
        return self.client.get(f"{API}/about/{about.id}").json()["years_of_experience"]

    def test_gains_one_year_every_january_first(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        for year, expected in [(2026, 4), (2027, 5), (2028, 6), (2036, 14)]:
            with self.pretend_year(year):
                self.assertEqual(self.api_years(about), expected, year)

    def test_same_year_does_not_change_and_never_goes_negative(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        with self.pretend_year(2026):
            self.assertEqual(about.years_of_experience, 4)
        with self.pretend_year(2020):
            self.assertEqual(about.years_of_experience, 4)

    def test_each_portfolio_has_its_own_years(self):
        _, a = self.make_track("Full Stack", "full-stack", years=4)
        _, b = self.make_track("CAD Engineer", "cad", years=1)
        with self.pretend_year(2027):
            self.assertEqual((self.api_years(a), self.api_years(b)), (5, 2))
        res = self.client.patch(f"{API}/about/{b.id}", {"experience_base_years": 3}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.experience_base_years, b.experience_base_years), (4, 3))

    def test_saving_a_number_anchors_it_to_the_current_year(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        with self.pretend_year(2028):
            self.assertEqual(self.api_years(about), 6)          # what the form shows
            res = self.client.patch(f"{API}/about/{about.id}", {"experience_base_years": 6}, format="json")
            self.assertEqual(res.status_code, 200, res.content)
            self.assertEqual(res.json()["years_of_experience"], 6)
        about.refresh_from_db()
        self.assertEqual((about.experience_base_years, about.experience_base_year), (6, 2028))
        with self.pretend_year(2029):
            self.assertEqual(self.api_years(about), 7)

    def test_editing_other_fields_keeps_the_rollover_going(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        with self.pretend_year(2027):
            res = self.client.patch(f"{API}/about/{about.id}", {"description": "new text"}, format="json")
            self.assertEqual(res.status_code, 200, res.content)
        about.refresh_from_db()
        self.assertEqual((about.experience_base_years, about.experience_base_year), (4, 2026))
        with self.pretend_year(2027):
            self.assertEqual(self.api_years(about), 5)

    def test_typing_the_stored_number_again_after_new_year_sets_exactly_that(self):
        # Entered 2 in 2025; in 2026 the page shows 3. Typing 2 must show 2.
        _, about = self.make_track("CAD Engineer", "cad", years=2, entered_in=2025)
        with self.pretend_year(2026):
            self.assertEqual(self.api_years(about), 3)
            res = self.client.patch(f"{API}/about/{about.id}", {"experience_base_years": 2}, format="json")
            self.assertEqual(res.status_code, 200, res.content)
            self.assertEqual(res.json()["years_of_experience"], 2)
            self.assertEqual(self.api_years(about), 2)
        with self.pretend_year(2027):
            self.assertEqual(self.api_years(about), 3)

    def test_saving_the_displayed_number_unchanged_is_harmless(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        with self.pretend_year(2027):
            self.client.patch(f"{API}/about/{about.id}", {"experience_base_years": 5}, format="json")
            self.assertEqual(self.api_years(about), 5)
        with self.pretend_year(2028):
            self.assertEqual(self.api_years(about), 6)

    def test_clients_cannot_set_the_anchor_year(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        self.client.patch(f"{API}/about/{about.id}", {"experience_base_year": 1990}, format="json")
        about.refresh_from_db()
        self.assertEqual(about.experience_base_year, 2026)

    def test_years_validation(self):
        _, about = self.make_track("Full Stack", "full-stack", years=4)
        url = f"{API}/about/{about.id}"
        for bad in (-1, 81, 4.5, "abc", None):
            res = self.client.patch(url, {"experience_base_years": bad}, format="json")
            self.assertEqual(res.status_code, 400, bad)
        for good in (0, 80, 12):
            res = self.client.patch(url, {"experience_base_years": good}, format="json")
            self.assertEqual(res.status_code, 200, good)

    def test_duplicate_carries_years_and_then_stands_alone(self):
        source, about = self.make_track("Full Stack", "full-stack", years=4, entered_in=2026)
        with self.pretend_year(2027):
            res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "Copy", "copy_from": source.id},
                                   format="json")
            self.assertEqual(res.status_code, 201, res.content)
            copy_about = About.objects.get(track_id=res.json()["id"])
            self.assertEqual(self.api_years(copy_about), self.api_years(about))
            self.assertEqual(copy_about.years_of_experience, 5)

            self.client.patch(f"{API}/about/{copy_about.id}", {"experience_base_years": 9}, format="json")
            self.assertEqual(self.api_years(about), 5)
            self.client.patch(f"{API}/about/{about.id}", {"experience_base_years": 2}, format="json")
            copy_about.refresh_from_db()
            self.assertEqual(copy_about.years_of_experience, 9)

    def test_blank_track_starts_at_zero(self):
        res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "Blank"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["about"]["years_of_experience"], 0)

    def test_data_migration_converts_the_start_date(self):
        migration = importlib.import_module("portfolio.migrations.0014_experience_years_from_since")
        _, dated = self.make_track("Full Stack", "full-stack", years=0, entered_in=2000)
        dated.experience_since = date(2022, 7, 29)
        dated.save()
        _, undated = self.make_track("CAD", "cad", years=7, entered_in=2000)
        About.objects.filter(pk=undated.pk).update(experience_since=None)

        with mock.patch.object(migration, "date") as fake_date:
            fake_date.today.return_value = date(2026, 10, 18)
            migration.experience_years_from_start_date(django_apps, None)

        dated.refresh_from_db(); undated.refresh_from_db()
        self.assertEqual((dated.experience_base_years, dated.experience_base_year), (4, 2026))
        self.assertEqual((undated.experience_base_years, undated.experience_base_year), (0, 2026))
