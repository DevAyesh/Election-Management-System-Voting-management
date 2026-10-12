from django.urls import path
from . import views


urlpatterns = [
    # -------------------------------------------------------------------------
    # Polling station session & Station Results
    # -------------------------------------------------------------------------
    path('station/login/',   views.station_login,  name='station_login'),
    path('station/logout/',  views.station_logout, name='station_logout'),
    path('station/results/', views.station_results, name='station_results'),
    path('login/',           views.station_login,  name='login'),
    path('verify/',          views.qr_verification, name='qr_verification'),
    path('verify/check/',    views.verify_qr_token, name='verify_qr_token'),
    path('station/verify/',  views.qr_verification, name='station_qr_verify'),

    # -------------------------------------------------------------------------
    # Voting interface (requires active station session)
    # -------------------------------------------------------------------------
    path('',        views.index,       name='voting_index'),
    path('submit/', views.submit_vote, name='submit_vote'),
    path('success/', views.success,   name='vote_success'),
    # -------------------------------------------------------------------------
    # Candidate Data API (Member 3 & External Services)
    # -------------------------------------------------------------------------
    path('api/candidates/', views.get_candidates_api, name='api_candidates'),
    path('api/candidates/<str:candidate_id>/', views.get_candidates_api, name='api_candidate_detail'),
]

