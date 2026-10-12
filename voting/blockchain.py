import hashlib
import hmac
import json
from collections import Counter
from datetime import datetime, timezone
from django.conf import settings

GENESIS_PREVIOUS_HASH = '0' * 64

def _sha256_hex(data):
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def compute_ballot_hash(preferences):
    canonical = json.dumps(preferences, sort_keys=True, separators=(',', ':'))
    return hmac.new(
        settings.LEDGER_HMAC_KEY.encode('utf-8'),
        canonical.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

def compute_ciphertext_hash(ciphertext):
    return _sha256_hex(ciphertext or '')


def compute_block_hash(block_index, station_code, voted_at_iso,
                       ballot_hash, previous_hash, ciphertext_hash=''):
    raw = (f'{block_index}|{station_code}|{voted_at_iso}|{ballot_hash}'
           f'|{ciphertext_hash}|{previous_hash}')
    return _sha256_hex(raw)


def build_block_fields(block_index, station_code, preferences,
                       previous_hash, voted_at=None, ciphertext=''):
    if voted_at is not None:
        if voted_at.tzinfo is None:
            voted_at = voted_at.replace(tzinfo=timezone.utc)
        voted_at_iso = voted_at.isoformat()
    else:
        voted_at_iso = ''
    ballot_hash = compute_ballot_hash(preferences)
    block_hash = compute_block_hash(
        block_index, station_code, voted_at_iso, ballot_hash,
        previous_hash, compute_ciphertext_hash(ciphertext))
    return {
        'block_index': block_index,
        'station_code': station_code,
        'voted_at_iso': voted_at_iso,
        'ballot_hash': ballot_hash,
        'ballot_ciphertext': ciphertext,
        'previous_hash': previous_hash,
        'block_hash': block_hash,
    }


def verify_chain(blocks_qs):
    blocks = list(blocks_qs)
    if not blocks:
        return True, None
    prev_hash = GENESIS_PREVIOUS_HASH
    expected_index = 0
    for block in blocks:
        if block.block_index != expected_index:
            return False, (f'Block sequence gap: expected {expected_index}, '
                           f'found {block.block_index}.')
        expected_prev = GENESIS_PREVIOUS_HASH if block.block_index == 0 else prev_hash
        if block.previous_hash != expected_prev:
            return False, f'Block {block.block_index}: previous_hash mismatch.'
        recomputed = compute_block_hash(
            block.block_index, block.station_code, block.voted_at_iso,
            block.ballot_hash, block.previous_hash,
            compute_ciphertext_hash(block.ballot_ciphertext))
        if recomputed != block.block_hash:
            return False, (f'Block {block.block_index}: block_hash tampered. '
                           f'Stored {block.block_hash[:16]}..., '
                           f'recomputed {recomputed[:16]}...')
        prev_hash = block.block_hash
        expected_index += 1
    return True, None

def get_chain_tip_hash(BlockchainBlock):
    last = BlockchainBlock.objects.order_by('-block_index').first()
    if last is None:
        return GENESIS_PREVIOUS_HASH
    return last.block_hash

def get_next_block_index(BlockchainBlock):
    last = BlockchainBlock.objects.order_by('-block_index').first()
    if last is None:
        return 0
    return last.block_index + 1


def reconcile_votes_with_chain(votes_qs, blocks_qs, decrypt):
    """Compare the vote collection with the ledger per station,
    without linking any single vote to any single block."""
    vote_side = Counter()
    undecryptable = 0
    for v in votes_qs:
        try:
            prefs = decrypt(v.preferences)
        except Exception:
            undecryptable += 1
            continue
        vote_side[(v.station_code or '', compute_ballot_hash(prefs))] += 1

    block_side = Counter((b.station_code, b.ballot_hash) for b in blocks_qs)

    votes_without_block = sum((vote_side - block_side).values())
    blocks_without_vote = sum((block_side - vote_side).values())
    ok = (votes_without_block == 0 and blocks_without_vote == 0
          and undecryptable == 0)
    return ok, {
        'votes': sum(vote_side.values()) + undecryptable,
        'blocks': sum(block_side.values()),
        'votes_without_block': votes_without_block,
        'blocks_without_vote': blocks_without_vote,
        'undecryptable_votes': undecryptable,
    }


def get_ballots_from_chain(blocks, decrypt):
    """Return (ballots, bad_block_indexes). A block is counted only if
    its own hash is consistent, its ciphertext decrypts, and the
    decrypted ballot matches ballot_hash."""
    ballots, bad = [], []
    for b in blocks:
        try:
            expected = compute_block_hash(
                b.block_index, b.station_code, b.voted_at_iso,
                b.ballot_hash, b.previous_hash,
                compute_ciphertext_hash(b.ballot_ciphertext))
            if expected != b.block_hash:
                raise ValueError('block hash mismatch')
            prefs = decrypt(b.ballot_ciphertext)
            if compute_ballot_hash(prefs) != b.ballot_hash:
                raise ValueError('ballot hash mismatch')
            ballots.append({'prefs': prefs, 'station_code': b.station_code})
        except Exception:
            bad.append(b.block_index)
    return ballots, bad

