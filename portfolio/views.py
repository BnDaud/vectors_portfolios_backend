from django.shortcuts import render
from django.utils import timezone
from rest_framework.reverse import reverse
from rest_framework import generics
from .models import Profile , Portfolio , About ,Resume ,School ,Proficiency , PortfolioTrack , Goal
from rest_framework.response import Response
from . serial import Profileserial ,Userserial , PortfolioSerial ,AboutSerial ,ResumeSerial , SchoolSerial ,ProficiencySerial , PortfolioTrackSerial , GoalSerial
from django.contrib.auth.models import User

# Create your views here.

class Userdetail(generics.ListCreateAPIView):

    ''' this function is used to create new user '''
    name = "create_user"
    queryset = User.objects.all()
    serializer_class = Userserial


class updateUserdetail(generics.RetrieveUpdateAPIView):
    """ this function help in editing existing user details"""
    name = "update_user"
    queryset = User.objects.all()
    serializer_class = Userserial


class ListCreateProfile(generics.ListCreateAPIView):
    """ this function helps to to create and list new user profile"""
    name = "all_profiles"
    #queryset = Profile.objects.all()
    serializer_class = Profileserial

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" ,None)

        if url_arg:
            return Profile.objects.filter(user__username = url_arg)

        return Profile.objects.all()

class UpdateProfile(generics.RetrieveUpdateAPIView):
    """ this function helps to to Update new user profile"""
    name = "update_profiles"
    queryset = Profile.objects.all()
    serializer_class = Profileserial


class list_tracks(generics.ListCreateAPIView):
    """ This class lists/creates PortfolioTracks, filterable by ?username= """
    name = "List_tracks"
    serializer_class = PortfolioTrackSerial

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            return PortfolioTrack.objects.filter(profile__user__username = url_arg)

        return PortfolioTrack.objects.all()


class update_track(generics.RetrieveUpdateAPIView):
    """ this class is responsible to update a single track at a given time """
    serializer_class = PortfolioTrackSerial
    queryset = PortfolioTrack.objects.all()
    name = "update_track"


class list_about (generics.ListCreateAPIView):

    """ this class is responsible for creating and listing user details"""
    name = "About_User"
    queryset = About.objects.all()
    serializer_class = AboutSerial


class UpdateAbout(generics.RetrieveUpdateAPIView):
    """
    This class is to update about any user and can be access with it Id"""
    name = "update_about"
    queryset = About.objects.all()
    serializer_class = AboutSerial


class List_portfolio(generics.ListCreateAPIView):
    """ This class returns all the available portfolio in the data base"""
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name = "List_Portfolio"


class updateportfolio(generics.RetrieveUpdateAPIView):
    """ this class is responsible to update any portfolio at a given time
     and can be access with its Id """
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name  = "update_portfolio"


class list_resume(generics.ListCreateAPIView):

    """ This Class List all the resume availble
    if username arg is not passed with the url
    it will return all the available resume but if passed
    it will return only the resume of the username"""
    serializer_class = ResumeSerial
    #queryset = Resume.objects.all()
    name = "List_resume"

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:

            return Resume.objects.filter(about__track__profile__user__username = url_arg)

        return Resume.objects.all()

class update_resume(generics.RetrieveUpdateAPIView):
    """
    this Class is responsible to update a single resume at a given time
     and this could only be called with its Id"""
    serializer_class = ResumeSerial
    queryset = Resume.objects.all()
    name = "update_resume"

class list_school(generics.ListCreateAPIView):

    """ This Class List all the school availble
    if username arg is not passed with the url
    it will return all the available school but if passed
    it will return only the school of the username"""
    serializer_class = SchoolSerial

    name = "List_school"

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:

            return School.objects.filter(about__track__profile__user__username = url_arg)

        return School.objects.all()

class update_school(generics.RetrieveUpdateAPIView):
    """
    this Class is responsible to update a single school at a given time
     and this could only be called with its Id"""
    serializer_class = SchoolSerial
    queryset = School.objects.all()
    name = "list_school"

