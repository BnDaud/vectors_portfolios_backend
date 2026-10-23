from django.shortcuts import render
from django.utils import timezone
from rest_framework.reverse import reverse
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from .models import Profile , Portfolio , About ,Resume ,School ,Proficiency , PortfolioTrack , Goal
from rest_framework.response import Response
from . serial import Profileserial ,Userserial , PortfolioSerial ,AboutSerial ,ResumeSerial , SchoolSerial ,ProficiencySerial , PortfolioTrackSerial , GoalSerial , delete_if_in_no_portfolio
from django.contrib.auth.models import User
from rest_framework.permissions import BasePermission
from .permissions import IsOwnerOrReadOnly , SiteOwnerOnlyWrites , is_site_owner , owner_of , require_owner


class SiteOwnerOnly(BasePermission):
    """Creating, listing and editing user accounts by hand: the site owner only (sign-up has its own endpoint)."""

    def has_permission(self , request , view):
        return is_site_owner(request.user)

# Create your views here.

class ParentOwnedMixin:
    """
    For entries hanging off a parent (an About off a portfolio, a job off an About,
    a project off portfolios): whatever parent a create or an edit points at must
    be the signed-in user's own - so nothing can be added to, or moved into,
    someone else's portfolio.
    """
    parent_fields = ()

    def _check_parents(self , serializer):
        for field in self.parent_fields:
            if field not in serializer.validated_data:
                continue
            value = serializer.validated_data[field]
            for parent in (value if isinstance(value , (list , tuple)) else [value]):
                require_owner(self.request , owner_of(parent))

    def perform_create(self , serializer):
        self._check_parents(serializer)
        serializer.save()

    def perform_update(self , serializer):
        self._check_parents(serializer)
        serializer.save()


class Userdetail(generics.ListCreateAPIView):

    ''' this function is used to create new user '''
    name = "create_user"
    queryset = User.objects.all()
    serializer_class = Userserial
    permission_classes = [SiteOwnerOnly]


class updateUserdetail(generics.RetrieveUpdateAPIView):
    """ this function help in editing existing user details"""
    name = "update_user"
    queryset = User.objects.all()
    serializer_class = Userserial
    permission_classes = [SiteOwnerOnly]


class ListCreateProfile(generics.ListCreateAPIView):
    """ this function helps to to create and list new user profile"""
    name = "all_profiles"
    #queryset = Profile.objects.all()
    serializer_class = Profileserial
    permission_classes = [SiteOwnerOnlyWrites]   # new accounts come from auth/signup

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" ,None)

        if url_arg:
            return Profile.objects.filter(user__username = url_arg)

        return Profile.objects.all()

class UpdateProfile(generics.RetrieveUpdateDestroyAPIView):
    """ this function helps to to Update new user profile"""
    name = "update_profiles"
    queryset = Profile.objects.all()
    serializer_class = Profileserial
    permission_classes = [IsOwnerOrReadOnly]


class list_tracks(generics.ListCreateAPIView):
    """ This class lists/creates PortfolioTracks, filterable by ?username= """
    name = "List_tracks"
    serializer_class = PortfolioTrackSerial

    def perform_create(self , serializer):
        if serializer.validated_data.get("username") != self.request.user.username:
            require_owner(self.request , None)
        serializer.save()

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            return PortfolioTrack.objects.filter(profile__user__username = url_arg)

        return PortfolioTrack.objects.all()


class update_track(generics.RetrieveUpdateDestroyAPIView):
    """ this class is responsible to update or delete a single track at a given time """
    serializer_class = PortfolioTrackSerial
    queryset = PortfolioTrack.objects.all()
    name = "update_track"
    permission_classes = [IsOwnerOrReadOnly]


class list_about (ParentOwnedMixin , generics.ListCreateAPIView):
    parent_fields = ("track",)

    """ this class is responsible for creating and listing user details"""
    name = "About_User"
    queryset = About.objects.all()
    serializer_class = AboutSerial


class UpdateAbout(ParentOwnedMixin , generics.RetrieveUpdateDestroyAPIView):
    parent_fields = ("track",)
    """
    This class is to update about any user and can be access with it Id"""
    name = "update_about"
    permission_classes = [IsOwnerOrReadOnly]
    queryset = About.objects.all()
    serializer_class = AboutSerial


