from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='voting_index'),
    path('submit/', views.submit_vote, name='submit_vote'),
    path('success/', views.success, name='vote_success'),
    path('results/', views.results, name='results'),
]
