from django.urls import path
from .views import CandidateCreateView, RegistrationSuccessView

urlpatterns = [
    path('', CandidateCreateView.as_view(), name='register_candidate'),
    path('success/', RegistrationSuccessView.as_view(), name='registration_success'),
]
