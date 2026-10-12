from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.db import IntegrityError
from pymongo.errors import DuplicateKeyError
from functools import wraps
from candidates.models import Candidate
from .models import Vote, PollingStation, AuditLog, BlockchainBlock, LedgerStatus
import json
import threading
import pymongo
import re
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from cryptography.fernet import Fernet
from django.contrib import messages
from django.utils import timezone
from .blockchain import (
    build_block_fields, get_chain_tip_hash, get_next_block_index,
    get_ballots_from_chain,
)

try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver()
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
except Exception:
    pass

# Serialise blockchain block creation within a process to prevent duplicate indices
_blockchain_lock = threading.Lock()

# Initialize Fernet
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _voting_locked():
    s = LedgerStatus.objects.first()
    return bool(s and s.voting_locked)

def _decrypt_json(s):
    return json.loads(cipher_suite.decrypt(s.encode()).decode())

def _load_ballots(station_code=None):
    qs = BlockchainBlock.objects.order_by('block_index')
    if station_code:
        qs = qs.filter(station_code=station_code)
    return get_ballots_from_chain(qs, _decrypt_json)

def _station_name_map():
    # maps station_code like "19-D" to the same display name that
    # station_login stores in session['polling_station_name']
    mapping = {}
    for s in PollingStation.objects.all():
        mapping[f"{s.district_number:02d}-{s.division_code}"] = str(s)
    return mapping

_qr_mongo_client = None

UUID_REGEX = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')

def _get_qr_database():
    """Returns the MongoDB database for QR verification."""
    global _qr_mongo_client
    if not getattr(settings, 'QR_MONGO_URI', None):
        return None
    try:
        if _qr_mongo_client is None:
            _qr_mongo_client = pymongo.MongoClient(
                settings.QR_MONGO_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
            )
        return _qr_mongo_client[settings.QR_DB]
    except Exception as exc:
        print(f"[QR DB ERROR] Could not connect to QR Mongo cluster: {exc}")
        _qr_mongo_client = None
        return None

def _get_qr_collection():
    """Returns the MongoDB collection for QR code verification, reusing client connection."""
    db = _get_qr_database()
    if db is None:
        return None
    try:
        existing = db.list_collection_names()
        coll_name = settings.QR_COLLECTION
        if coll_name in existing:
            return db[coll_name]
        if 'qr_codes' in existing:
            return db['qr_codes']
        if 'qr_code' in existing:
            return db['qr_code']
        return db[coll_name]
    except Exception as exc:
        print(f"[QR DB ERROR] Could not get collection: {exc}")
        return None

def _resolve_qr_document(raw_input):
    """
    Intelligently resolves a QR document from raw input in any format:
    1. Direct UUID string (e.g. 720daa51-7a05-4de6-9dab-49abc649e7b5)
    2. URL containing a UUID token
    3. JSON payload containing {'qr_token': '...'}, {'token': '...'}, or {'id': '...'}
    4. JSON payload containing {'nic': '...'} (resolved via verification_logs)
    5. Raw NIC string (e.g. 200200302540)
    """
    db = _get_qr_database()
    if db is None:
        return None, None
    coll = _get_qr_collection()
    if coll is None:
        return None, None

    raw = raw_input.strip()

    # 1. Direct match on qr_token
    doc = coll.find_one({'qr_token': raw})
    if doc:
        return doc, doc.get('qr_token')

    # 2. Extract UUID pattern from string or URL
    uuid_match = UUID_REGEX.search(raw)
    if uuid_match:
        token = uuid_match.group(0)
        doc = coll.find_one({'qr_token': token})
        if doc:
            return doc, token

    # 3. Check if raw input is JSON
    parsed_json = None
    if (raw.startswith('{') and raw.endswith('}')) or (raw.startswith('[') and raw.endswith(']')):
        try:
            parsed_json = json.loads(raw)
        except Exception:
            pass

    if isinstance(parsed_json, dict):
        for field in ['qr_token', 'token', 'token_id', 'id', 'uuid']:
            val = parsed_json.get(field)
            if val:
                val_str = str(val).strip()
                doc = coll.find_one({'qr_token': val_str})
                if doc:
                    return doc, doc.get('qr_token')
                uuid_m = UUID_REGEX.search(val_str)
                if uuid_m:
                    doc = coll.find_one({'qr_token': uuid_m.group(0)})
                    if doc:
                        return doc, doc.get('qr_token')

        nic = parsed_json.get('nic') or parsed_json.get('NIC') or parsed_json.get('nic_no')
        if nic:
            doc = _find_qr_by_nic(db, coll, str(nic).strip())
            if doc:
                return doc, doc.get('qr_token')

    # 4. Check if raw input itself is an NIC number
    clean_nic = raw.replace('"', '').replace("'", "").strip()
    if re.match(r'^[0-9]{9,12}[vVxX]?$', clean_nic):
        doc = _find_qr_by_nic(db, coll, clean_nic)
        if doc:
            return doc, doc.get('qr_token')

    return None, None

