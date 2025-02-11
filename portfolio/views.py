from django.shortcuts import render
from rest_framework.reverse import reverse
from rest_framework import generics
from .models import Profile , Portfolio , About ,Resume
from rest_framework.response import Response
from . serial import Profileserial ,Userserial , PortfolioSerial ,AboutSerial ,ResumeSerial
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
    queryset = Profile.objects.all()
    serializer_class = Profileserial


class list_about (generics.ListCreateAPIView):

    """ this class is responsible for creating and listing user details"""
    name = "About_User"
    queryset = About.objects.all()
    serializer_class = AboutSerial


class UpdateAbout(generics.RetrieveUpdateAPIView):
    name = "update_about"
    queryset = About.objects.all()
    serializer_class = AboutSerial


class List_portfolio(generics.ListCreateAPIView):
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name = "List_Portfolio"


class updateportfolio(generics.RetrieveUpdateAPIView):
    serializer_class = PortfolioSerial
    queryset = Portfolio.objects.all()
    name  = "update_portfolio"


class list_resume(generics.ListCreateAPIView):
    serializer_class = ResumeSerial
    #queryset = Resume.objects.all()
    name = "List_resume"
    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            print(url_arg)
            print("i got here")
            print(Resume.objects.all())
            print(Resume.objects.filter(about__about__user__username = url_arg)
)

            return Resume.objects.filter(about__about__user__username = url_arg)

        return Resume.objects.none()

class update_resume(generics.RetrieveUpdateAPIView):
    serializer_class = ResumeSerial
    queryset = Resume.objects.all()
    name = "update_resume"
   

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" , None)

        if url_arg:
            print(url_arg)
            print("i got here")
            print(Resume.objects.all())
            print(Resume.objects.filter(about__about__user__username = url_arg)
)

            return Resume.objects.filter(about__about__user__username = url_arg)

        return Resume.objects.none()


class api_root(generics.GenericAPIView):
    name = "api_root"

    def get(self , req , *arg , **kwarg):
        return Response( {
            ListCreateProfile.name : reverse("portfolio:"+ListCreateProfile.name , request=req),
            Userdetail.name : reverse("portfolio:"+Userdetail.name , request= req),
            List_portfolio.name : reverse("portfolio:"+List_portfolio.name , request=req),
            list_about.name :reverse("portfolio:"+list_about.name , request=req),
            list_resume.name : reverse("portfolio:"+list_resume.name , request=req),

        })