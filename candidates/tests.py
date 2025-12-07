from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Candidate

class CandidateModelTest(TestCase):
    def setUp(self):
        self.valid_dob = date.today() - timedelta(days=365*35) # 35 years old
        self.underage_dob = date.today() - timedelta(days=365*25) # 25 years old
        
        self.dummy_file = SimpleUploadedFile("file.pdf", b"file_content", content_type="application/pdf")
        self.dummy_image = SimpleUploadedFile("image.jpg", b"image_content", content_type="image/jpeg")

    def test_age_gatekeeper(self):
        """Test that candidates under 30 are rejected."""
        candidate = Candidate(
            full_name="Young Candidate",
            date_of_birth=self.underage_dob,
            nic="123456789V",
            is_dual_citizen=False,
            nomination_type='INDEPENDENT',
            mp_status_proof=self.dummy_file,
            nominator_nic="987654321V",
            form_a=self.dummy_file,
            asset_declaration=self.dummy_file
        )
        with self.assertRaises(ValidationError) as cm:
            candidate.full_clean()
        self.assertIn("Candidate must be at least 30 years old", str(cm.exception))

    def test_citizenship_gatekeeper(self):
        """Test that dual citizens are rejected."""
        candidate = Candidate(
            full_name="Dual Citizen Candidate",
            date_of_birth=self.valid_dob,
            nic="123456789V",
            is_dual_citizen=True, # Disqualified
            nomination_type='INDEPENDENT',
            mp_status_proof=self.dummy_file,
            nominator_nic="987654321V",
            form_a=self.dummy_file,
            asset_declaration=self.dummy_file
        )
        with self.assertRaises(ValidationError) as cm:
            candidate.full_clean()
        self.assertIn("Dual citizens are disqualified", str(cm.exception))

    def test_party_nomination_requirements(self):
        """Test that Party candidates must provide Secretary Name and Symbol."""
        candidate = Candidate(
            full_name="Party Candidate",
            date_of_birth=self.valid_dob,
            nic="123456789V",
            is_dual_citizen=False,
            nomination_type='PARTY',
            # Missing secretary and symbol
            form_a=self.dummy_file,
            asset_declaration=self.dummy_file
        )
        with self.assertRaises(ValidationError) as cm:
            candidate.full_clean()
        self.assertIn("Party Secretary Name is required", str(cm.exception))
        self.assertIn("Party Symbol is required", str(cm.exception))

    def test_independent_nomination_requirements(self):
        """Test that Independent candidates must provide MP Proof and Nominator NIC."""
        candidate = Candidate(
            full_name="Independent Candidate",
            date_of_birth=self.valid_dob,
            nic="123456789V",
            is_dual_citizen=False,
            nomination_type='INDEPENDENT',
            # Missing MP proof and nominator NIC
            form_a=self.dummy_file,
            asset_declaration=self.dummy_file
        )
        with self.assertRaises(ValidationError) as cm:
            candidate.full_clean()
        self.assertIn("MP Status Proof is required", str(cm.exception))
        self.assertIn("Nominator NIC is required", str(cm.exception))

    def test_valid_submission(self):
        """Test a valid submission."""
        candidate = Candidate(
            full_name="Valid Candidate",
            date_of_birth=self.valid_dob,
            nic="123456789V",
            is_dual_citizen=False,
            nomination_type='INDEPENDENT',
            mp_status_proof=self.dummy_file,
            nominator_nic="987654321V",
            form_a=self.dummy_file,
            asset_declaration=self.dummy_file
        )
        try:
            candidate.full_clean()
            candidate.save()
        except ValidationError:
            self.fail("Valid candidate raised ValidationError")
