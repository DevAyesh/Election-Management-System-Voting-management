from django.core.management.base import BaseCommand
from django.utils import timezone
from voting.models import LedgerStatus, AuditLog


class Command(BaseCommand):
    help = 'Unlock voting after officials have reviewed an integrity failure.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true',
                            help='confirm the unlock')

    def handle(self, *args, **o):
        if not o['yes']:
            self.stdout.write('Add --yes to confirm unlocking voting.')
            return
        status = LedgerStatus.objects.first() or LedgerStatus()
        status.voting_locked = False
        status.ok = True
        status.detail = f'Unlocked by operator at {timezone.now().isoformat()}'
        status.checked_at = timezone.now()
        status.save()
        AuditLog.objects.create(
            event_type=AuditLog.EventType.ERROR,
            details='Voting unlocked by operator after integrity review.',
        )
        self.stdout.write(self.style.SUCCESS('Voting unlocked.'))
