from rest_framework.serializers import ModelSerializer  , HyperlinkedModelSerializer
from rest_framework.serializers import SlugRelatedField , HyperlinkedRelatedField
from rest_framework.serializers import ChoiceField ,CharField ,SerializerMethodField
from rest_framework.serializers import IntegerField , BooleanField , PrimaryKeyRelatedField , JSONField
from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.db import transaction
from . import models as portfolio_models
from .models import Profile , Portfolio , About , Resume , School , Proficiency , PortfolioTrack , Goal , TRACK_CONTACT_FIELDS


def _unique_slug(profile , name , exclude_pk = None):
    base = slugify(name)
    slug = base
    suffix = 2
    qs = PortfolioTrack.objects.filter(profile = profile , slug = slug)
    if exclude_pk:
        qs = qs.exclude(pk = exclude_pk)
    while qs.exists():
        slug = f"{base}-{suffix}"
        suffix += 1
        qs = PortfolioTrack.objects.filter(profile = profile , slug = slug)
        if exclude_pk:
            qs = qs.exclude(pk = exclude_pk)
    return slug


class Userserial(ModelSerializer):

    """ this serializer is responsible for the creation of new user
            And
    editing of the former ones


    """
    # write_only: this serializer is nested in the public profile payload, and
    # the stored hash must never be readable there.
    password = CharField(write_only = True , required = True)
    class Meta:
        model = User
        fields = ["username" , "first_name" , "last_name" , "password"]


    def create(self , validated_data):

        pword = validated_data.pop("password")
        user =  User.objects.create(**validated_data)
        user.set_password(pword)
        user.save()
        return user

    def update(self , instance ,new_data):

        instance.username = new_data.get("username" , instance.username)
        instance.first_name = new_data.get("first_name" , instance.first_name)
        instance.last_name = new_data.get("last_name" , instance.last_name)
        if len(new_data["password"]) > 0:

            instance.set_password(new_data["password"])

        instance.save()
        return instance



class ProficiencySerial(ModelSerializer):
    _about = SerializerMethodField()

    def get__about(self , obj):
        return obj.about.track.profile.user.username

    class Meta :
        model = Proficiency
        fields = "__all__"

class ResumeSerial(ModelSerializer):
    _about = SerializerMethodField()

    def get__about(self , obj):
        return obj.about.track.profile.user.username

    class Meta :
        model = Resume
        fields = "__all__"


class SchoolSerial(ModelSerializer):
    _about = SerializerMethodField()

    def get__about(self , obj):
        return obj.about.track.profile.user.username

    class Meta :
        model = School
        fields = "__all__"


class AboutSerial(ModelSerializer):
    resume = ResumeSerial(many = True , read_only = True)
    school = SchoolSerial(many = True , read_only = True)
    proficiency = ProficiencySerial(many = True , read_only = True)
    years_of_experience = SerializerMethodField()

    def get_years_of_experience(self , obj):
        return obj.years_of_experience

    def update(self , instance , validated_data):
        # Any save of the number means "this many years as of today", even if
        # it equals the stored base: after a January 1 the form shows base + 1,
        # so typing the old base back has to re-anchor it, not be ignored.
        if "experience_base_years" in validated_data:
            validated_data["experience_base_year"] = portfolio_models.current_year()
        return super().update(instance , validated_data)

    class Meta:
        model = About
        fields = "__all__"


def delete_if_in_no_portfolio(project):
    """A project shown in no portfolio is of no use to anyone: remove it. True when it was removed."""
    if project.pk and not project.tracks.exists():
        project.delete()
        return True
    return False


