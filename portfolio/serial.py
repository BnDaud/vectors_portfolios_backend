from rest_framework.serializers import ModelSerializer  , HyperlinkedModelSerializer 
from rest_framework.serializers import SlugRelatedField , HyperlinkedRelatedField
from rest_framework.serializers import ChoiceField ,CharField ,SerializerMethodField
from django.contrib.auth.models import User
from .models import Profile , Portfolio , About , Resume


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





class ResumeSerial(ModelSerializer):
    _about = SerializerMethodField()

    def get__about(self , obj):
        return obj.about.about.user.username
    
    class Meta :
        model = Resume
        fields = "__all__"



class AboutSerial(ModelSerializer):
    about = CharField(required = True)
    resume = ResumeSerial(many = True , read_only = True)

    def get_about(self , obj):
        return obj.about.user.username
    
    class Meta:
        model = About
        fields = "__all__"

    def create(self, validated_data):
        profile = validated_data.pop("about")
        
        user = Profile.objects.get(user__username =  profile)
        about_  = About.objects.create(about = user  , **validated_data)
        return about_
    
    def update(self , instance , validated_data):
        profile = validated_data.pop("about" , instance.about)
        user = Profile.objects.get(user__username = profile)
        instance.about = user
        instance.skill = validated_data.get("skill" , instance.skill)
        instance.years_of_experience  = validated_data.get("years_of_experience" ,instance.years_of_experience)
        instance.education = validated_data.get("education" , instance.education)
        instance.save()
        return instance
    
   


class PortfolioSerial(ModelSerializer):
    category = ChoiceField(choices=Portfolio.portfoiio_choice)
  
    display_username = SerializerMethodField(read_only = True)
    username = CharField(required  = True  , write_only = True)

    def get_display_username(self , obj):
        return obj.portfolio.user.username
        
    class Meta:
        model = Portfolio
        fields = ["id", "category" , "display_username" , "username"]
    
    def create(self, validated_data):
        
        username = validated_data.pop("username")
        profile = Profile.objects.get(user__username = username)
        model = Portfolio.objects.create(portfolio = profile , **validated_data )
        
        return model

   



class Profileserial(ModelSerializer):
   
    user = Userserial()
    about = AboutSerial(read_only = True)
    portfolio = PortfolioSerial(many = True , read_only = True)
  
    class Meta:
        model = Profile
        fields = ["user" , "display_pic" , "about" , "portfolio" ]

    def create(self , validated_data):
        img = validated_data.pop("display_pic")
        password = validated_data["user"].pop("password")

        user = User.objects.create(**validated_data["user"])
        user.set_password(password)
        user.save()
        profile = Profile.objects.create(user = user , display_pic = img)
    
        return profile
    
    def update(self, instance, validated_data):
      
        display_pic = validated_data.pop("display_pic" , instance.display_pic)
       
        new_user_detail = validated_data.pop("user"  , instance.user)
        
        password = new_user_detail.pop("password" , None) #None means the password remains the same
       
        new_user_detail["username"] = instance.user.username
        
        user =  User.objects.get(**new_user_detail)
        
        user.set_password(password)
        
        user.save()
        
        instance.display_pic = display_pic
        
        instance.user = user

        return instance

        


