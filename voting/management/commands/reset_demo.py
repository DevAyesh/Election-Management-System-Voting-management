import os
from django.core.management.base import BaseCommand, CommandError
from voting.models import Vote, BlockchainBlock, LedgerStatus

class Command(BaseCommand):
    help = 'DEMO ONLY: clear votes, ledger, status and the anchor file.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true')
        parser.add_argument('--anchor-file', default='data/anchors.txt')

    def handle(self, *args, **o):
        if os.environ.get('DEMO_RESET') != 'true':
            raise CommandError('Refusing: DEMO_RESET is not "true".')
        if not o['yes']:
            raise CommandError('Add --yes to confirm.')
        counts = {
            'votes': Vote.objects.all().delete()[0],
            'blocks': BlockchainBlock.objects.all().delete()[0],
            'status': LedgerStatus.objects.all().delete()[0],
        }
        try:
            from voting.models import UsedToken
            counts['used_tokens'] = UsedToken.objects.all().delete()[0]
        except ImportError:
            pass
        if os.path.exists(o['anchor_file']):
            os.remove(o['anchor_file'])
            counts['anchor_file'] = 'deleted'
        self.stdout.write(self.style.WARNING(f'Demo reset done: {counts}'))
