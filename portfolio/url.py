from django.urls import path, re_path
from .views import ListCreateProfile , api_root , list_about , Userdetail ,updateUserdetail , UpdateProfile
from .views import List_portfolio ,list_about ,UpdateAbout , updateportfolio , list_resume , update_resume , list_school , update_school , list_proficency , update_profiency

app_name = "portfolio"


urlpatterns = [
    path("" , view=api_root.as_view() , name = api_root.name),
    ### edit_user/<int:pk> is used to update the user detail likewise createuser 
    # is to create/ and list existing user
    
    path("edit_user/<int:pk>" , view = updateUserdetail.as_view() , name= updateUserdetail.name),
    path("createuser" , view = Userdetail.as_view() , name= Userdetail.name),
    
    
    #about/ is to get all the data in the DB About
    # about<int:pk/> is to get and update a specific user about data in the DB
    
    path("about/" , view= list_about.as_view() , name = list_about.name),
    path("about/<int:pk>" , view=UpdateAbout.as_view() , name=UpdateAbout.name),
   

   #profiles/ is to get all the user profiles in the DB 
   # which includes:
   # Portfolio
   # About
   # Resume

   #profiles/?username=apple will return the profile about the user called apple in the DB
        # which includes:
        # Portfolio
        # About
        # Resume
   
        # NOTE:
        # Portolio
        # About
        # Resume
        # can not be created or updated from the profiles/ or profiles/?username= apple
        # because it is in read only 
   # or returns None if if doesnt Exist
   # profiles/<int:pk> is used to get a specific user profile and could be updated
    
    path("profiles/" , view=ListCreateProfile.as_view() , name=ListCreateProfile.name),
    path("profiles/<int:pk>" , view=UpdateProfile.as_view() , name=UpdateProfile.name),
    
    #portfolio/ returns all user portfolio in the DB
    # portfolio/<int:pk> returns a specific user portfolio and could be updated
    
    path("portfolio/" , view=List_portfolio.as_view(),name=List_portfolio.name  ),
    path("portfolio/<int:pk>" , view=updateportfolio.as_view(),name=updateportfolio.name  ),
   
   #resume/ returns all user resumes in the DB 
   #resume/?username=apple returns reusme related to the user called apple
   # resume/<int:pk> returns a specific resume from the DB and could be updated

    path("resume/" , view=list_resume.as_view() , name=list_resume.name),
    path("resume/<int:pk>" , view=update_resume.as_view() , name=update_resume.name),
    
    #school/ returns all user school in the DB 
    #school/?username=apple returns school related to the user called apple
    # schoo/<int:pk> returns a specific school from the DB and could be updated

    path("school/" , view=list_school.as_view() , name=list_school.name),
    path("school/<int:pk>" , view=update_school.as_view() , name=update_school.name),
    
    #proficency/ returns all user proficency in the DB 
    #proficency/?username=apple returns proficency related to the user called apple
    # proficency/<int:pk> returns a specific proficency from the DB and could be updated

    path("profiency/" , view=list_proficency.as_view() , name=list_proficency.name),
    path("profiency/<int:pk>" , view=update_profiency.as_view() , name=update_profiency.name),
     
     
]