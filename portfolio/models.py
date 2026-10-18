from datetime import date
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


# Contact/picture fields every track carries for itself, so each portfolio
# can show its own dp and links. Profile keeps the same fields as the
# owner-level default a brand new track starts from.
TRACK_CONTACT_FIELDS = [
    "display_pic" , "github" , "linkedin" , "whatapp" , "facebook" ,
    "twitter" , "email" , "phone_number" ,
]


class PortfolioTrack(models.Model):
    profile = models.ForeignKey(Profile , on_delete=models.CASCADE , related_name="tracks")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110)
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    display_pic = models.URLField(default="" , blank=False)
    linkedin = models.URLField(default="" , blank=True)
    github = models.URLField(default="" , blank=True)
    whatapp = models.URLField(default="" , blank=True)
    facebook = models.URLField(default="" , blank=True)
    twitter = models.URLField(default="" , blank=True)
    email = models.CharField(default="" , blank=True , max_length=50)
    phone_number = models.CharField(default="" , blank=True , max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "slug")
        ordering = ["order", "id"]
        verbose_name_plural = "Portfolio Tracks"

    def __str__(self):
        return f"{self.profile.user.username} - {self.name}"


def current_year():
    return date.today().year


# Cap for the optional short description on resume/education/skill entries,
# kept small so the resume board on the portfolio page can't be overrun.
ENTRY_DESCRIPTION_MAX = 240


class About(models.Model):
    track = models.OneToOneField(PortfolioTrack , on_delete=models.CASCADE , related_name="about" )
    skill = models.CharField(blank=False , max_length=100)
    # Superseded by experience_base_years/experience_base_year below and no
    # longer read anywhere; kept so no data is dropped.
    experience_since = models.DateField(null=True , blank=True)
    # Years of experience as entered, and the calendar year they were entered
    # in. years_of_experience adds one for every January 1 since then, so the
    # number rolls over by itself with no scheduled job, per track.
    experience_base_years = models.PositiveSmallIntegerField(default=0 , validators=[MaxValueValidator(80)])
    experience_base_year = models.PositiveSmallIntegerField(default=current_year , editable=False)
    #education = models.CharField(max_length=200)# i will drop this column later
    description = models.TextField(max_length=1000 , default="")
    image_link = models.URLField(default="" , blank=True)

    @property
    def years_of_experience(self):
        return self.experience_base_years + max(0 , current_year() - self.experience_base_year)

    def save(self , *args , **kwargs):
        # Whenever the number is changed (API or admin), re-anchor it to the
        # current year so the stored value is "as of now".
        if self.pk:
            previous = type(self).objects.filter(pk = self.pk).values_list("experience_base_years" , flat = True).first()
            if previous is not None and previous != self.experience_base_years:
                self.experience_base_year = current_year()
        super().save(*args , **kwargs)

    def __str__(self):
        return "About " + self.track.profile.user.username


class Resume(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="resume")
    post = models.CharField(max_length=100)
    start_year = models.DateField(auto_now=False , auto_now_add=False)
    end_year = models.DateField(auto_now=False , auto_now_add=False)
    company_name = models.CharField(max_length=50 , default="")
    certificate_link = models.URLField(blank=True , default="")
    description = models.CharField(max_length=ENTRY_DESCRIPTION_MAX , blank=True , default="")

class School(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="school")
    start_year = models.DateField(auto_now=False , auto_now_add=False)
    end_year = models.DateField(auto_now=False , auto_now_add=False)
    school_name = models.CharField(max_length=50 , default="")
    certificate_link = models.URLField(blank=True , default="")
    description = models.CharField(max_length=ENTRY_DESCRIPTION_MAX , blank=True , default="")

    class Meta:
        verbose_name_plural = "Schools"

class Proficiency(models.Model):
    about = models.ForeignKey(About , on_delete=models.CASCADE , related_name="proficiency")
    skill_name = models.CharField(max_length=50 , default="")
    skill_range = models.SmallIntegerField(validators=[ MinValueValidator(0) , MaxValueValidator(100)] , default=10)
    certificate_link = models.URLField(blank=True , default="")
    description = models.CharField(max_length=ENTRY_DESCRIPTION_MAX , blank=True , default="")

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
        CAD = "CAD", "CAD"

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


class Visitor(models.Model):
    """
    One anonymous browser, known only by a random id the browser made up for
    itself. No IP address, user agent or any other personal data is stored.
    visit_count counts visits (a return after SESSION_GAP of inactivity starts
    a new one), not page views - so a returning person is one row whose count
    goes up, never a second visitor.
    """
    visitor_id = models.UUIDField(unique=True , editable=False)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField()
    visit_count = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"Visitor #{self.pk} ({self.visit_count} visits)"


class PageView(models.Model):
    """A portfolio (track=None means the landing page) a visitor opened during one of their visits."""
    visitor = models.ForeignKey(Visitor , on_delete=models.CASCADE , related_name="views")
    track = models.ForeignKey(PortfolioTrack , null=True , blank=True , on_delete=models.CASCADE , related_name="views")
    visit_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # one row per portfolio per visit; NULL track (landing) needs its own rule
            models.UniqueConstraint(fields=["visitor" , "visit_number" , "track"] , name="one_view_per_track_per_visit"),
            models.UniqueConstraint(fields=["visitor" , "visit_number"] , condition=models.Q(track__isnull=True) ,
                                    name="one_landing_view_per_visit"),
        ]