def _find_qr_by_nic(db, qr_coll, nic):
    """Finds the corresponding qr_codes document linked to an NIC's verification log."""
    try:
        # Check direct NIC field on qr_codes if present
        direct_doc = qr_coll.find_one({'nic': nic})
        if direct_doc:
            return direct_doc

        vlog = db['verification_logs'].find_one({'nic': nic, 'verified': True}, sort=[('_id', -1)])
        if not vlog:
            vlog = db['verification_logs'].find_one({'nic': nic}, sort=[('_id', -1)])
        if vlog:
            doc = qr_coll.find_one({'_id': {'$gte': vlog['_id']}}, sort=[('_id', 1)])
            if doc:
                return doc
    except Exception as e:
        print(f"[NIC RESOLUTION ERROR] {e}")
    return None




def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _write_audit(event_type, request=None, station_name=None, details=''):
    try:
        AuditLog.objects.create(
            event_type=event_type,
            ip_address=_get_client_ip(request) if request else None,
            station_name=station_name,
            details=details,
        )
    except Exception as exc:
        print(f"[AUDIT ERROR] Could not write audit log: {exc}")


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------


def station_login_required(view_func):
    """Requires an active polling-station session."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.session.get('polling_station_id'):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Please log in with your Polling Station key to continue.')
        return redirect('station_login')
    return _wrapped


# ---------------------------------------------------------------------------
# Party helpers (unchanged)
# ---------------------------------------------------------------------------

def get_party_color(party_name):
    colors = {
        "National People's Power": "#A91D62",
        "Sri Lanka Podujana Peramuna": "#800020",
        "United National Party": "#008000",
        "Samagi Jana Balawegaya": "#008000",
        "Sri Lanka Freedom Party": "#0000FF",
        "Independent": "#808080",
        "Sarvajana Balaya": "#0066CC",
        "Mawbima Janatha Pakshaya": "#0066CC",
        "Ape Janabala Pakshaya": "#FF6B35",
        "Arunalu People's Front": "#4ECDC4",
        "Democratic United National Front": "#008000",
        "Democratic Unity Alliance": "#1A535C",
        "Jana Setha Peramuna": "#FFD700",
        "Jathika Sangwardhena Peramuna": "#8B4513",
        "Nawa Sama Samaja Party": "#D62828",
        "Nawa Sihala Urumaya": "#FF8C00",
        "New Independent Front": "#20B2AA",
        "People's Struggle Alliance (Jana Aragala Sandhanaya)": "#9370DB",
        "Samabima Party": "#DC143C",
        "Socialist Equality Party": "#8B0000",
        "Socialist Party of Sri Lanka": "#FF1493",
        "Socialist People's Forum": "#4B0082",
        "Sri Lanka Labour Party": "#4169E1",
        "National Democratic Front": "#FF4500",
        "United Lanka People's Party": "#8B008B",
        "United Lanka Podujana Party": "#8B008B",
        "United National Freedom Front": "#DAA520",
        "United Socialist Party": "#B22222",
        "New Democratic Front": "#4682B4",
    }
    return colors.get(party_name, "#666666")


def get_party_symbol(party_name):
    if not party_name:
        return None
    symbols = {
        "Samagi Jana Balawegaya": "Samagi Jana Balawegaya.png",
        "Sri Lanka Podujana Peramuna": "Sri Lanka Podujana Peramuna.png",
        "National People's Power": "National People's Power.png",
        "Sri Lanka Freedom Party": "Sri Lanka Freedom Party.png",
        "United National Party": "United National Party.png",
        "Mawbima Janatha Pakshaya": "Mawbima Janatha Pakshaya.png",
        "Ape Janabala Pakshaya": "Ape Janabala Pakshaya.png",
        "Arunalu People's Front": "Arunalu People's Front.png",
        "Democratic United National Front": "Democratic United National Front.png",
        "Democratic Unity Alliance": "Democratic Unity Alliance.png",
        "Jana Setha Peramuna": "Jana Setha Peramuna.png",
        "Jathika Sangwardhena Peramuna": "Jathika Sangwardhena Peramuna.png",
        "Nawa Sama Samaja Party": "Nawa Sama Samaja Party.png",
        "Nawa Sihala Urumaya": "Nawa Sihala Urumaya.png",
        "New Independent Front": "New Independent Front.png",
        "People's Struggle Alliance (Jana Aragala Sandhanaya)": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "Samabima Party": "Samabima Party.png",
        "Socialist Equality Party": "Socialist Equality Party.png",
        "Socialist Party of Sri Lanka": "Socialist Party of Sri Lanka.png",
        "Socialist People's Forum": "Samabima Party.png",
        "Sri Lanka Labour Party": "Sri Lanka Labour Party.png",
        "National Democratic Front": "National Democratic Front.png",
        "United Lanka People's Party": "United Lanka People's Party.png",
        "United Lanka Podujana Party": "United Lanka People's Party.png",
        "United National Freedom Front": "United National Freedom Front.png",
        "United Socialist Party": "United Socialist Party.png",
        "New Democratic Front": "new democratic front.png",
    }
    normalized_aliases = {
        "people's struggle alliance (jana aragala sandhanaya)": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "people's struggle alliance": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "peoples struggle alliance": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "jana aragala sandhanaya": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
    }
    symbol = symbols.get(party_name)
    if symbol:
        return symbol
    return normalized_aliases.get(party_name.strip().lower(), None)


def get_candidate_sort_priority(candidate):
    """
    Sort priority to ensure the 1st row of the voting dashboard displays:
    1. Anura Dissanayake
    2. Dilith Jayaweera
    3. Namal Rajapaksa
    4. Sajith Premadasa
    """
    text = f"{candidate.ballot_name or ''} {candidate.full_name or ''} {candidate.party_name or ''}".lower()
    
    if ('anura' in text and 'dissanayake' in text) or 'anura' in text:
        return 0
    if 'dilith' in text or 'jayaweera' in text:
        return 1
    if 'namal' in text or 'rajapak' in text:
        return 2
    if 'sajith' in text or 'premadasa' in text:
        return 3
    
    # Party fallback
    if 'national people' in text or 'npp' in text:
        return 0
    if 'mawbima' in text or 'mjp' in text:
        return 1
    if 'podujana' in text or 'slpp' in text:
        return 2
    if 'samagi' in text or 'sjb' in text:
        return 3
        
    return 100


# ---------------------------------------------------------------------------
# Main voting views
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
@station_login_required
def index(request):
    """Main voting ballot — only accessible after polling station login."""
    if _voting_locked():
        return HttpResponse(
            'Voting is paused: integrity check failed. Contact the presiding officer.',
            status=503)

    candidates_qs = Candidate.objects.all()
    candidates = []
    for c in candidates_qs:
        c.color = get_party_color(c.party_name)
        symbol_filename = get_party_symbol(c.party_name)
        c.party_symbol_url = (
            f"{settings.MEDIA_URL}party_symbols/{symbol_filename}" if symbol_filename else None
        )
        name_parts = c.full_name.split()
        c.short_name = f"{name_parts[0]} {name_parts[-1]}" if len(name_parts) >= 2 else c.full_name
        candidates.append(c)

    # Sort candidates with 1st row priority: Anura Dissanayake, Dilith Jayaweera, Namal Rajapaksa, Sajith Premadasa
    candidates.sort(key=lambda c: (get_candidate_sort_priority(c), c.ballot_name or c.full_name))

    station_name = request.session.get('polling_station_name', '')
    
    # Calculate expiry timestamp to pass to JS countdown
    expiry_date = request.session.get_expiry_date()
    expiry_timestamp = expiry_date.timestamp() * 1000  # Convert to milliseconds for JS

    return render(request, 'voting/index.html', {
        'candidates': candidates,
        'station_name': station_name,
        'expiry_timestamp': expiry_timestamp,
    })


def submit_vote(request):
    """
    Submit a vote. Requires active station session.
    The terminal stays logged in all day (polling master logs in once at 7 AM).
    has_voted is set to True during submission to prevent double-click double-votes,
    then reset to False after success so the NEXT voter can use the same terminal.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    # Must have an active station session
    station_id   = request.session.get('polling_station_id')
    station_name = request.session.get('polling_station_name', 'Unknown')
    if not station_id:
        return JsonResponse(
            {'status': 'error', 'message': 'Polling station session not active.'},
            status=403,
        )

    if _voting_locked():
        return JsonResponse(
            {'status': 'error',
             'message': 'Voting is paused: integrity check failed. Contact the presiding officer.'},
            status=503)

    # Guard against duplicate concurrent POST (double-click protection only)
    if request.session.get('vote_in_progress'):
        return JsonResponse(
            {'status': 'error', 'message': 'A vote submission is already in progress.'},
            status=429,
        )

    try:
    
        request.session['vote_in_progress'] = True
        request.session.save()

        data = json.loads(request.body)
        preferences = data.get('preferences', {})

        if not preferences:
            request.session['vote_in_progress'] = False
            request.session.save()
            return JsonResponse({'status': 'error', 'message': 'No preferences selected'}, status=400)

        # Fetch station for code
        try:
            station = PollingStation.objects.get(id=station_id)
            station_code = f"{station.district_number:02d}-{station.division_code}"
        except PollingStation.DoesNotExist:
            station_code = 'XX'

        # Encrypt twice with a fixed timestamp of 0 so no creation time is
        # exposed. Fernet uses a random IV, so the two ciphertexts differ and
        # nothing links the vote row to the block.
        json_str     = json.dumps(preferences)
        vote_cipher  = cipher_suite.encrypt_at_time(json_str.encode(), 0).decode()
        block_cipher = cipher_suite.encrypt_at_time(json_str.encode(), 0).decode()

        # 1) Authoritative record: the ledger block (retry on index collision)
        appended = False
        for _attempt in range(5):
            try:
                with _blockchain_lock:
                    next_index   = get_next_block_index(BlockchainBlock)
                    prev_hash    = get_chain_tip_hash(BlockchainBlock)
                    block_fields = build_block_fields(
                        block_index   = next_index,
                        station_code  = station_code,
                        preferences   = preferences,
                        previous_hash = prev_hash,
                        ciphertext    = block_cipher,
                    )
                    BlockchainBlock.objects.create(**block_fields)
                appended = True
                break
            except (IntegrityError, DuplicateKeyError):
                continue
        if not appended:
            raise RuntimeError('Could not append ledger block')

        # 2) Cross-check copy in the vote collection
        try:
            Vote.objects.create(
                preferences=vote_cipher,
                polling_station=station_name,
                station_code=station_code,
            )
        except Exception as copy_err:
            _write_audit(
                AuditLog.EventType.ERROR,
                request=request,
                station_name=station_name,
                details=f'Vote copy write failed after block append: {copy_err}',
            )


        # Mark verified QR token as used in MongoDB Atlas
        voter_qr_token = request.session.get('voter_qr_token')
        if voter_qr_token:
            try:
                coll = _get_qr_collection()
                if coll:
                    coll.update_one({'qr_token': voter_qr_token}, {'$set': {'used': True}})
            except Exception as q_err:
                print(f"[QR CONSUME ERROR] Could not mark QR token used: {q_err}")
            request.session.pop('voter_qr_token', None)

        # Reset lock — terminal is ready for the NEXT voter
        request.session['vote_in_progress'] = False
        request.session.save()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        # Always release the lock so the terminal isn't stuck
        request.session['vote_in_progress'] = False
        request.session.save()
        _write_audit(
            AuditLog.EventType.ERROR,
            request=request,
            station_name=station_name,
            details=str(e),
        )
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Station login / logout
# ---------------------------------------------------------------------------

