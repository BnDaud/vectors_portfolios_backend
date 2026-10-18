import importlib
from datetime import date
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from io import StringIO
from django.test import override_settings
import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.test import APIClient, APITestCase

from .models import (
    About, ENTRY_DESCRIPTION_MAX, PageView, Portfolio, PortfolioTrack, Profile, Proficiency, Resume, School,
    TRACK_CONTACT_FIELDS, Visitor,
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


class EntryDescriptionTests(APITestCase):
    """Resume, education and skill entries carry an optional, capped
    description shown on the resume board."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password="pw")
        profile = Profile.objects.create(user=cls.user, display_pic="https://img.example.com/p.png")
        cls.track = PortfolioTrack.objects.create(profile=profile, name="Full Stack", slug="full-stack",
                                                  display_pic="https://img.example.com/p.png")
        cls.about = About.objects.create(track=cls.track, skill="s", description="d")
        cls.resume = Resume.objects.create(about=cls.about, post="Dev", company_name="Acme",
                                           start_year=date(2022, 1, 1), end_year=date(2023, 1, 1),
                                           description="Built things.")
        cls.school = School.objects.create(about=cls.about, school_name="Uni", start_year=date(2018, 1, 1),
                                           end_year=date(2022, 1, 1), description="Studied things.")
        cls.skill = Proficiency.objects.create(about=cls.about, skill_name="Python", skill_range=80,
                                               description="Used daily.")

    def setUp(self):
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(user=self.user)

    def urls(self):
        return {"resume": f"{API}/resume/{self.resume.id}", "school": f"{API}/school/{self.school.id}",
                "proficiency": f"{API}/proficiency/{self.skill.id}"}

    def test_cap_is_240(self):
        self.assertEqual(ENTRY_DESCRIPTION_MAX, 240)

    def test_description_is_optional_everywhere(self):
        for name, url in self.urls().items():
            res = self.client.patch(url, {"description": ""}, format="json")
            self.assertEqual(res.status_code, 200, (name, res.content))
        res = self.client.post(f"{API}/resume/", {"about": self.about.id, "post": "Dev 2", "company_name": "B",
                                                  "start_year": "2023-01-01", "end_year": "2024-01-01"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["description"], "")

    def test_description_cap_enforced_on_all_three(self):
        for name, url in self.urls().items():
            ok = self.client.patch(url, {"description": "x" * 240}, format="json")
            self.assertEqual(ok.status_code, 200, (name, ok.content))
            bad = self.client.patch(url, {"description": "x" * 241}, format="json")
            self.assertEqual(bad.status_code, 400, name)
            self.assertIn("description", bad.json())

    def test_descriptions_are_in_the_public_payload(self):
        data = self.client.get(f"{API}/profiles/?username=owner").json()[0]
        about = data["tracks"][0]["about"]
        self.assertEqual(about["resume"][0]["description"], "Built things.")
        self.assertEqual(about["school"][0]["description"], "Studied things.")
        self.assertEqual(about["proficiency"][0]["description"], "Used daily.")

    def test_duplicate_copies_descriptions_and_they_then_diverge(self):
        res = self.client.post(f"{API}/tracks/", {"username": "owner", "name": "Copy", "copy_from": self.track.id},
                               format="json")
        self.assertEqual(res.status_code, 201, res.content)
        copy_about = About.objects.get(track_id=res.json()["id"])
        self.assertEqual(copy_about.resume.get().description, "Built things.")
        self.assertEqual(copy_about.school.get().description, "Studied things.")
        self.assertEqual(copy_about.proficiency.get().description, "Used daily.")

        self.client.patch(f"{API}/resume/{copy_about.resume.get().id}", {"description": "Copy only"}, format="json")
        self.resume.refresh_from_db()
        self.assertEqual(self.resume.description, "Built things.")


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])   # fast, tests only
class ChangePasswordTests(APITestCase):
    OLD = "Old-Passw0rd-xyz"
    NEW = "Brand-New-Passw0rd-42"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password=cls.OLD, first_name="Own", last_name="Er")
        Profile.objects.create(user=cls.user, display_pic="https://img.example.com/p.png")

    def setUp(self):
        cache.clear()      # the endpoint is rate limited; keep tests independent
        self.url = f"{API}/auth/change-password"

    def session(self, password=None):
        client = APIClient(HTTP_HOST="localhost")
        res = client.post(f"{API}/auth/login", {"username": "owner", "password": password or self.OLD}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        return client

    def me(self, client):
        return client.get(f"{API}/auth/me").json()["authenticated"]

    def change(self, client, current, new):
        return client.post(self.url, {"current_password": current, "new_password": new}, format="json")

    def test_wrong_current_password_is_rejected_and_nothing_changes(self):
        client = self.session()
        res = self.change(client, "not-the-password", self.NEW)
        self.assertEqual(res.status_code, 400)
        self.assertIn("current_password", res.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.OLD))

    def test_weak_or_unchanged_new_passwords_are_rejected(self):
        client = self.session()
        for weak in ("short1", "password123", "12345678901", "owner1234", self.OLD):
            res = self.change(client, self.OLD, weak)
            self.assertEqual(res.status_code, 400, weak)
            self.assertIn("new_password", res.json(), weak)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.OLD))

    def test_missing_fields_are_rejected(self):
        client = self.session()
        res = client.post(self.url, {}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(set(res.json()), {"current_password", "new_password"})

    def test_change_works_and_the_same_session_keeps_going(self):
        client = self.session()
        res = self.change(client, self.OLD, self.NEW)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)
        self.assertTrue(self.me(client), "current session should stay signed in")
        # and it can still write
        track = PortfolioTrack.objects.create(profile=Profile.objects.get(), name="T", slug="t",
                                              display_pic="https://img.example.com/p.png")
        res = client.patch(f"{API}/tracks/{track.id}", {"name": "T2"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)

    def test_old_password_stops_working_and_new_one_logs_in(self):
        self.change(self.session(), self.OLD, self.NEW)
        anon = APIClient(HTTP_HOST="localhost")
        self.assertEqual(anon.post(f"{API}/auth/login", {"username": "owner", "password": self.OLD},
                                   format="json").status_code, 401)
        self.assertEqual(anon.post(f"{API}/auth/login", {"username": "owner", "password": self.NEW},
                                   format="json").status_code, 200)

    def test_other_sessions_are_signed_out_but_can_log_in_again(self):
        phone, laptop = self.session(), self.session()
        self.assertTrue(self.me(phone) and self.me(laptop))

        self.assertEqual(self.change(laptop, self.OLD, self.NEW).status_code, 200)

        self.assertFalse(self.me(phone), "old session must be revoked")
        track = PortfolioTrack.objects.create(profile=Profile.objects.get(), name="T", slug="t",
                                              display_pic="https://img.example.com/p.png")
        self.assertIn(phone.patch(f"{API}/tracks/{track.id}", {"name": "Hacked"}, format="json").status_code,
                      (401, 403))
        # public reads and logging in again still work with the stale cookies attached
        self.assertEqual(phone.get(f"{API}/tracks/").status_code, 200)
        relog = phone.post(f"{API}/auth/login", {"username": "owner", "password": self.NEW}, format="json")
        self.assertEqual(relog.status_code, 200, relog.content)
        self.assertTrue(self.me(phone))

    def test_anonymous_cannot_change_a_password(self):
        res = self.change(APIClient(HTTP_HOST="localhost"), self.OLD, self.NEW)
        self.assertIn(res.status_code, (401, 403))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.OLD))

    def test_guessing_is_rate_limited(self):
        client = self.session()
        codes = [self.change(client, f"guess-{i}", self.NEW).status_code for i in range(7)]
        self.assertEqual(codes[:5], [400] * 5)
        self.assertEqual(codes[5], 429)

    def test_password_hash_is_never_in_the_public_profile(self):
        anon = APIClient(HTTP_HOST="localhost")
        for url in (f"{API}/profiles/?username=owner", f"{API}/profiles/{Profile.objects.get().id}"):
            body = anon.get(url).content.decode()
            self.assertNotIn("pbkdf2", body, url)
            self.assertNotIn('"password"', body, url)


class SeedEntryDescriptionsTests(APITestCase):
    """The one-off command that drafts descriptions for existing entries."""

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user("owner", password="pw")
        profile = Profile.objects.create(user=user, display_pic="https://img.example.com/p.png")
        track = PortfolioTrack.objects.create(profile=profile, name="Full Stack", slug="full-stack",
                                              display_pic="https://img.example.com/p.png")
        about = About.objects.create(track=track, skill="s", description="d")
        cls.job = Resume.objects.create(about=about, post="Robotic Instructor", company_name="Al Izzah",
                                        start_year=date(2022, 9, 1), end_year=date(2022, 10, 1))
        cls.written = Resume.objects.create(about=about, post="Class Teacher", company_name="Al Izzah",
                                            start_year=date(2022, 10, 1), end_year=date(2023, 1, 1),
                                            description="My own words.")
        cls.unknown = Resume.objects.create(about=about, post="Astronaut", company_name="NASA",
                                            start_year=date(2020, 1, 1), end_year=date(2021, 1, 1))
        cls.skill = Proficiency.objects.create(about=about, skill_name="Python", skill_range=80)
        cls.school = School.objects.create(about=about, school_name="Uni", start_year=date(2018, 1, 1),
                                           end_year=date(2022, 1, 1))

    def run_command(self, *args):
        out = StringIO()
        call_command("seed_entry_descriptions", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_command()
        self.assertIn("dry run", output)
        self.job.refresh_from_db()
        self.assertEqual(self.job.description, "")

    def test_apply_fills_blanks_only(self):
        self.run_command("--apply")
        for entry in (self.job, self.written, self.unknown, self.skill, self.school):
            entry.refresh_from_db()
        self.assertTrue(self.job.description)
        self.assertTrue(self.skill.description)
        self.assertEqual(self.written.description, "My own words.", "never overwrites what the owner wrote")
        self.assertEqual(self.unknown.description, "", "entries without a draft are left alone")
        self.assertEqual(self.school.description, "", "education is left for the owner to write")

    def test_is_idempotent(self):
        self.run_command("--apply")
        self.assertIn("0 entries", self.run_command("--apply"))

    def test_every_draft_fits_the_cap(self):
        from portfolio.management.commands import seed_entry_descriptions as seed
        for text in list(seed.RESUME_DESCRIPTIONS.values()) + list(seed.SKILL_DESCRIPTIONS.values()):
            self.assertLessEqual(len(text), ENTRY_DESCRIPTION_MAX, text)


BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])   # fast, tests only
class VisitorAnalyticsTests(APITestCase):
    """Anonymous visitor counting: the owner and bots don't count, a returning
    person is a repeat on the same visitor, and only the owner can read it."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("owner", password="Old-Passw0rd-xyz")
        cls.profile = Profile.objects.create(user=cls.user, display_pic="https://img.example.com/p.png")
        cls.fs = PortfolioTrack.objects.create(profile=cls.profile, name="Full Stack", slug="full-stack",
                                               display_pic="https://img.example.com/p.png")
        cls.cad = PortfolioTrack.objects.create(profile=cls.profile, name="CAD Engineer", slug="cad",
                                                display_pic="https://img.example.com/p.png")

    def setUp(self):
        cache.clear()
        self.url = f"{API}/analytics/visit"
        self.summary = f"{API}/analytics/summary"

    def browser(self, agent=BROWSER):
        return APIClient(HTTP_HOST="localhost", HTTP_USER_AGENT=agent)

    def visit(self, vid, path="/", client=None):
        return (client or self.browser()).post(self.url, {"visitor_id": str(vid), "path": path}, format="json")

    def owner_client(self):
        client = self.browser()
        res = client.post(f"{API}/auth/login", {"username": "owner", "password": "Old-Passw0rd-xyz"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        return client

    def at(self, moment):
        return mock.patch("portfolio.analytics.timezone.now", return_value=moment)

    # --- counting ------------------------------------------------------------

    def test_a_first_visit_creates_one_visitor_and_one_page_view(self):
        vid = uuid.uuid4()
        self.assertEqual(self.visit(vid).status_code, 204)
        visitor = Visitor.objects.get()
        self.assertEqual((str(visitor.visitor_id), visitor.visit_count), (str(vid), 1))
        view = PageView.objects.get()
        self.assertIsNone(view.track)

    def test_repeating_the_same_page_in_one_visit_changes_nothing(self):
        vid = uuid.uuid4()
        for _ in range(3):
            self.visit(vid)
            self.visit(vid, "full-stack")
        self.assertEqual((Visitor.objects.count(), Visitor.objects.get().visit_count), (1, 1))
        self.assertEqual(PageView.objects.count(), 2)       # landing + full-stack, once each

    def test_browsing_more_portfolios_in_the_same_visit_is_not_a_new_visit(self):
        vid = uuid.uuid4()
        self.visit(vid); self.visit(vid, "full-stack"); self.visit(vid, "/cad")
        visitor = Visitor.objects.get()
        self.assertEqual(visitor.visit_count, 1)
        self.assertEqual(set(visitor.views.values_list("track__slug", flat=True)), {None, "full-stack", "cad"})

    def test_coming_back_later_is_a_repeat_on_the_same_visitor_not_a_new_one(self):
        vid, start = uuid.uuid4(), timezone.now()
        with self.at(start):
            self.visit(vid, "full-stack")
        with self.at(start + timedelta(minutes=10)):
            self.visit(vid, "cad")                          # same session
        self.assertEqual(Visitor.objects.get().visit_count, 1)
        with self.at(start + timedelta(minutes=10 + 31)):
            self.visit(vid, "full-stack")                   # a fresh visit, same person
        self.assertEqual(Visitor.objects.count(), 1, "unique visitors must not go up")
        self.assertEqual(Visitor.objects.get().visit_count, 2)
        self.assertEqual(PageView.objects.filter(track=self.fs).count(), 2, "the repeat is recorded")

    def test_different_browsers_are_different_visitors(self):
        self.visit(uuid.uuid4()); self.visit(uuid.uuid4())
        self.assertEqual(Visitor.objects.count(), 2)

    # --- who is NOT counted ---------------------------------------------------

    def test_the_signed_in_owner_is_never_counted(self):
        owner = self.owner_client()
        res = self.visit(uuid.uuid4(), "full-stack", client=owner)
        self.assertEqual(res.status_code, 204)
        self.assertEqual((Visitor.objects.count(), PageView.objects.count()), (0, 0))

    def test_an_owner_whose_session_was_revoked_is_just_a_visitor(self):
        owner = self.owner_client()
        stale = {c: owner.cookies[c].value for c in ("access_token", "refresh_token")}
        self.user.set_password("Some-Other-Pass-9"); self.user.save()      # revokes the old tokens
        client = self.browser()
        for name, value in stale.items():
            client.cookies[name] = value
        self.visit(uuid.uuid4(), client=client)
        self.assertEqual(Visitor.objects.count(), 1)

    def test_bots_and_automation_are_not_counted(self):
        for agent in ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                      "Mozilla/5.0 HeadlessChrome/120.0", "Slackbot-LinkExpanding 1.0", "python-requests/2.31",
                      "facebookexternalhit/1.1", "Chrome-Lighthouse", ""):
            self.assertEqual(self.visit(uuid.uuid4(), client=self.browser(agent)).status_code, 204, agent)
        self.assertEqual(Visitor.objects.count(), 0)
        self.visit(uuid.uuid4())
        self.assertEqual(Visitor.objects.count(), 1)

    def test_unknown_pages_are_ignored_and_look_identical_to_counted_ones(self):
        res = self.visit(uuid.uuid4(), "no-such-portfolio")
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Visitor.objects.count(), 0)

    def test_bad_requests(self):
        self.assertEqual(self.browser().post(self.url, {"path": "/"}, format="json").status_code, 400)
        self.assertEqual(self.visit("not-a-uuid").status_code, 400)
        res = self.browser().post(self.url, {"visitor_id": str(uuid.uuid4()), "path": {"x": 1}}, format="json")
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Visitor.objects.count(), 0)

    def test_the_beacon_is_rate_limited_per_ip(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"visit": "3/hour"}):
            codes = [self.visit(uuid.uuid4()).status_code for _ in range(5)]
        self.assertEqual(codes, [204, 204, 204, 429, 429])
        self.assertEqual(Visitor.objects.count(), 3)

    # --- who can SEE it ---------------------------------------------------------

    def test_only_the_signed_in_owner_can_read_the_summary(self):
        self.assertIn(self.browser().get(self.summary).status_code, (401, 403))
        self.assertEqual(self.owner_client().get(self.summary).status_code, 200)

    def test_summary_numbers(self):
        a, b, c, t0 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), timezone.now() - timedelta(hours=3)
        with self.at(t0):
            self.visit(a); self.visit(a, "full-stack")      # A: visit 1
            self.visit(b, "cad")
            self.visit(c)
        with self.at(t0 + timedelta(hours=2)):
            self.visit(a, "cad")                            # A comes back: visit 2
        data = self.owner_client().get(self.summary).json()

        self.assertEqual(data["unique_visitors"], 3, "A counted once even though they came twice")
        self.assertEqual(data["returning_visitors"], 1)
        self.assertEqual(data["total_visits"], 4)
        self.assertEqual(data["new_last_7_days"], 3)
        self.assertEqual(data["landing"], {"viewers": 2, "visits": 2})
        by_slug = {p["slug"]: p for p in data["portfolios"]}
        self.assertEqual(by_slug["full-stack"], {"slug": "full-stack", "name": "Full Stack", "viewers": 1, "visits": 1})
        self.assertEqual((by_slug["cad"]["viewers"], by_slug["cad"]["visits"]), (2, 2))

        recent = data["recent"]
        self.assertEqual(len(recent), 3)
        first = recent[0]                                    # A was seen most recently
        self.assertTrue(first["returning"] and first["visits"] == 2)
        self.assertEqual({v["slug"]: v["visits"] for v in first["viewed"]}, {"full-stack": 1, "cad": 1})
        self.assertEqual(first["landing_visits"], 1)
        self.assertFalse(any(r["returning"] for r in recent[1:]))

    def test_summary_exposes_no_browser_ids_or_network_details(self):
        vid = uuid.uuid4()
        self.visit(vid)
        body = self.owner_client().get(self.summary).content.decode()
        self.assertNotIn(str(vid), body)
        self.assertEqual({f.name for f in Visitor._meta.get_fields()} & {"ip", "ip_address", "user_agent"}, set())

    def test_deleting_a_portfolio_keeps_the_visitors(self):
        vid = uuid.uuid4()
        self.visit(vid, "full-stack")
        self.fs.delete()
        self.assertEqual((Visitor.objects.count(), PageView.objects.count()), (1, 0))
