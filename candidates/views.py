from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from .models import Candidate
from .forms import CandidateForm

class CandidateCreateView(CreateView):
    """
    View to handle candidate registration.
    """
    model = Candidate
    form_class = CandidateForm
    template_name = 'candidates/register.html'
    success_url = reverse_lazy('registration_success')

    def form_valid(self, form):
        # Any additional logic before saving can go here
        return super().form_valid(form)

class RegistrationSuccessView(TemplateView):
    """
    View to display registration success message.
    """
    template_name = 'candidates/success.html'