class list_proficiency(generics.ListCreateAPIView):

    """ This Class List all the proficiency available
    if username arg is not passed with the url
    it will return all the available proficiency but if passed
    it will return only the proficiency of the username"""
    serializer_class = ProficiencySerial

    name = "List_proficiency"

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:

            return Proficiency.objects.filter(about__track__profile__user__username = url_arg)

        return Proficiency.objects.all()

class update_proficiency(generics.RetrieveUpdateAPIView):
    """
    this Class is responsible to update a single school at a given time
     and this could only be called with its Id"""
    serializer_class = ProficiencySerial
    queryset = Proficiency.objects.all()
    name = "update_proficiency"


class list_goals(generics.ListCreateAPIView):
    """ Lists/creates Goals, filterable by ?username= """
    name = "List_goals"
    serializer_class = GoalSerial

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            return Goal.objects.filter(profile__user__username = url_arg)

        return Goal.objects.all()


class update_goal(generics.RetrieveUpdateAPIView):
    """ this class is responsible to update a single goal at a given time """
    serializer_class = GoalSerial
    queryset = Goal.objects.all()
    name = "update_goal"


ENTRY_TYPE_MODELS = {
    "education": School,
    "experience": Resume,
    "skill": Proficiency,
}


class complete_goal(generics.GenericAPIView):
    """
    Marks a goal completed and creates the chosen entry type (education/
    experience/skill) under each selected track's About.

    PATCH body: {entry_type, entry_data: {...}, track_ids: [...]}
    """
    name = "complete_goal"
    queryset = Goal.objects.all()
    serializer_class = GoalSerial

    def patch(self , request , pk , *args , **kwargs):
        goal = self.get_object()

        entry_type = request.data.get("entry_type")
        entry_data = request.data.get("entry_data" , {})
        track_ids = request.data.get("track_ids" , [])
        new_track_data = request.data.get("new_track")

        model_cls = ENTRY_TYPE_MODELS.get(entry_type)
        if not model_cls:
            return Response(
                {"entry_type": "must be one of: " + ", ".join(ENTRY_TYPE_MODELS.keys())},
                status = 400,
            )

        tracks = list(PortfolioTrack.objects.filter(id__in = track_ids , profile = goal.profile))

        new_track = None
        if new_track_data:
            track_serial = PortfolioTrackSerial(data = {
                **new_track_data,
                "username": goal.profile.user.username,
            })
            track_serial.is_valid(raise_exception = True)
            new_track = track_serial.save()
            tracks.append(new_track)

        if not tracks:
            return Response(
                {"track_ids": "provide at least one existing track id or a new_track to create"},
                status = 400,
            )

        created_ids = []
        for track in tracks:
            try:
                entry = model_cls.objects.create(about = track.about , **entry_data)
            except TypeError as exc:
                return Response({"entry_data": str(exc)} , status = 400)
            created_ids.append(entry.id)

        goal.status = Goal.GoalStatus.COMPLETED
        goal.completed_at = timezone.now()
        goal.save(update_fields = ["status" , "completed_at"])

        return Response({
            "goal": GoalSerial(goal).data,
            "created_ids": created_ids,
            "new_track": PortfolioTrackSerial(new_track).data if new_track else None,
        })


class api_root(generics.GenericAPIView):

    '''
    this is the root api for all link to each model serializer
    so as to fetch there data or post'''
    name = "api_root"

    def get(self , req , *arg , **kwarg):
        return Response( {
            ListCreateProfile.name : reverse("portfolio:"+ListCreateProfile.name , request=req),
            Userdetail.name : reverse("portfolio:"+Userdetail.name , request= req),
            list_tracks.name : reverse("portfolio:"+list_tracks.name , request=req),
            List_portfolio.name : reverse("portfolio:"+List_portfolio.name , request=req),
            list_about.name :reverse("portfolio:"+list_about.name , request=req),
            list_school.name : reverse("portfolio:"+list_school.name , request=req),
            list_proficiency.name : reverse("portfolio:"+list_proficiency.name , request=req),
            list_resume.name : reverse("portfolio:"+list_resume.name , request=req),
            list_goals.name : reverse("portfolio:"+list_goals.name , request=req),

        })
