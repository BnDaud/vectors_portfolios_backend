from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class Profile(models.Model):
    user = models.OneToOneField(User , on_delete=models.CASCADE)
    display_pic = models.ImageField(blank=False , upload_to= "images")

    def __str__(self):
        return self.user.username
     


class About(models.Model):
    about = models.OneToOneField(Profile , on_delete=models.CASCADE , related_name="about" )
    skill = models.CharField(blank=False , max_length=100)
    years_of_experience = models.IntegerField()
    education = models.CharField(max_length=200)
    description = models.TextField(max_length=500 , default="")
    image_link = models.URLField(default="" , blank=True) 



    def __str__(self):
        return "About " + self.about.user.username


class Resume(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="resume")
    post = models.CharField(max_length=100)
    start_year = models.DateField(auto_now=False , auto_now_add=False)
    end_year = models.DateField(auto_now=False , auto_now_add=False)
    company_name = models.CharField(max_length=50 , default="")
    

class Portfolio(models.Model):
    class portfoiio_choice(models.TextChoices):
        Frontend = "FE" , "Front End"
        Backend = "BE" , "Back End"
        data_analysis = "DA" ,"Data Analyst"
        Robotics = "RB","Robotics"

    portfolio = models.ForeignKey(Profile , on_delete=models.CASCADE , related_name="portfolio")
    category = models.CharField(choices = portfoiio_choice , max_length= 50)


    def __str__(self):
        return self.portfolio.user.username + " Portfolio"
