import os
import pymongo
from django.core.management.base import BaseCommand
from django.conf import settings
from candidates.models import Candidate

# =============================================================================
# FIELD_MAP: Maps local Candidate model fields to remote MongoDB document fields.
# Modify the right-hand remote field names after verifying remote schema output.
# =============================================================================
FIELD_MAP = {
    'full_name':   'full_name',     # Remote field for candidate full name (e.g., 'name', 'candidate_name')
    'ballot_name': 'ballot_name',   # Remote field for ballot display name (e.g., 'ballot_name', 'display_name')
    'party_name':  'party_name',    # Remote field for political party name (e.g., 'party', 'party_name')
    'photo_url':   'photo_url',     # Remote field for candidate photo URL (e.g., 'photo_url', 'image', 'avatar')
}

class Command(BaseCommand):
    help = 'Sync candidate data from Member 3 read-only MongoDB Atlas cluster into local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate synchronization without modifying local database records',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        uri = getattr(settings, 'MEMBER3_MONGO_URI', '') or os.environ.get('MEMBER3_MONGO_URI', '')
        db_name = getattr(settings, 'MEMBER3_DB', '') or os.environ.get('MEMBER3_DB', '')
        coll_name = getattr(settings, 'MEMBER3_COLLECTION', '') or os.environ.get('MEMBER3_COLLECTION', '')

        if not uri or not db_name or not coll_name:
            self.stderr.write(self.style.ERROR(
                "[ERROR] Missing configuration in .env. Ensure MEMBER3_MONGO_URI, MEMBER3_DB, and MEMBER3_COLLECTION are set."
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("=== RUNNING IN DRY-RUN MODE (No database writes) ===\n"))

        self.stdout.write(f"Connecting to remote MongoDB database '{db_name}'...")

        import time
        remote_docs = None
        last_error = None
        for attempt in range(1, 4):
            try:
                client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000)
                db = client[db_name]
                collection = db[coll_name]
                remote_docs = list(collection.find())
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(1.5)

        if remote_docs is None:
            self.stderr.write(self.style.ERROR(f"[CONNECTION ERROR] Failed to fetch remote candidates: {last_error}"))
            return

        total_remote = len(remote_docs)
        self.stdout.write(f"Found {total_remote} candidate document(s) in collection '{coll_name}'.\n")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for doc in remote_docs:
            remote_id = doc.get('_id')
            if not remote_id:
                skipped_count += 1
                continue

            source_id = str(remote_id)

            # Extract nested dictionaries from Member 3 schema
            ballot_details = doc.get('ballotDetails') or {}
            party_affiliation = doc.get('partyAffiliation') or {}

            # Map fields with fallback to Member 3 schema structure
            full_name = (
                doc.get(FIELD_MAP['full_name']) or
                doc.get('fullName') or
                doc.get('name') or
                'Unknown Candidate'
            )
            ballot_name = (
                doc.get(FIELD_MAP['ballot_name']) or
                ballot_details.get('ballotName') or
                doc.get('ballotName') or
                full_name
            )
            party_name = (
                doc.get(FIELD_MAP['party_name']) or
                party_affiliation.get('partyName') or
                doc.get('party') or
                ''
            )
            photo_url = (
                doc.get(FIELD_MAP['photo_url']) or
                ballot_details.get('symbolImageUrl') or
                doc.get('photo') or
                doc.get('image') or
                ''
            )

            candidate_id = doc.get('candidateId') or doc.get('candidate_id') or ''

            # Check if candidate exists by _id (same DB) or source_id
            existing = (
                Candidate.objects.filter(source_id=source_id).first() or
                Candidate.objects.filter(id=remote_id).first()
            )

            if dry_run:
                if existing:
                    updated_count += 1
                    self.stdout.write(f"  [WOULD UPDATE] source_id={source_id} | {ballot_name} ({party_name})")
                else:
                    created_count += 1
                    self.stdout.write(f"  [WOULD CREATE] source_id={source_id} | {ballot_name} ({party_name})")
            else:
                if existing:
                    existing.source_id = source_id
                    existing.full_name = full_name
                    existing.ballot_name = ballot_name
                    existing.party_name = party_name
                    existing.photo_url = photo_url
                    if candidate_id:
                        existing.candidateId = candidate_id
                    existing.save()
                    updated_count += 1
                    self.stdout.write(f"  [UPDATED] source_id={source_id} | {ballot_name}")
                else:
                    candidate = Candidate.objects.create(
                        id=remote_id,
                        source_id=source_id,
                        candidateId=candidate_id,
                        full_name=full_name,
                        ballot_name=ballot_name,
                        party_name=party_name,
                        photo_url=photo_url,
                    )
                    created_count += 1
                    self.stdout.write(f"  [CREATED] source_id={source_id} | {candidate.ballot_name}")

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("CANDIDATE SYNC SUMMARY:")
        self.stdout.write(f"  Total Remote Documents: {total_remote}")
        self.stdout.write(f"  {'Would Create' if dry_run else 'Created'}:         {created_count}")
        self.stdout.write(f"  {'Would Update' if dry_run else 'Updated'}:         {updated_count}")
        self.stdout.write(f"  Skipped (No _id):       {skipped_count}")
        self.stdout.write("=" * 50)
