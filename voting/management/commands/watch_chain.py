import json
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from voting.models import Vote, BlockchainBlock, LedgerStatus, AuditLog
from voting.views import cipher_suite
from voting.blockchain import (
    verify_chain, reconcile_votes_with_chain, get_ballots_from_chain,
)


def _decrypt(s):
    return json.loads(cipher_suite.decrypt(s.encode()).decode())


def run_checks(anchor_file):
    problems = []
    blocks = list(BlockchainBlock.objects.order_by('block_index'))

    ok, err = verify_chain(blocks)
    if not ok:
        problems.append(f'chain: {err}')

    _, bad = get_ballots_from_chain(blocks, _decrypt)
    if bad:
        problems.append(f'blocks with bad content: {bad[:10]}')

    ok, info = reconcile_votes_with_chain(Vote.objects.all(), blocks, _decrypt)
    if not ok:
        problems.append(f'votes vs ledger: {info}')

    try:
        with open(anchor_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        if lines:
            count_s, tip_s = lines[-1].split(':')
            count = int(count_s)
            if count > 0 and (len(blocks) < count or
                              blocks[count - 1].block_hash != tip_s):
                problems.append(f'anchor mismatch: {lines[-1][:24]}...')
    except FileNotFoundError:
        pass
    except (ValueError, IndexError):
        problems.append('anchor file unreadable')

    return problems, blocks


class Command(BaseCommand):
    help = 'Continuously audit the ledger. Locks voting on any failure.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=60)
        parser.add_argument('--anchor-every', type=int, default=300)
        parser.add_argument('--anchor-file', default='anchors.txt')
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--lock-on-failure', action='store_true',
                            help='also lock voting when a check fails (off by default)')

    def handle(self, *args, **o):
        last_anchor = 0.0
        while True:
            problems, blocks = run_checks(o['anchor_file'])
            if problems:
                # a vote may be mid-write (block saved, copy not yet);
                # re-check once before locking
                time.sleep(3)
                problems, blocks = run_checks(o['anchor_file'])

            self._update(problems, lock=o['lock_on_failure'])

            if (not problems and blocks
                    and time.time() - last_anchor >= o['anchor_every']):
                with open(o['anchor_file'], 'a') as f:
                    f.write(f'{len(blocks)}:{blocks[-1].block_hash}\n')
                last_anchor = time.time()

            stamp = timezone.localtime().strftime('%H:%M:%S')
            if problems:
                self.stdout.write(self.style.ERROR(
                    f'[{stamp}] FAIL: ' + ' | '.join(problems)))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'[{stamp}] OK: {len(blocks)} blocks'))

            if o['once']:
                break
            time.sleep(o['interval'])

    def _update(self, problems, lock=False):
        status = LedgerStatus.objects.first() or LedgerStatus()
        status.checked_at = timezone.now()
        if problems:
            new_detail = ' | '.join(problems)[:2000]
            changed = (new_detail != status.detail)
            status.ok = False
            status.detail = new_detail
            if lock:
                status.voting_locked = True
            status.save()
            if changed:
                AuditLog.objects.create(
                    event_type=AuditLog.EventType.ERROR,
                    details='INTEGRITY WARNING: ' + new_detail[:500],
                )
        else:
            status.ok = True
            if not status.voting_locked:
                status.detail = ''
            status.save()
