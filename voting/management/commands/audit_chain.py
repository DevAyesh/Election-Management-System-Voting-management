import json
import sys
from django.core.management.base import BaseCommand
from voting.models import Vote, BlockchainBlock
from voting.views import cipher_suite
from voting.blockchain import (
    verify_chain, reconcile_votes_with_chain, get_chain_tip_hash,
    get_ballots_from_chain,
)


class Command(BaseCommand):
    help = "Audit the vote ledger: chain, vote reconciliation, external anchor."

    def add_arguments(self, parser):
        parser.add_argument("--anchor", help="COUNT:TIPHASH saved earlier")
        parser.add_argument("--save-anchor", metavar="FILE",
                            help="append the current COUNT:TIPHASH to FILE")

    def handle(self, *args, **o):
        failures = []
        blocks = list(BlockchainBlock.objects.order_by("block_index"))
        total = len(blocks)

        ok, err = verify_chain(blocks)
        self._line("Chain integrity", ok, err or f"{total} blocks")
        if not ok:
            failures.append("chain")

        decrypt = lambda s: json.loads(cipher_suite.decrypt(s.encode()).decode())
        _, bad = get_ballots_from_chain(blocks, decrypt)
        ok_contents = len(bad) == 0
        self._line("Block contents", ok_contents, f"bad blocks: {bad[:10]}" if bad else f"{total} blocks")
        if not ok_contents:
            failures.append("contents")

        ok, info = reconcile_votes_with_chain(Vote.objects.all(), blocks, decrypt)
        self._line("Votes vs ledger", ok, str(info))
        if not ok:
            failures.append("reconcile")

        tip = get_chain_tip_hash(BlockchainBlock)
        if o["anchor"]:
            try:
                count_s, tip_s = o["anchor"].split(":")
                count = int(count_s)
                if count == 0:
                    good = True
                else:
                    good = total >= count and blocks[count - 1].block_hash == tip_s
            except (ValueError, IndexError):
                good = False
            self._line("Anchor", good, o["anchor"][:30] + "...")
            if not good:
                failures.append("anchor")
        else:
            self.stdout.write("Anchor            : skipped (no --anchor given)")

        self.stdout.write(f"\nCurrent anchor -> {total}:{tip}")
        if o["save_anchor"]:
            if total > 0:
                with open(o["save_anchor"], "a") as f:
                    f.write(f"{total}:{tip}\n")
                self.stdout.write(f"Saved to {o['save_anchor']}")
            else:
                self.stdout.write("No blocks yet, anchor not saved.")

        if failures:
            self.stdout.write(self.style.ERROR(f"\nAUDIT FAILED: {', '.join(failures)}"))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("\nAUDIT PASSED"))

    def _line(self, name, ok, detail):
        mark = self.style.SUCCESS("PASS") if ok else self.style.ERROR("FAIL")
        self.stdout.write(f"{name:<18}: {mark}  {detail}")
