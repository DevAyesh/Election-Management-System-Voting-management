from django.db import models
from django.core.exceptions import ValidationError
from datetime import date

def validate_age(dob):
    today = date.today()
    # Calculate age
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 30:
        raise ValidationError("Candidate must be at least 30 years old.")

def validate_citizenship(is_dual):
    if is_dual:
        raise ValidationError("Dual citizens are disqualified per 21st Amendment.")

class Candidate(models.Model):
    NOMINATION_CHOICES = [
        ('PARTY', 'Recognized Political Party'),
        ('INDEPENDENT', 'Independent Candidate'),
    ]

    PARTY_CHOICES = [
        ('SLPP', 'Sri Lanka Podujana Peramuna (SLPP)'),
        ('SJB', 'Samagi Jana Balawegaya (SJB)'),
        ('NPP', 'National People’s Power (NPP)'),
        ('SLFP', 'Sri Lanka Freedom Party (SLFP)'),
        ('UNP', 'United National Party (UNP)'),
        ('MJP', 'Mawbima Janatha Pakshaya (MJP)'),
    ]

    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other / Prefer not to say'),
    ]

    full_name = models.CharField(max_length=255)
    ballot_name = models.CharField(max_length=255, help_text="Name to appear on the record")
    date_of_birth = models.DateField(validators=[validate_age])
    nic = models.CharField(max_length=20, unique=True)
    
    # Contact Details
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='OTHER')
    address = models.TextField()
    mailing_address = models.TextField(blank=True, null=True, help_text="If different from the permanent address.")
    contact_number = models.CharField(max_length=20)
    email = models.EmailField()

    # Electoral Qualification / Voter Status
    is_registered_voter = models.BooleanField(
        default=False,
        help_text="Confirm that the candidate is a registered voter in the National Voter Registry."
    )
    electoral_district = models.CharField(max_length=100, blank=True, null=True)
    polling_division = models.CharField(max_length=100, blank=True, null=True)
    gn_division = models.CharField("Gram Niladhari (GN) Division", max_length=150, blank=True, null=True)
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Serial number from the certified Electoral Register (e.g., Reg No: 154 in Unit A)."
    )
    
    nomination_type = models.CharField(max_length=20, choices=NOMINATION_CHOICES)
    
    # Party Fields
    party_name = models.CharField(max_length=20, choices=PARTY_CHOICES, blank=True, null=True)
    party_secretary_name = models.CharField(max_length=255, blank=True, null=True)
    # party_symbol is now auto-assigned/derived, no longer a field
    
    # Independent Fields
    mp_status_proof = models.FileField(upload_to='mp_proofs/', blank=True, null=True)
    nominator_nic = models.CharField(max_length=20, blank=True, null=True)
    
    # Mandatory Artifacts
    candidate_photo = models.ImageField(
        upload_to='candidate_photos/',
        help_text="Passport-style colour photograph to be used on the ballot / voter information."
    )
    form_a = models.FileField(upload_to='form_a/')
    asset_declaration = models.FileField(upload_to='asset_declarations/')
    
    # Comprehensive Declaration
    eligibility_declaration = models.BooleanField(default=False)
    
    submission_date = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errors = {}
        # Nomination Logic Validation
        if self.nomination_type == 'PARTY':
            if not self.party_name:
                errors['party_name'] = 'Please select a Political Party.'
            if not self.party_secretary_name:
                errors['party_secretary_name'] = 'Party Secretary Name is required for recognized parties.'
        
        elif self.nomination_type == 'INDEPENDENT':
            if not self.mp_status_proof:
                errors['mp_status_proof'] = 'MP Status Proof is required for independent candidates.'
            if not self.nominator_nic:
                errors['nominator_nic'] = 'Nominator NIC is required for independent candidates.'

        # Electoral Qualification – candidate must be a registered voter
        if not self.is_registered_voter:
            errors['is_registered_voter'] = 'Candidate must be a registered voter as per the Electoral Register.'
        if self.is_registered_voter:
            if not self.electoral_district:
                errors['electoral_district'] = 'Electoral District is required for registered voters.'
            if not self.polling_division:
                errors['polling_division'] = 'Polling Division is required for registered voters.'
            if not self.gn_division:
                errors['gn_division'] = 'Gram Niladhari (GN) Division is required for registered voters.'
            if not self.registration_number:
                errors['registration_number'] = 'Registration Number from the Electoral Register is required.'

        # Declaration Validation
        if not self.eligibility_declaration:
            errors['eligibility_declaration'] = 'You must confirm that you meet all eligibility criteria and that the information provided is true.'
            
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        # For new instances, ensure we don't explicitly set id=None
        # Let MongoDB backend auto-generate the ObjectId
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.nomination_type})"
