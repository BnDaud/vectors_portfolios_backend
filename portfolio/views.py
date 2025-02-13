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
    #queryset = Profile.objects.all()
    serializer_class = Profileserial

    def get_queryset(self):
        url_arg = self.request.query_params.get("username" ,None)
        print(url_arg)
        if url_arg:
            return Profile.objects.filter(user__username = url_arg)
        
        return Profile.objects.all()

class UpdateProfile(generics.RetrieveUpdateAPIView):
    """ this function helps to to Update new user profile"""
    name = "update_profiles"
    queryset = Profile.objects.all()
    serializer_class = Profileserial





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
        
            return Resume.objects.filter(about__about__user__username = url_arg)

        return Resume.objects.all()

class update_resume(generics.RetrieveUpdateAPIView):
    """
    this Class is responsible to update a single resume at a given time
     and this could only be called with its Id"""
    serializer_class = ResumeSerial
    queryset = Resume.objects.all()
    name = "update_resume"
   

    


class api_root(generics.GenericAPIView):

    '''
    this is the root api for all link to each model serializer 
    so as to fetch there data or post'''
    name = "api_root"

    def get(self , req , *arg , **kwarg):
        return Response( {
            ListCreateProfile.name : reverse("portfolio:"+ListCreateProfile.name , request=req),
            Userdetail.name : reverse("portfolio:"+Userdetail.name , request= req),
            List_portfolio.name : reverse("portfolio:"+List_portfolio.name , request=req),
            list_about.name :reverse("portfolio:"+list_about.name , request=req),
            list_resume.name : reverse("portfolio:"+list_resume.name , request=req),

        })