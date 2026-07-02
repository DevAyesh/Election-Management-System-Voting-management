from django.urls import path
from . import views


urlpatterns = [
    # -------------------------------------------------------------------------
    # Results admin login (super-admin)
    # -------------------------------------------------------------------------
    path('login/',  views.user_login,  name='login'),
    path('logout/', views.user_logout, name='logout'),

    # -------------------------------------------------------------------------
    # Polling station session (polling master logs in once at start of day)
    # -------------------------------------------------------------------------
    path('station/login/',   views.station_login,  name='station_login'),
    path('station/logout/',  views.station_logout, name='station_logout'),
    path('station/results/', views.station_results, name='station_results'),

    # -------------------------------------------------------------------------
    # Voting (requires active station session)
    # -------------------------------------------------------------------------
    path('',        views.index,       name='voting_index'),
    path('submit/', views.submit_vote, name='submit_vote'),
    path('success/', views.success,   name='vote_success'),

    # -------------------------------------------------------------------------
    # Global results (super-admin only)
    # -------------------------------------------------------------------------
    path('results/', views.results, name='results'),

    # -------------------------------------------------------------------------
    # Temporary Voter ID management (super-admin only)
    # -------------------------------------------------------------------------
    path('voters/',                   views.voter_id_list,   name='voter_id_list'),
    path('voters/create/',            views.voter_id_create, name='voter_id_create'),
    path('voters/bulk/',              views.voter_id_bulk,   name='voter_id_bulk'),
    path('voters/<str:voter_id>/delete/', views.voter_id_delete, name='voter_id_delete'),
]
