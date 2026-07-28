from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.


class Profile(models.Model):
    user = models.OneToOneField(User , on_delete=models.CASCADE)
    linkedin = models.URLField(default="" , blank=True)
    github = models.URLField(default="" , blank=True)
    whatapp = models.URLField(default="" , blank=True)
    facebook = models.URLField(default="" , blank=True)
    twitter = models.URLField(default="" , blank=True)
    email = models.CharField(default="" , blank=True , max_length=50)
    phone_number = models.CharField(default="" , blank=True , max_length=50)


    display_pic = models.URLField(default="" , blank=False)

    def __str__(self):
        return self.user.username


class PortfolioTrack(models.Model):
    profile = models.ForeignKey(Profile , on_delete=models.CASCADE , related_name="tracks")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110)
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "slug")
        ordering = ["order", "id"]
        verbose_name_plural = "Portfolio Tracks"

    def __str__(self):
        return f"{self.profile.user.username} - {self.name}"


class About(models.Model):
    track = models.OneToOneField(PortfolioTrack , on_delete=models.CASCADE , related_name="about" )
    skill = models.CharField(blank=False , max_length=100)
    years_of_experience = models.IntegerField()
    #education = models.CharField(max_length=200)# i will drop this column later
    description = models.TextField(max_length=500 , default="")
    image_link = models.URLField(default="" , blank=True)



    def __str__(self):
        return "About " + self.track.profile.user.username


class Resume(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="resume")
    post = models.CharField(max_length=100)
    start_year = models.DateField(auto_now=False , auto_now_add=False)
    end_year = models.DateField(auto_now=False , auto_now_add=False)
    company_name = models.CharField(max_length=50 , default="")
    certificate_link = models.URLField(blank=True , default="")

class School(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="school")
    start_year = models.DateField(auto_now=False , auto_now_add=False)
    end_year = models.DateField(auto_now=False , auto_now_add=False)
    school_name = models.CharField(max_length=50 , default="")
    certificate_link = models.URLField(blank=True , default="")

    class Meta:
        verbose_name_plural = "Schools"

class Proficiency(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="proficiency")
    skill_name = models.CharField(max_length=50 , default="")
    skill_range = models.SmallIntegerField(validators=[ MinValueValidator(0) , MaxValueValidator(100)] , default=10)
    certificate_link = models.URLField(blank=True , default="")

    class Meta:
        verbose_name_plural = "Proficiency"
    

class Portfolio(models.Model):
    

    class portfolio_choice(models.TextChoices):
        WebDev = "WebDev", "WebDev"
        DataScience = "DataScience", "DataScience"
        AI = "AI", "AI"
        MachineLearning = "MachineLearning", "MachineLearning"
        ComputerVision = "ComputerVision", "ComputerVision"
        NLP = "NLP", "NLP"
        Cybersecurity = "Cybersecurity", "Cybersecurity"
        UIUX = "UIUX", "UIUX"
        ProductManagement = "ProductManagement", "ProductManagement"
        CloudComputing = "CloudComputing", "CloudComputing"
        Robotics = "Robotics", "Robotics"
        IoT = "IoT", "IoT"
        BigData = "BigData", "BigData"
        Blockchain = "Blockchain", "Blockchain"
        MobileDev = "MobileDev", "MobileDev"
        QA = "QA", "QA"
        SoftwareEng = "SoftwareEng", "SoftwareEng"
        DataAnalysis = "DataAnalysis", "DataAnalysis"
        DatabaseAdmin = "DatabaseAdmin", "DatabaseAdmin"
        NetworkEng = "NetworkEng", "NetworkEng"

        Marketing = "Marketing", "Marketing"
        DigitalMarketing = "DigitalMarketing", "DigitalMarketing"
        SocialMedia = "SocialMedia", "SocialMedia"
        ContentMarketing = "ContentMarketing", "ContentMarketing"
        Sales = "Sales", "Sales"
        PublicRelations = "PublicRelations", "PublicRelations"
        Advertising = "Advertising", "Advertising"
        BrandManagement = "BrandManagement", "BrandManagement"
        ProductMarketing = "ProductMarketing", "ProductMarketing"
        AgriMarketing = "AgriMarketing", "AgriMarketing"

        HumanResources = "HumanResources", "HumanResources"
        Finance = "Finance", "Finance"
        Accounting = "Accounting", "Accounting"
        Banking = "Banking", "Banking"
        InvestmentBanking = "InvestmentBanking", "InvestmentBanking"
        RealEstate = "RealEstate", "RealEstate"
        Legal = "Legal", "Legal"
        Education = "Education", "Education"
        Teaching = "Teaching", "Teaching"
        Research = "Research", "Research"

        Catering = "Catering", "Catering"
        Hospitality = "Hospitality", "Hospitality"
        EventManagement = "EventManagement", "EventManagement"
        Fashion = "Fashion", "Fashion"
        Architecture = "Architecture", "Architecture"
        InteriorDesign = "InteriorDesign", "InteriorDesign"
        Medical = "Medical", "Medical"
        Pharmacy = "Pharmacy", "Pharmacy"
        Sports = "Sports", "Sports"
        Entrepreneurship = "Entrepreneurship", "Entrepreneurship"
        Agriculture = "Agriculture", "Agriculture"
        Others = "Others", "Others"



    track = models.ForeignKey(PortfolioTrack , on_delete=models.CASCADE , related_name="items")
    category = models.CharField(choices = portfolio_choice , max_length= 50)
    name = models.CharField(blank=False , max_length=50 , default="")
    thumbnail = models.URLField(blank=False , default= "")
    project_link = models.URLField(blank=False , default="")



    def __str__(self):
        return self.track.profile.user.username + " Portfolio"


class Goal(models.Model):

    class GoalStatus(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    profile = models.ForeignKey(Profile , on_delete=models.CASCADE , related_name="goals")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True , default="")
    target_date = models.DateField(null=True , blank=True)
    status = models.CharField(max_length=20 , choices=GoalStatus , default=GoalStatus.IN_PROGRESS)
    completed_at = models.DateTimeField(null=True , blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.user.username} - {self.title}"







