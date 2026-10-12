"""
test_blockchain_tamper.py
Tamper-evidence test suite for the election blockchain ledger.
Validates HMAC-keyed ballot hashing, ciphertext hashing, chain integrity
verification, get_ballots_from_chain, and tamper detection using temporary
in-memory test data.
DOES NOT touch or modify any production database records.
"""

import os
import sys
import json
import hashlib
import hmac

# Configure standard output encoding for Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Initialize Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "election_portal.settings")
import django
django.setup()

from django.conf import settings
from voting.blockchain import (
    GENESIS_PREVIOUS_HASH,
    compute_ballot_hash,
    compute_ciphertext_hash,
    compute_block_hash,
    build_block_fields,
    verify_chain,
    reconcile_votes_with_chain,
    get_ballots_from_chain,
)
from voting.models import BlockchainBlock
from voting.views import cipher_suite


class MockVote:
    """Lightweight in-memory mock representing a Vote for reconciliation testing."""
    def __init__(self, station_code, preferences_raw):
        self.station_code = station_code
        self.preferences = preferences_raw


def run_tests():
    print("=" * 65)
    print("BLOCKCHAIN LEDGER TAMPER DETECTION & HMAC VERIFICATION SUITE")
    print("=" * 65)

    # 1. Verify LEDGER_HMAC_KEY configuration via Django settings
    hmac_key = getattr(settings, "LEDGER_HMAC_KEY", None)
    if hmac_key is None:
        print("[FAIL] settings.LEDGER_HMAC_KEY is not defined!")
        sys.exit(1)

    print(f"[1/6] Checking Django settings: LEDGER_HMAC_KEY is configured (type: {type(hmac_key).__name__}).")

    # 2. Test HMAC ballot hash generation
    test_prefs = {"first": 1, "second": 2}
    ballot_hash = compute_ballot_hash(test_prefs)
    assert len(ballot_hash) == 64, "Ballot hash must be a 64-char hex string"
    print(f"[2/6] HMAC-SHA256 ballot hash computation: PASS (hash length: {len(ballot_hash)})")

    # 3. Build a temporary in-memory test chain with ballot_ciphertext
    prefs_0 = {"candidate_id": 10}
    cipher_0 = cipher_suite.encrypt(json.dumps(prefs_0).encode()).decode()
    fields_0 = build_block_fields(
        block_index=0,
        station_code="TEST-01",
        preferences=prefs_0,
        previous_hash=GENESIS_PREVIOUS_HASH,
        ciphertext=cipher_0,
    )
    b0 = BlockchainBlock(**fields_0)

    prefs_1 = {"candidate_id": 20}
    cipher_1 = cipher_suite.encrypt(json.dumps(prefs_1).encode()).decode()
    fields_1 = build_block_fields(
        block_index=1,
        station_code="TEST-01",
        preferences=prefs_1,
        previous_hash=b0.block_hash,
        ciphertext=cipher_1,
    )
    b1 = BlockchainBlock(**fields_1)

    prefs_2 = {"candidate_id": 30}
    cipher_2 = cipher_suite.encrypt(json.dumps(prefs_2).encode()).decode()
    fields_2 = build_block_fields(
        block_index=2,
        station_code="TEST-02",
        preferences=prefs_2,
        previous_hash=b1.block_hash,
        ciphertext=cipher_2,
    )
    b2 = BlockchainBlock(**fields_2)

    chain = [b0, b1, b2]

    # Test baseline chain integrity
    ok, err = verify_chain(chain)
    if not ok:
        print(f"[FAIL] Baseline valid chain failed verification: {err}")
        sys.exit(1)
    print(f"[3/6] Valid chain verification (3 temporary blocks): PASS ({err or 'Chain intact'})")

    # 4. Test get_ballots_from_chain on valid chain
    decrypt = lambda s: json.loads(cipher_suite.decrypt(s.encode()).decode())
    ballots, bad = get_ballots_from_chain(chain, decrypt)
    assert len(ballots) == 3 and not bad, f"get_ballots_from_chain failed: bad blocks {bad}"
    print(f"[4/6] Extracting ballots from chain: PASS ({len(ballots)} ballots decrypted, bad: {len(bad)})")

    # 5. Tamper Scenarios
    print("[5/6] Testing tamper detection scenarios:")

    # Scenario A: Modify ballot_hash in block 1
    original_ballot_hash = b1.ballot_hash
    try:
        b1.ballot_hash = "0" * 64
        ok, err = verify_chain(chain)
        assert not ok, "Tampered ballot_hash was not detected!"
        assert "block_hash tampered" in err, f"Unexpected error message: {err}"
        print("  - [PASS] Detected tampered ballot hash on Block #1")
    finally:
        b1.ballot_hash = original_ballot_hash

    # Scenario B: Modify ballot_ciphertext in block 1
    original_ciphertext = b1.ballot_ciphertext
    try:
        b1.ballot_ciphertext = "corrupted_ciphertext"
        ok, err = verify_chain(chain)
        assert not ok, "Tampered ballot_ciphertext was not detected by verify_chain!"
        assert "block_hash tampered" in err, f"Unexpected error message: {err}"
        _, bad_test = get_ballots_from_chain(chain, decrypt)
        assert 1 in bad_test, "Tampered ballot_ciphertext was not detected by get_ballots_from_chain!"
        print("  - [PASS] Detected tampered ballot ciphertext on Block #1")
    finally:
        b1.ballot_ciphertext = original_ciphertext

    # Scenario C: Modify previous_hash in block 2
    original_prev_hash = b2.previous_hash
    try:
        b2.previous_hash = "f" * 64
        ok, err = verify_chain(chain)
        assert not ok, "Tampered previous_hash was not detected!"
        assert "previous_hash mismatch" in err, f"Unexpected error message: {err}"
        print("  - [PASS] Detected broken chain linkage (previous_hash mismatch) on Block #2")
    finally:
        b2.previous_hash = original_prev_hash

    # Scenario D: Sequence gap
    original_index = b2.block_index
    try:
        b2.block_index = 4
        ok, err = verify_chain(chain)
        assert not ok, "Sequence gap was not detected!"
        assert "Block sequence gap" in err, f"Unexpected error message: {err}"
        print("  - [PASS] Detected sequence index gap")
    finally:
        b2.block_index = original_index

    # 6. Reconciliation testing
    print("[6/6] Testing vote vs ledger reconciliation:")
    mock_votes = [
        MockVote("TEST-01", cipher_suite.encrypt(json.dumps(prefs_0).encode()).decode()),
        MockVote("TEST-01", cipher_suite.encrypt(json.dumps(prefs_1).encode()).decode()),
        MockVote("TEST-02", cipher_suite.encrypt(json.dumps(prefs_2).encode()).decode()),
    ]

    rec_ok, rec_info = reconcile_votes_with_chain(mock_votes, chain, decrypt)
    assert rec_ok, f"Reconciliation failed on matching test data: {rec_info}"
    print(f"  - [PASS] Clean reconciliation: {rec_info}")

    # Introduce mismatch
    tampered_votes = [
        MockVote("TEST-01", cipher_suite.encrypt(json.dumps(prefs_0).encode()).decode()),
        MockVote("TEST-01", cipher_suite.encrypt(json.dumps({"candidate_id": 99}).encode()).decode()),  # mismatch
        MockVote("TEST-02", cipher_suite.encrypt(json.dumps(prefs_2).encode()).decode()),
    ]
    rec_tampered_ok, rec_tampered_info = reconcile_votes_with_chain(tampered_votes, chain, decrypt)
    assert not rec_tampered_ok, "Reconciliation failed to detect mismatched vote!"
    print(f"  - [PASS] Detected vote mismatch in reconciliation: {rec_tampered_info}")

    print("=" * 65)
    print("ALL BLOCKCHAIN INTEGRITY & TAMPER TESTS PASSED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