class PortfolioSerial(ModelSerializer):
    """
    A project, shared by as many portfolios as list it.
      read:   `tracks` - the ids of the portfolios that show it
      create: `track` - the portfolio it is added to; optionally `share_with` (a list of
              portfolio ids, or "all") to show it in others too, or `tracks` (the full list)
      update: `tracks` - the full list it should now be shown in; the others are untouched,
              and an empty list deletes the project (it would be shown nowhere)
    """
    category = ChoiceField(choices=Portfolio.portfolio_choice)

    display_username = SerializerMethodField(read_only = True)
    tracks = PrimaryKeyRelatedField(many = True , queryset = PortfolioTrack.objects.all() , required = False)
    track = PrimaryKeyRelatedField(queryset = PortfolioTrack.objects.all() , write_only = True , required = False)
    share_with = JSONField(write_only = True , required = False , allow_null = True)

    def get_display_username(self , obj):
        first = obj.tracks.first()
        return first.profile.user.username if first else ""

    class Meta:
        model = Portfolio
        fields = ["id", "category" , "display_username" , "tracks" , "track" , "share_with" , "name" , "thumbnail" , "project_link" , "description"]

    def validate(self , attrs):
        share = attrs.pop("share_with" , None)
        primary = attrs.pop("track" , None)
        if self.instance is not None:      # an edit: only `tracks` can change who shows it
            if "tracks" in attrs:
                self._same_owner(attrs["tracks"] , self.instance.tracks.first())
            return attrs

        targets = list(attrs.get("tracks" , []))
        if primary is not None:
            targets.append(primary)
        if not targets:
            raise serializers.ValidationError({"track": "Say which portfolio this project is added to."})
        owner = targets[0].profile
        if share == "all":
            targets += list(PortfolioTrack.objects.filter(profile = owner))
        elif share is not None:
            if not isinstance(share , list) or not all(isinstance(i , int) and not isinstance(i , bool) for i in share):
                raise serializers.ValidationError({"share_with": "Use a list of portfolio ids, or \"all\"."})
            found = {t.pk: t for t in PortfolioTrack.objects.filter(pk__in = share)}
            missing = [i for i in share if i not in found]
            if missing:
                raise serializers.ValidationError({"share_with": f"No such portfolio: {missing[0]}."})
            targets += [found[i] for i in share]
        self._same_owner(targets , targets[0])
        attrs["tracks"] = list({t.pk: t for t in targets}.values())
        return attrs

    @staticmethod
    def _same_owner(tracks , reference):
        if reference is not None and any(t.profile_id != reference.profile_id for t in tracks):
            raise serializers.ValidationError({"tracks": "A project can only be shared between portfolios of the same owner."})

    @transaction.atomic
    def update(self , instance , validated_data):
        wanted = validated_data.pop("tracks" , None)
        project = super().update(instance , validated_data)
        if wanted is not None:
            current = set(project.tracks.all())
            project.tracks.add(*(set(wanted) - current))       # add before removing, so it never sits in none by accident
            project.tracks.remove(*(current - set(wanted)))
            delete_if_in_no_portfolio(project)                  # unticked everywhere: gone (project.pk is then None)
        return project