def station_login(request):
    """
    Polling master logs in once at the start of the voting session (e.g. 7 AM).
    The session then stays active for the entire day.
    """
    if request.session.get('polling_station_id'):
        destination = request.GET.get('destination', 'voting')
        if destination == 'results':
            return redirect('station_results')
        return redirect('qr_verification')

    if request.method == 'POST':
        login_key = request.POST.get('login_key', '').strip()
        destination = request.POST.get('destination', 'voting')

        try:
            station = PollingStation.objects.get(login_key=login_key, is_active=True)
            # Establish station session
            request.session['polling_station_id']       = str(station.id)
            request.session['polling_station_name']     = str(station)
            request.session['polling_station_district'] = station.district_name
            request.session['polling_station_division'] = station.division_name
            request.session['vote_in_progress']         = False
            
            # Polling hours are 7 AM to 4 PM (9 hours). Expire the session exactly after 9 hours.
            request.session.set_expiry(9 * 3600)
            
            request.session.save()

            _write_audit(
                AuditLog.EventType.STATION_LOGIN,
                request=request,
                station_name=str(station),
                details=f"Station session started ({destination}): {station.district_name} / {station.division_name}",
            )
            messages.success(request, f'Station "{station}" logged in successfully.')
            
            if destination == 'results':
                return redirect('station_results')
            return redirect('qr_verification')

        except PollingStation.DoesNotExist:
            _write_audit(
                AuditLog.EventType.LOGIN_FAILED,
                request=request,
                details=f"Invalid login key attempt ({destination}): {login_key[:8]}***",
            )
            messages.error(request, 'Invalid or inactive station key. Please try again.')
            return render(request, 'voting/login.html', {'active_tab': destination})

    active_tab = request.GET.get('tab', 'station')
    return render(request, 'voting/login.html', {'active_tab': active_tab})