class List_portfolio(ParentOwnedMixin , generics.ListCreateAPIView):
    parent_fields = ("tracks",)
    """ This class returns all the available portfolio in the data base"""
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name = "List_Portfolio"


class updateportfolio(generics.RetrieveUpdateDestroyAPIView):
    """ this class is responsible to update any portfolio at a given time
     and can be access with its Id """
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name  = "update_portfolio"
    permission_classes = [IsOwnerOrReadOnly]

    def update(self , request , *args , **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance , data = request.data , partial = kwargs.pop("partial" , False))
        serializer.is_valid(raise_exception = True)
        for track in serializer.validated_data.get("tracks" , []):     # can only share into your own portfolios
            require_owner(request , owner_of(track))
        project = serializer.save()
        if project.pk is None:      # it was unticked in every portfolio, so it was deleted
            return Response(status = 204)
        return Response(serializer.data)

    def destroy(self , request , *args , **kwargs):
        """
        DELETE ?from=<portfolio id>[&also=<id>,<id>... | all]
        Takes the project out of that portfolio and nothing else - unless more are named in
        `also` (or "all" of them). Once no portfolio shows it any more, it is deleted for good.
        """
        project = self.get_object()
        shown_in = set(project.tracks.values_list("id" , flat = True))
        source = request.query_params.get("from")
        if source is None:
            if len(shown_in) > 1:
                raise ValidationError({"from": "This project is shown in several portfolios - say which one to delete it from."})
            remove = set(shown_in)
        else:
            also = request.query_params.get("also" , "")
            try:
                remove = {int(source)} | (set(shown_in) if also == "all" else {int(i) for i in also.split(",") if i})
            except ValueError:
                raise ValidationError({"also": "Use portfolio ids separated by commas, or \"all\"."})
            unknown = remove - shown_in
            if unknown:
                raise ValidationError({"from": f"This project is not shown in portfolio {sorted(unknown)[0]}."})
        project.tracks.remove(*remove)
        delete_if_in_no_portfolio(project)
        return Response(status = 204)


class list_resume(ParentOwnedMixin , generics.ListCreateAPIView):
    parent_fields = ("about",)

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

class update_resume(ParentOwnedMixin , generics.RetrieveUpdateDestroyAPIView):
    parent_fields = ("about",)
    """
    this Class is responsible to update a single resume at a given time
     and this could only be called with its Id"""
    serializer_class = ResumeSerial
    queryset = Resume.objects.all()
    name = "update_resume"
    permission_classes = [IsOwnerOrReadOnly]

class list_school(ParentOwnedMixin , generics.ListCreateAPIView):
    parent_fields = ("about",)

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

class update_school(ParentOwnedMixin , generics.RetrieveUpdateDestroyAPIView):
    parent_fields = ("about",)
    """
    this Class is responsible to update a single school at a given time
     and this could only be called with its Id"""
    serializer_class = SchoolSerial
    queryset = School.objects.all()
    name = "list_school"
    permission_classes = [IsOwnerOrReadOnly]

class list_proficiency(ParentOwnedMixin , generics.ListCreateAPIView):
    parent_fields = ("about",)

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

class update_proficiency(ParentOwnedMixin , generics.RetrieveUpdateDestroyAPIView):
    parent_fields = ("about",)
    """
    this Class is responsible to update a single school at a given time
     and this could only be called with its Id"""
    serializer_class = ProficiencySerial
    queryset = Proficiency.objects.all()
    name = "update_proficiency"
    permission_classes = [IsOwnerOrReadOnly]


class list_goals(generics.ListCreateAPIView):
    """ Lists/creates Goals, filterable by ?username= """
    name = "List_goals"
    serializer_class = GoalSerial

    def perform_create(self , serializer):
        if serializer.validated_data.get("username") != self.request.user.username:
            require_owner(self.request , None)
        serializer.save()

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            return Goal.objects.filter(profile__user__username = url_arg)

        return Goal.objects.all()


class update_goal(generics.RetrieveUpdateDestroyAPIView):
    """ this class is responsible to update or delete a single goal at a given time """
    serializer_class = GoalSerial
    queryset = Goal.objects.all()
    name = "update_goal"
    permission_classes = [IsOwnerOrReadOnly]


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
    permission_classes = [IsOwnerOrReadOnly]
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