class PortfolioTrackSerial(ModelSerializer):
    about = AboutSerial(read_only = True)
    items = PortfolioSerial(many = True , read_only = True)
    username = CharField(write_only = True , required = False)
    copy_from = IntegerField(write_only = True , required = False , allow_null = True)
    copy_portfolio_items = BooleanField(write_only = True , required = False , default = False)
    # instead of copying the projects, show the very same ones in the new portfolio (they become shared)
    share_portfolio_items = BooleanField(write_only = True , required = False , default = False)

    class Meta:
        model = PortfolioTrack
        fields = ["id" , "name" , "slug" , "is_default" , "order" , "about" , "items" ,
                  "username" , "copy_from" , "copy_portfolio_items" , "share_portfolio_items" , "location"] + TRACK_CONTACT_FIELDS
        extra_kwargs = {"slug": {"required": False}}

    @transaction.atomic
    def create(self , validated_data):
        username = validated_data.pop("username" , None)
        copy_from_id = validated_data.pop("copy_from" , None)
        copy_items = validated_data.pop("copy_portfolio_items" , False)
        share_items = validated_data.pop("share_portfolio_items" , False)

        if not username:
            raise serializers.ValidationError({"username": "This field is required."})

        profile = Profile.objects.get(user__username = username)

        # Resolve the source before creating anything so a bad copy_from
        # can't leave a half-made track behind.
        source = None
        if copy_from_id:
            source = PortfolioTrack.objects.filter(pk = copy_from_id , profile = profile).first()
            if source is None:
                raise serializers.ValidationError({"copy_from": "Portfolio not found."})

        # A new track gets its own copy of the dp/contact values - from the
        # track it is cloned from, else from the owner's profile - and is
        # independent of that origin from then on.
        origin = source or profile
        initial = {field: getattr(origin , field) for field in TRACK_CONTACT_FIELDS}
        if source is not None:
            initial["location"] = source.location

        if profile.max_portfolios is not None and profile.tracks.count() >= profile.max_portfolios:
            raise serializers.ValidationError({"detail": f"Your account can have {profile.max_portfolios} portfolio"
                                               f"{'' if profile.max_portfolios == 1 else 's'}. Delete one to make another."})

        validated_data.setdefault("slug" , _unique_slug(profile , validated_data["name"]))
        track = PortfolioTrack.objects.create(profile = profile , **{**initial , **validated_data})

        if source is not None:
            source_about = source.about
            new_about = About.objects.create(
                track = track,
                skill = source_about.skill,
                experience_since = source_about.experience_since,
                experience_base_years = source_about.experience_base_years,
                experience_base_year = source_about.experience_base_year,
                description = source_about.description,
                image_link = source_about.image_link,
            )
            for r in source_about.resume.all():
                Resume.objects.create(about = new_about , post = r.post , start_year = r.start_year ,
                                       end_year = r.end_year , company_name = r.company_name ,
                                       certificate_link = r.certificate_link , description = r.description)
            for s in source_about.school.all():
                School.objects.create(about = new_about , start_year = s.start_year , end_year = s.end_year ,
                                       school_name = s.school_name , degree = s.degree ,
                                       certificate_link = s.certificate_link , description = s.description)
            for p in source_about.proficiency.all():
                Proficiency.objects.create(about = new_about , skill_name = p.skill_name ,
                                            skill_range = p.skill_range , certificate_link = p.certificate_link ,
                                            description = p.description)
            if copy_items or share_items:
                for item in source.items.all():
                    if share_items:      # the same projects, now shown here too
                        item.tracks.add(track)
                        continue
                    # a copy of the portfolio gets its own copies of the projects, independent of the originals
                    Portfolio.objects.create(category = item.category , name = item.name ,
                                             thumbnail = item.thumbnail , project_link = item.project_link ,
                                             description = item.description).tracks.add(track)
        else:
            About.objects.create(track = track , skill = "" , description = "" , image_link = "")

        return track

    def update(self , instance , validated_data):
        validated_data.pop("username" , None)
        validated_data.pop("copy_from" , None)
        validated_data.pop("copy_portfolio_items" , None)
        validated_data.pop("share_portfolio_items" , None)

        new_name = validated_data.get("name")
        if new_name and new_name != instance.name and "slug" not in validated_data:
            validated_data["slug"] = _unique_slug(instance.profile , new_name , exclude_pk = instance.pk)

        return super().update(instance , validated_data)


class GoalSerial(ModelSerializer):
    username = CharField(write_only = True , required = False)

    class Meta:
        model = Goal
        fields = ["id" , "username" , "title" , "description" , "target_date" , "status" , "completed_at" , "created_at"]
        read_only_fields = ["status" , "completed_at" , "created_at"]

    def create(self , validated_data):
        username = validated_data.pop("username" , None)
        if not username:
            raise serializers.ValidationError({"username": "This field is required."})
        profile = Profile.objects.get(user__username = username)
        return Goal.objects.create(profile = profile , **validated_data)


class Profileserial(ModelSerializer):

    user = Userserial()
    tracks = PortfolioTrackSerial(many = True , read_only = True)

    class Meta:
        model = Profile
        fields = ["id" , "user" , "display_pic" ,"github" , "linkedin" , "whatapp" ,"facebook" ,"email","twitter","phone_number","tracks" , "max_portfolios"]
        read_only_fields = ["max_portfolios"]

    def create(self , validated_data):
        #img = validated_data.pop("display_pic")

        password = validated_data["user"].pop("password")
        validated_user = validated_data.pop("user")

        user = User.objects.create(**validated_user)
        user.set_password(password)
        user.save()
        profile = Profile.objects.create(user = user , **validated_data)

        return profile




    def update(self, instance, validated_data):

        display_pic = validated_data.pop("display_pic" , instance.display_pic)

        new_user_detail = validated_data.pop("user" , None)

        if new_user_detail is not None:
            user = instance.user
            password = new_user_detail.pop("password" , None)
            for field , value in new_user_detail.items():
                setattr(user , field , value)
            if password:
                user.set_password(password)
            user.save()

        instance.display_pic = display_pic
        instance.phone_number = validated_data.get("phone_number" , instance.phone_number)
        instance.linkedin = validated_data.get("linkedin" , instance.linkedin)
        instance.whatapp = validated_data.get("whatapp" , instance.whatapp)
        instance.twitter = validated_data.get("twitter", instance.twitter)
        instance.github = validated_data.get("github" , instance.github)
        instance.facebook = validated_data.get("facebook" , instance.facebook)
        instance.email = validated_data.get("email" , instance.email)

        #instance.user = user

        instance.save()

        return instance
