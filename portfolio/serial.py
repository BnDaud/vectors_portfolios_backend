from rest_framework.serializers import ModelSerializer  , HyperlinkedModelSerializer 
from rest_framework.serializers import SlugRelatedField , HyperlinkedRelatedField
from rest_framework.serializers import ChoiceField ,CharField ,SerializerMethodField
from django.contrib.auth.models import User
from .models import Profile , Portfolio , About , Resume


class Userserial(ModelSerializer):
    class Meta:
        model = User
        fields = ["username" , "first_name" , "last_name" , "password"]

    
    def create(self , validated_data):
        print(validated_data)
        pword = validated_data.pop("password")
        user =  User.objects.create(**validated_data)   
        user.set_password(pword)  
        user.save()
        return user
    
    def update(self , instance ,new_data):
        print(new_data)
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
    about = SerializerMethodField()
    resume = ResumeSerial(many = True)

    def get_about(self , obj):
        return obj.about.user.username
    
    class Meta:
        model = About
        fields = "__all__"



class PortfolioSerial(ModelSerializer):
    category = ChoiceField(choices=Portfolio.portfoiio_choice)
  
    username = SerializerMethodField(read_only = True)

    def get_username(self , obj):
        return obj.portfolio.user.username
        
    class Meta:
        model = Portfolio
        fields = ["id", "category" , "username"]




class Profileserial(ModelSerializer):
   
    user = Userserial()
    about = AboutSerial()
    portfolio = PortfolioSerial(many = True)
  
    class Meta:
        model = Profile
        fields = ["user" , "display_pic" , "about" , "portfolio" ]
        


