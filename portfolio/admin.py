from django.contrib import admin
from .models import Profile , Portfolio , About , Resume , School , Proficiency , PortfolioTrack , Goal
# Register your models here.

class display_profile(admin.ModelAdmin):
    list_display = ["user" , "display_pic" , "github" , "linkedin" , "whatapp" ,"facebook" , "email" , "phone_number" , "twitter"]


class display_track(admin.ModelAdmin):
    list_display = ["profile" , "name" , "slug" , "is_default" , "order"]


class display_about(admin.ModelAdmin):
    list_display =["track" , "skill" ,"years_of_experience" ,]


class display_portfolio(admin.ModelAdmin):
    list_display = ["track" , "category"]


class display_resume(admin.ModelAdmin):
    list_display = ["about" , "post" ,"start_year" ,"end_year"]


class display_school(admin.ModelAdmin):
    list_display = ["about" , "school_name" ,"start_year" ,"end_year"]


class display_proficiency(admin.ModelAdmin):
    list_display = ["about" , "skill_name" ,"skill_range"]


class display_goal(admin.ModelAdmin):
    list_display = ["profile" , "title" , "status" , "target_date" , "completed_at"]


admin.site.register(Profile , display_profile)
admin.site.register(PortfolioTrack , display_track)
admin.site.register(Portfolio, display_portfolio )
admin.site.register(About, display_about)
admin.site.register(Resume , display_resume)
admin.site.register(School , display_school)
admin.site.register(Proficiency , display_proficiency)
admin.site.register(Goal , display_goal)
