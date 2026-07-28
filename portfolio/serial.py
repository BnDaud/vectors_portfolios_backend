from rest_framework.serializers import ModelSerializer  , HyperlinkedModelSerializer
from rest_framework.serializers import SlugRelatedField , HyperlinkedRelatedField
from rest_framework.serializers import ChoiceField ,CharField ,SerializerMethodField
from rest_framework.serializers import IntegerField , BooleanField
from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils.text import slugify
from .models import Profile , Portfolio , About , Resume , School , Proficiency , PortfolioTrack , Goal


class Userserial(ModelSerializer):

    """ this serializer is responsible for the creation of new user
            And
    editing of the former ones


    """
    password = CharField(write_only = False , required = True)
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

    class Meta:
        model = About
        fields = "__all__"


class PortfolioSerial(ModelSerializer):
    category = ChoiceField(choices=Portfolio.portfolio_choice)

    display_username = SerializerMethodField(read_only = True)

    def get_display_username(self , obj):
        return obj.track.profile.user.username

    class Meta:
        model = Portfolio
        fields = ["id", "category" , "display_username" , "track" , "name" , "thumbnail" , "project_link"]


class PortfolioTrackSerial(ModelSerializer):
    about = AboutSerial(read_only = True)
    items = PortfolioSerial(many = True , read_only = True)
    username = CharField(write_only = True , required = False)
    copy_from = IntegerField(write_only = True , required = False , allow_null = True)
    copy_portfolio_items = BooleanField(write_only = True , required = False , default = False)

    class Meta:
        model = PortfolioTrack
        fields = ["id" , "name" , "slug" , "is_default" , "order" , "about" , "items" ,
                  "username" , "copy_from" , "copy_portfolio_items"]
        extra_kwargs = {"slug": {"required": False}}

    def create(self , validated_data):
        username = validated_data.pop("username" , None)
        copy_from_id = validated_data.pop("copy_from" , None)
        copy_items = validated_data.pop("copy_portfolio_items" , False)

        if not username:
            raise serializers.ValidationError({"username": "This field is required."})

        profile = Profile.objects.get(user__username = username)
        validated_data.setdefault("slug" , slugify(validated_data["name"]))
        track = PortfolioTrack.objects.create(profile = profile , **validated_data)

        if copy_from_id:
            source = PortfolioTrack.objects.get(pk = copy_from_id , profile = profile)
            source_about = source.about
            new_about = About.objects.create(
                track = track,
                skill = source_about.skill,
                experience_since = source_about.experience_since,
                description = source_about.description,
                image_link = source_about.image_link,
            )
            for r in source_about.resume.all():
                Resume.objects.create(about = new_about , post = r.post , start_year = r.start_year ,
                                       end_year = r.end_year , company_name = r.company_name ,
                                       certificate_link = r.certificate_link)
            for s in source_about.school.all():
                School.objects.create(about = new_about , start_year = s.start_year , end_year = s.end_year ,
                                       school_name = s.school_name , certificate_link = s.certificate_link)
            for p in source_about.proficiency.all():
                Proficiency.objects.create(about = new_about , skill_name = p.skill_name ,
                                            skill_range = p.skill_range , certificate_link = p.certificate_link)
            if copy_items:
                for item in source.items.all():
                    Portfolio.objects.create(track = track , category = item.category , name = item.name ,
                                              thumbnail = item.thumbnail , project_link = item.project_link)
        else:
            About.objects.create(track = track , skill = "" , description = "" , image_link = "")

        return track


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
        fields = ["id" , "user" , "display_pic" ,"github" , "linkedin" , "whatapp" ,"facebook" ,"email","twitter","phone_number","tracks" ]

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