def station_logout(request):
    """End the polling station day session."""
    station_name = request.session.get('polling_station_name', 'Unknown')
    _write_audit(
        AuditLog.EventType.STATION_LOGOUT,
        request=request,
        station_name=station_name,
    )
    for key in ['polling_station_id', 'polling_station_name', 'polling_station_district',
                'polling_station_division', 'has_voted']:
        request.session.pop(key, None)
    request.session.save()
    messages.success(request, 'Polling station session ended.')
    return redirect('station_login')


@station_login_required
def qr_verification(request):
    """
    Voter QR Code Optical Verification Window.
    Displayed after polling station key authentication to scan issued voter tokens.
    """
    station_name = request.session.get('polling_station_name', '')
    station_district = request.session.get('polling_station_district', '')
    station_division = request.session.get('polling_station_division', '')

    expiry_date = request.session.get_expiry_date()
    expiry_timestamp = expiry_date.timestamp() * 1000 if expiry_date else 0

    dist_abbr = station_district[:3].upper() if station_district else 'STN'
    div_abbr = station_division[:3].upper() if station_division else '01'
    terminal_code = f"SL-EC-{dist_abbr}-{div_abbr}-VOTING-01"

    # Fetch available unused QR codes for quick operator selection/testing
    sample_qrs = []
    try:
        coll = _get_qr_collection()
        if coll:
            sample_qrs = [doc.get('qr_token') for doc in coll.find({'used': False}).limit(10) if doc.get('qr_token')]
    except Exception as e:
        print(f"[QR FETCH ERROR] {e}")

    return render(request, 'voting/qr_verification.html', {
        'station_name': station_name,
        'station_district': station_district,
        'station_division': station_division,
        'terminal_code': terminal_code,
        'expiry_timestamp': expiry_timestamp,
        'sample_qrs': sample_qrs,
    })


