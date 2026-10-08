import hashlib
import json
from datetime import datetime, timezone

GENESIS_PREVIOUS_HASH = '0' * 64

def _sha256_hex(data):
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def compute_ballot_hash(preferences):
    canonical = json.dumps(preferences, sort_keys=True, separators=(',', ':'))
    return _sha256_hex(canonical)

def compute_block_hash(block_index, station_code, voted_at_iso, ballot_hash, previous_hash):
    raw = f'{block_index}|{station_code}|{voted_at_iso}|{ballot_hash}|{previous_hash}'
    return _sha256_hex(raw)

def build_block_fields(block_index, station_code, voted_at, preferences, previous_hash):
    if voted_at.tzinfo is None:
        voted_at = voted_at.replace(tzinfo=timezone.utc)
    voted_at_iso = voted_at.isoformat()
    ballot_hash = compute_ballot_hash(preferences)
    block_hash = compute_block_hash(block_index, station_code, voted_at_iso, ballot_hash, previous_hash)
    return {
        'block_index': block_index,
        'station_code': station_code,
        'voted_at_iso': voted_at_iso,
        'ballot_hash': ballot_hash,
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
            return False, f'Block sequence gap: expected {expected_index}, found {block.block_index}.'
        if block.block_index == 0:
            expected_prev = GENESIS_PREVIOUS_HASH
        else:
            expected_prev = prev_hash
        if block.previous_hash != expected_prev:
            return False, f'Block {block.block_index}: previous_hash mismatch.'
        recomputed = compute_block_hash(block.block_index, block.station_code, block.voted_at_iso, block.ballot_hash, block.previous_hash)
        if recomputed != block.block_hash:
            return False, f'Block {block.block_index}: block_hash tampered. Stored {block.block_hash[:16]}..., recomputed {recomputed[:16]}...'
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
