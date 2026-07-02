from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('', views.index, name='voting_index'),
    path('submit/', views.submit_vote, name='submit_vote'),
    path('success/', views.success, name='vote_success'),
    path('results/', views.results, name='results'),
]

