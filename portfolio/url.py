from django.urls import path, re_path
from .views import ListCreateProfile , api_root , list_about , Userdetail ,updateUserdetail
from .views import List_portfolio ,list_about ,UpdateAbout , updateportfolio , list_resume , update_resume

app_name = "portfolio"


urlpatterns = [
    path("" , view=api_root.as_view() , name = api_root.name),
    path("edit_user/<int:pk>" , view = updateUserdetail.as_view() , name= updateUserdetail.name),
     path("createuser" , view = Userdetail.as_view() , name= Userdetail.name),
    path("about/" , view= list_about.as_view() , name = list_about.name),
    path("profiles/" , view=ListCreateProfile.as_view() , name=ListCreateProfile.name),
    path("portfolio/" , view=List_portfolio.as_view(),name=List_portfolio.name  ),
     path("portfolio/<int:pk>" , view=updateportfolio.as_view(),name=updateportfolio.name  ),
    path("about/" , view=list_about.as_view() , name=list_about.name),
     path("about/<int:pk>" , view=UpdateAbout.as_view() , name=UpdateAbout.name),
     path("resume" , view=list_resume.as_view() , name=list_resume.name),
      path("resume/<int:pk>" , view=update_resume.as_view() , name=update_resume.name),
     
]