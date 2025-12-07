from django import forms
from .models import Candidate

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            'full_name', 'ballot_name', 'date_of_birth', 'nic',
            'gender',
            'address', 'mailing_address',
            'contact_number', 'email',
            'is_registered_voter', 'electoral_district', 'polling_division',
            'gn_division', 'registration_number',
            'nomination_type',
            'party_name', 'party_secretary_name',
            'mp_status_proof', 'nominator_nic',
            'candidate_photo',
            'form_a', 'asset_declaration',
            'eligibility_declaration'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Legal Name'}),
            'ballot_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name to appear on record'}),
            'nic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIC Number'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Permanent Residence Address (must match Electoral Register)',
            }),
            'mailing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Current / Mailing Address (if different)',
            }),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_registered_voter': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'electoral_district': forms.TextInput(attrs={'class': 'form-control'}),
            'polling_division': forms.TextInput(attrs={'class': 'form-control'}),
            'gn_division': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'nomination_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_nomination_type'}),
            'party_name': forms.Select(attrs={'class': 'form-control party-field'}),
            'party_secretary_name': forms.TextInput(attrs={'class': 'form-control party-field'}),
            'nominator_nic': forms.TextInput(attrs={'class': 'form-control independent-field'}),
            'eligibility_declaration': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'gender': 'Gender',
            'address': 'Permanent Residence Address',
            'mailing_address': 'Current / Mailing Address',
            'is_registered_voter': 'Candidate is a registered voter in the National Voter Registry',
            'electoral_district': 'Electoral District',
            'polling_division': 'Polling Division',
            'gn_division': 'Gram Niladhari (GN) Division',
            'registration_number': 'Electoral Register Registration Number',
            'mp_status_proof': 'Proof of MP Status (PDF)',
            'candidate_photo': 'Candidate Photograph (for ballot / voter display)',
            'form_a': 'Form A – Nomination Paper (PDF)',
            'asset_declaration': 'Asset Declaration (PDF, as per declaration requirements)',
            'eligibility_declaration': 'I confirm that I agree to all terms and conditions listed above.',
        }
