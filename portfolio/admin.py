from django.contrib import admin
from .models import Profile , Portfolio , About , Resume
# Register your models here.

class display_profile(admin.ModelAdmin):
    list_display = ["user" , "display_pic" , "github" , "linkedin" , "whatapp" ,"facebook" , "email" , "phone_number"]

class display_about(admin.ModelAdmin):
    list_display =["about" , "skill" ,"years_of_experience" ,]


class display_portfolio(admin.ModelAdmin):
    list_display = ["portfolio" , "category"]


class display_resume(admin.ModelAdmin):
    list_display = ["about" , "post" ,"start_year" ,"end_year"]

    
admin.site.register(Profile , display_profile)
admin.site.register(Portfolio, display_portfolio )
admin.site.register(About, display_about)
admin.site.register(Resume , display_resume)