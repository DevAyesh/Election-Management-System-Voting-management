from django.db import models
from django_mongodb_backend.fields import ObjectIdAutoField
import secrets


class PollingStation(models.Model):
    """One entry per polling division (154 total across 22 districts)."""
    id              = ObjectIdAutoField(primary_key=True)
    district_number = models.IntegerField()
    district_name   = models.CharField(max_length=100)
    division_code   = models.CharField(max_length=5)
    division_name   = models.CharField(max_length=100)
    # Unique secret key the polling master enters at session start
    login_key       = models.CharField(max_length=64, unique=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table    = 'polling_station'

    def __str__(self):
        return f"{self.district_name} / {self.division_name} ({self.division_code})"

    def regenerate_key(self):
        self.login_key = secrets.token_urlsafe(32)
        self.save(update_fields=['login_key'])


class Vote(models.Model):
    """A single encrypted ballot, tagged with the originating polling station."""
    id              = ObjectIdAutoField(primary_key=True)
    preferences     = models.TextField()                                  # Fernet-encrypted JSON
    polling_station = models.CharField(max_length=200, null=True, blank=True)  
    station_code    = models.CharField(max_length=20,  null=True, blank=True)  
    voted_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vote'


class TempVoterId(models.Model):
    """
    Stub voter ID record for POC testing.
    Will be replaced / connected to the real external ID system later.
    """
    id         = ObjectIdAutoField(primary_key=True)
    voter_id   = models.CharField(max_length=20, unique=True)  
    full_name  = models.CharField(max_length=200)
    district   = models.CharField(max_length=100)
    division   = models.CharField(max_length=100)
    has_voted  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'temp_voter_id'

    def __str__(self):
        return f"{self.voter_id} — {self.full_name}"


class AuditLog(models.Model):
    """Immutable audit trail for all critical events."""
    id           = ObjectIdAutoField(primary_key=True)

    class EventType(models.TextChoices):
        STATION_LOGIN    = 'STATION_LOGIN',    'Station Login'
        STATION_LOGOUT   = 'STATION_LOGOUT',   'Station Logout'
        LOGIN_FAILED     = 'LOGIN_FAILED',     'Login Failed'
        VOTE_CAST        = 'VOTE_CAST',        'Vote Cast'
        RATE_LIMITED     = 'RATE_LIMITED',     'Rate Limited'
        VOTER_CREATED    = 'VOTER_CREATED',    'Voter ID Created'
        VOTER_DELETED    = 'VOTER_DELETED',    'Voter ID Deleted'
        ERROR            = 'ERROR',            'Error'

    event_type   = models.CharField(max_length=20, choices=EventType.choices)
    station_name = models.CharField(max_length=200, null=True, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    details      = models.TextField(blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.event_type}] {self.station_name or 'N/A'} @ {self.timestamp}"


class BlockchainBlock(models.Model):
    """
    One block per vote, forming a tamper-evident ledger.

    Fields
    ------
    block_index   : Monotonically increasing integer.  Block 0 is the genesis block.
    station_code  : E.g. '01-KMB', copied from the matching Vote record.
    voted_at_iso  : ISO-8601 UTC timestamp string (round-trips losslessly across
                    Python, MongoDB, and JSON without needing a DateTimeField).
    ballot_hash   : SHA-256 of the plaintext preferences dict (sort_keys=True).
                    Voter identity is deliberately excluded.
    previous_hash : block_hash of block N-1, or '000…0' (64 zeros) for block 0.
    block_hash    : SHA-256 of  block_index|station_code|voted_at_iso|ballot_hash|previous_hash
                    Changing any field breaks this hash, making tampering detectable.
    """

    id            = ObjectIdAutoField(primary_key=True)
    block_index   = models.IntegerField(unique=True, db_index=True)
    station_code  = models.CharField(max_length=30)
    voted_at_iso  = models.CharField(max_length=50)  # ISO-8601 string
    ballot_hash   = models.CharField(max_length=64)  # SHA-256 hex
    previous_hash = models.CharField(max_length=64)  # SHA-256 hex
    block_hash    = models.CharField(max_length=64, unique=True)  # SHA-256 hex

    class Meta:
        db_table = 'blockchain_block'
        ordering = ['block_index']

    def __str__(self):
        return f"Block #{self.block_index} | {self.station_code} | {self.block_hash[:12]}…"
