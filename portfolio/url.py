from django.urls import path, re_path
from .views import ListCreateProfile , api_root , list_about , Userdetail ,updateUserdetail , UpdateProfile
from .views import List_portfolio ,list_about ,UpdateAbout , updateportfolio , list_resume , update_resume , list_school , update_school , list_proficiency , update_proficiency
from .views import list_tracks , update_track , list_goals , update_goal , complete_goal
from .auth_views import CsrfPrimeView , SignupView , GoogleLoginView , GoogleLinkView , SetPasswordView , LoginView , LogoutView , RefreshView , MeView , ChangePasswordView
from .analytics_views import RecordVisitView , RecordResumeViewView , VisitorSummaryView
from .accounts_views import AccountListView , AccountDeleteView
from .resume_views import ResumeDownloadView , ResumePagesView , ResumePageImageView , ResumeTemplatesView

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
    
    #proficiency/ returns all user proficiency in the DB
    #proficiency/?username=apple returns proficiency related to the user called apple
    # proficiency/<int:pk> returns a specific proficiency from the DB and could be updated

    path("proficiency/" , view=list_proficiency.as_view() , name=list_proficiency.name),
    path("proficiency/<int:pk>" , view=update_proficiency.as_view() , name=update_proficiency.name),

    #tracks/ returns all portfolio tracks in the DB
    #tracks/?username=apple returns tracks belonging to the user called apple
    #tracks/<int:pk> returns a specific track and could be updated
    #POST supports optional copy_from=<track_id> and copy_portfolio_items=true to clone content from an existing track

    path("tracks/" , view=list_tracks.as_view() , name=list_tracks.name),
    path("tracks/<int:pk>" , view=update_track.as_view() , name=update_track.name),

    #goals/ returns all goals in the DB
    #goals/?username=apple returns goals belonging to the user called apple
    #goals/<int:pk> returns a specific goal and could be updated
    #goals/<int:pk>/complete marks a goal completed and creates the chosen entry type under the selected tracks

    path("goals/" , view=list_goals.as_view() , name=list_goals.name),
    path("goals/<int:pk>" , view=update_goal.as_view() , name=update_goal.name),
    path("goals/<int:pk>/complete" , view=complete_goal.as_view() , name=complete_goal.name),

    #auth/csrf primes the csrftoken cookie, returns its value in the body
    #auth/login sets access_token+refresh_token httpOnly cookies
    #auth/logout clears both cookies
    #auth/refresh reissues access_token from refresh_token cookie
    #auth/me reports whether the current request is authenticated
    #auth/change-password takes current_password + new_password for the signed-in user

    path("auth/csrf" , view=CsrfPrimeView.as_view() , name=CsrfPrimeView.name),
    path("accounts/" , view=AccountListView.as_view() , name=AccountListView.name),
    path("accounts/<int:pk>" , view=AccountDeleteView.as_view() , name=AccountDeleteView.name),
    path("auth/signup" , view=SignupView.as_view() , name=SignupView.name),
    path("auth/google" , view=GoogleLoginView.as_view() , name=GoogleLoginView.name),
    path("auth/google/link" , view=GoogleLinkView.as_view() , name=GoogleLinkView.name),
    path("auth/set-password" , view=SetPasswordView.as_view() , name=SetPasswordView.name),
    path("auth/login" , view=LoginView.as_view() , name=LoginView.name),
    path("auth/logout" , view=LogoutView.as_view() , name=LogoutView.name),
    path("auth/refresh" , view=RefreshView.as_view() , name=RefreshView.name),
    path("auth/me" , view=MeView.as_view() , name=MeView.name),
    path("auth/change-password" , view=ChangePasswordView.as_view() , name=ChangePasswordView.name),

    #analytics/visit is the public beacon the site calls on every page open (always 204)
    #analytics/summary is the owner-only visitor report (landing page, signed in)

    path("analytics/visit" , view=RecordVisitView.as_view() , name=RecordVisitView.name),
    path("analytics/summary" , view=VisitorSummaryView.as_view() , name=VisitorSummaryView.name),
    path("analytics/resume-view" , view=RecordResumeViewView.as_view() , name=RecordResumeViewView.name),

    #resume-export/<slug>/download/pdf|docx is the owner-only download of one portfolio's resume
    #resume-export/<slug>/pages and /pages/<n>.png are the public read-only viewer (images only)

    path("resume-export/templates" , view=ResumeTemplatesView.as_view() , name=ResumeTemplatesView.name),
    path("resume-export/<slug:slug>/download/<str:kind>" , view=ResumeDownloadView.as_view() , name=ResumeDownloadView.name),
    path("resume-export/<slug:slug>/pages" , view=ResumePagesView.as_view() , name=ResumePagesView.name),
    path("resume-export/<slug:slug>/pages/<int:page>.png" , view=ResumePageImageView.as_view() , name=ResumePageImageView.name),

]