@station_login_required
def verify_qr_token(request):
    """
    AJAX endpoint to verify a scanned or entered QR token against MongoDB
    Election_Management_System.qr_codes collection.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        raw_token = data.get('qr_token', '').strip()
        if not raw_token:
            return JsonResponse({'status': 'invalid', 'message': 'QR token is empty'}, status=400)

        coll = _get_qr_collection()
        if coll is None:
            return JsonResponse({'status': 'error', 'message': 'QR Database connection failed'}, status=500)

        # Resolve document from raw token, UUID pattern, JSON payload, or NIC
        doc, token_str = _resolve_qr_document(raw_token)
        if not doc:
            _write_audit(
                AuditLog.EventType.LOGIN_FAILED,
                request=request,
                station_name=request.session.get('polling_station_name'),
                details=f"Unrecognized QR token scanned: {raw_token[:16]}***",
            )
            return JsonResponse({
                'status': 'invalid',
                'message': 'QR කේතය හඳුනාගත නොහැක / Invalid or Unrecognized QR Code',
            })

        actual_token = doc.get('qr_token') or token_str

        if doc.get('used') is True:
            _write_audit(
                AuditLog.EventType.LOGIN_FAILED,
                request=request,
                station_name=request.session.get('polling_station_name'),
                details=f"Attempted reuse of QR token: {actual_token[:8]}***",
            )
            return JsonResponse({
                'status': 'used',
                'message': 'මෙම QR කේතය දැනටමත් භාවිතා කර ඇත / QR Code Already Used',
            })

        # Token is valid and unused! Mark as used immediately in MongoDB Atlas
        try:
            coll.update_one({'_id': doc['_id']}, {'$set': {'used': True}})
            if actual_token:
                coll.update_one({'qr_token': actual_token}, {'$set': {'used': True}})
        except Exception as up_err:
            print(f"[QR UPDATE ERROR] Failed to mark QR as used in MongoDB: {up_err}")

        # Store in session
        request.session['voter_qr_token'] = actual_token
        request.session.save()

        _write_audit(
            AuditLog.EventType.STATION_LOGIN,
            request=request,
            station_name=request.session.get('polling_station_name'),
            details=f"Voter QR token verified and marked used: {actual_token[:8]}***",
        )

        return JsonResponse({
            'status': 'success',
            'token': actual_token,
            'message': 'අනුමත කරන ලදී / Authorization Confirmed',
            'redirect_url': '/voting/',
        })


    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)



# ---------------------------------------------------------------------------
# Station results — polling master views their own station's votes
# ---------------------------------------------------------------------------

@station_login_required
def station_results(request):
    """
    Read-only results view scoped to the active polling station.
    Accessible to the polling master after voting ends without re-auth.
    """
    station_name = request.session.get('polling_station_name', '')
    station_id = request.session.get('polling_station_id')
    station_code = None
    if station_id:
        try:
            station = PollingStation.objects.get(id=station_id)
            station_code = f"{station.district_number:02d}-{station.division_code}"
        except Exception:
            pass

    candidates_qs = Candidate.objects.all()
    ballots, bad_blocks = _load_ballots(station_code)

    results_data = []
    for candidate in candidates_qs:
        c_id   = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        for b in ballots:
            prefs = b['prefs']
            if prefs.get('1') == c_id:
                counts[1] += 1
            if prefs.get('2') == c_id:
                counts[2] += 1
            if prefs.get('3') == c_id:
                counts[3] += 1

        symbol_filename = get_party_symbol(candidate.party_name)
        results_data.append({
            'name': candidate.ballot_name or candidate.full_name,
            'party': candidate.party_name or 'Independent',
            'color': get_party_color(candidate.party_name),
            'party_symbol_url': (
                f"{settings.MEDIA_URL}party_symbols/{symbol_filename}" if symbol_filename else None
            ),
            'counts': counts,
            'total_1st': counts[1],
        })

    results_data.sort(key=lambda x: x['total_1st'], reverse=True)

    first_count = sum(r['counts'][1] for r in results_data)
    second_count = sum(r['counts'][2] for r in results_data)
    third_count = sum(r['counts'][3] for r in results_data)

    # Full integrity and reconciliation checks
    from .blockchain import (
        verify_chain as _verify_chain,
        reconcile_votes_with_chain as _reconcile_votes,
    )
    all_blocks = list(BlockchainBlock.objects.order_by('block_index'))
    chain_is_valid, chain_error = _verify_chain(all_blocks)

    reconcile_ok, reconcile_info = _reconcile_votes(Vote.objects.all(), all_blocks, _decrypt_json)

    ledger_status = LedgerStatus.objects.first()

    errors = []
    if not chain_is_valid:
        errors.append(chain_error or 'Blockchain sequence or hash tampered')
    if bad_blocks:
        errors.append(f'Corrupted block contents detected: Block(s) {bad_blocks}')
    if not reconcile_ok:
        v_diff = reconcile_info.get('votes_without_block', 0)
        b_diff = reconcile_info.get('blocks_without_vote', 0)
        u_diff = reconcile_info.get('undecryptable_votes', 0)
        reconcile_parts = []
        if v_diff:
            reconcile_parts.append(f'{v_diff} vote(s) in database do not match ledger')
        if b_diff:
            reconcile_parts.append(f'{b_diff} block(s) in ledger have no matching vote')
        if u_diff:
            reconcile_parts.append(f'{u_diff} undecryptable vote(s)')
        errors.append('Vote record mismatch: ' + (', '.join(reconcile_parts) or str(reconcile_info)))
    if ledger_status and not ledger_status.ok and ledger_status.detail:
        if ledger_status.detail not in errors:
            errors.append(ledger_status.detail)

    ledger_ok = (len(errors) == 0)
    integrity_error = ' | '.join(errors) if errors else ''

    return render(request, 'voting/station_results.html', {
        'results': results_data,
        'station_name': station_name,
        'total_votes': len(ballots),
        'first_count': first_count,
        'second_count': second_count,
        'third_count': third_count,
        'ledger_ok': ledger_ok,
        'integrity_error': integrity_error,
        'chain_is_valid': chain_is_valid,
        'chain_error': chain_error,
        'ledger_status': ledger_status,
        'bad_blocks_count': len(bad_blocks),
        'excluded_blocks': bad_blocks,
    })


def results(request):
    """
    Global results view across all polling stations.
    """
    candidates_qs = Candidate.objects.all()
    ballots, bad_blocks = _load_ballots()

    results_data = []
    for candidate in candidates_qs:
        c_id   = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        for b in ballots:
            prefs = b['prefs']
            if prefs.get('1') == c_id:
                counts[1] += 1
            if prefs.get('2') == c_id:
                counts[2] += 1
            if prefs.get('3') == c_id:
                counts[3] += 1

        symbol_filename = get_party_symbol(candidate.party_name)
        results_data.append({
            'name': candidate.ballot_name or candidate.full_name,
            'party': candidate.party_name or 'Independent',
            'color': get_party_color(candidate.party_name),
            'party_symbol_url': (
                f"{settings.MEDIA_URL}party_symbols/{symbol_filename}" if symbol_filename else None
            ),
            'counts': counts,
            'total_1st': counts[1],
        })

    results_data.sort(key=lambda x: x['total_1st'], reverse=True)

    from .blockchain import (
        verify_chain as _verify_chain,
        reconcile_votes_with_chain as _reconcile_votes,
    )
    all_blocks = list(BlockchainBlock.objects.order_by('block_index'))
    chain_is_valid, chain_error = _verify_chain(all_blocks)

    reconcile_ok, reconcile_info = _reconcile_votes(Vote.objects.all(), all_blocks, _decrypt_json)

    ledger_status = LedgerStatus.objects.first()

    errors = []
    if not chain_is_valid:
        errors.append(chain_error or 'Blockchain sequence or hash tampered')
    if bad_blocks:
        errors.append(f'Corrupted block contents detected: Block(s) {bad_blocks}')
    if not reconcile_ok:
        v_diff = reconcile_info.get('votes_without_block', 0)
        b_diff = reconcile_info.get('blocks_without_vote', 0)
        u_diff = reconcile_info.get('undecryptable_votes', 0)
        reconcile_parts = []
        if v_diff:
            reconcile_parts.append(f'{v_diff} vote(s) in database do not match ledger')
        if b_diff:
            reconcile_parts.append(f'{b_diff} block(s) in ledger have no matching vote')
        if u_diff:
            reconcile_parts.append(f'{u_diff} undecryptable vote(s)')
        errors.append('Vote record mismatch: ' + (', '.join(reconcile_parts) or str(reconcile_info)))
    if ledger_status and not ledger_status.ok and ledger_status.detail:
        if ledger_status.detail not in errors:
            errors.append(ledger_status.detail)

    ledger_ok = (len(errors) == 0)
    integrity_error = ' | '.join(errors) if errors else ''

    return render(request, 'voting/results.html', {
        'results': results_data,
        'total_votes': len(ballots),
        'ledger_ok': ledger_ok,
        'integrity_error': integrity_error,
        'chain_is_valid': chain_is_valid,
        'chain_error': chain_error,
        'ledger_status': ledger_status,
        'bad_blocks_count': len(bad_blocks),
        'excluded_blocks': bad_blocks,
    })


# ---------------------------------------------------------------------------
# Success page
# ---------------------------------------------------------------------------

def success(request):
    """Render the vote confirmation screen."""
    return render(request, 'voting/success.html')

