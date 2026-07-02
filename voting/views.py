from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from functools import wraps
from candidates.models import Candidate
from .models import Vote, PollingStation, TempVoterId, AuditLog
import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from cryptography.fernet import Fernet
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import update_last_login
from django.utils import timezone

# Disconnect the default update_last_login signal to prevent MongoDB ObjectId save error
user_logged_in.disconnect(update_last_login)

# Initialize Fernet
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

# Fallback credentials for MongoDB deployments where updating Django auth users can fail.
FALLBACK_RESULTS_USERNAME = "admin"
FALLBACK_RESULTS_PASSWORD = "admin"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

def results_login_required(view_func):
    """Requires the super-admin session (results admin)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated or request.session.get('results_admin_authenticated'):
            return view_func(request, *args, **kwargs)
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    return _wrapped


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


# ---------------------------------------------------------------------------
# Main voting views
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
@station_login_required
def index(request):
    """Main voting ballot — only accessible after polling station login."""
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

    # Guard against duplicate concurrent POST (double-click protection only)
    if request.session.get('vote_in_progress'):
        return JsonResponse(
            {'status': 'error', 'message': 'A vote submission is already in progress.'},
            status=429,
        )

    try:
        # Lock against double-click for this submission cycle
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

        # Encrypt preferences
        json_str       = json.dumps(preferences)
        encrypted_data = cipher_suite.encrypt(json_str.encode()).decode()

        # Store vote with station tag
        Vote.objects.create(
            preferences=encrypted_data,
            polling_station=station_name,
            station_code=station_code,
        )

        _write_audit(
            AuditLog.EventType.VOTE_CAST,
            request=request,
            station_name=station_name,
            details=f"Vote cast at station {station_code}",
        )

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
        return redirect('voting_index')

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
            return redirect('voting_index')

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

    candidates_qs = Candidate.objects.all()
    station_votes = Vote.objects.filter(polling_station=station_name)

    decrypted_votes = []
    for vote in station_votes:
        try:
            decrypted_data = cipher_suite.decrypt(vote.preferences.encode()).decode()
            decrypted_votes.append(json.loads(decrypted_data))
        except Exception as e:
            print(f"[DECRYPT ERROR] {e}")
            continue

    results_data = []
    for candidate in candidates_qs:
        c_id   = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        for prefs in decrypted_votes:
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

    return render(request, 'voting/station_results.html', {
        'results': results_data,
        'station_name': station_name,
        'total_votes': len(decrypted_votes),
        'first_count': first_count,
        'second_count': second_count,
        'third_count': third_count,
    })


# ---------------------------------------------------------------------------
# Global results (super-admin) — unchanged + per-station breakdown
# ---------------------------------------------------------------------------

@results_login_required
def results(request):
    candidates_qs = Candidate.objects.all()
    results_data  = []
    all_votes     = Vote.objects.all()

    decrypted_votes = []
    for vote in all_votes:
        try:
            decrypted_data = cipher_suite.decrypt(vote.preferences.encode()).decode()
            decrypted_votes.append({
                'prefs': json.loads(decrypted_data),
                'station': vote.polling_station or 'Unknown',
            })
        except Exception as e:
            print(f"Error decrypting vote: {e}")
            continue

    # Aggregate by station
    station_breakdown = {}
    for entry in decrypted_votes:
        stn = entry['station']
        if stn not in station_breakdown:
            station_breakdown[stn] = {}

    for candidate in candidates_qs:
        c_id   = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        for entry in decrypted_votes:
            prefs = entry['prefs']
            stn   = entry['station']
            name  = candidate.ballot_name or candidate.full_name

            for pref_rank in [1, 2, 3]:
                if prefs.get(str(pref_rank)) == c_id:
                    counts[pref_rank] += 1
                    # Station breakdown
                    if name not in station_breakdown[stn]:
                        station_breakdown[stn][name] = {1: 0, 2: 0, 3: 0}
                    station_breakdown[stn][name][pref_rank] += 1

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

    return render(request, 'voting/results.html', {
        'results': results_data,
        'station_breakdown': station_breakdown,
    })


# ---------------------------------------------------------------------------
# Success page
# ---------------------------------------------------------------------------

def success(request):
    return render(request, 'voting/success.html')


# ---------------------------------------------------------------------------
# Results admin login / logout
# ---------------------------------------------------------------------------

def user_login(request):
    """Handle user login with MongoDB-compatible session management."""
    if request.user.is_authenticated:
        return redirect('voting_index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username == FALLBACK_RESULTS_USERNAME and password == FALLBACK_RESULTS_PASSWORD:
            request.session['results_admin_authenticated'] = True
            request.session.save()
            next_url = request.POST.get('next') or request.GET.get('next') or 'results'
            return redirect(next_url)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
            request.session.flush()
            request.session[SESSION_KEY]         = user._get_pk_val()
            request.session[BACKEND_SESSION_KEY] = user.backend
            request.session[HASH_SESSION_KEY]    = user.get_session_auth_hash()
            request.session.cycle_key()
            try:
                user.last_login = timezone.now()
                user.save()
            except Exception as e:
                print(f"Warning: Could not update last_login: {e}")
            request.session.save()
            request.user = user
            next_url = request.POST.get('next') or request.GET.get('next') or 'voting_index'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'voting/login.html', {'active_tab': 'admin'})


def user_logout(request):
    request.session.pop('results_admin_authenticated', None)
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')


# ---------------------------------------------------------------------------
# Temporary Voter ID management (stub for real ID system)
# ---------------------------------------------------------------------------

def _admin_required(view_func):
    """Requires results admin session."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated or request.session.get('results_admin_authenticated'):
            return view_func(request, *args, **kwargs)
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    return _wrapped


@_admin_required
def voter_id_list(request):
    """List all temporary voter IDs with search/filter."""
    query    = request.GET.get('q', '')
    district = request.GET.get('district', '')
    division = request.GET.get('division', '')
    has_voted = request.GET.get('has_voted', '')

    voters = TempVoterId.objects.all()
    if query:
        voters = [v for v in voters if query.lower() in v.voter_id.lower() or query.lower() in v.full_name.lower()]
    if district:
        voters = [v for v in voters if v.district == district]
    if division:
        voters = [v for v in voters if v.division == division]
    if has_voted == 'yes':
        voters = [v for v in voters if v.has_voted]
    elif has_voted == 'no':
        voters = [v for v in voters if not v.has_voted]

    # Distinct districts/divisions for filter dropdowns
    all_voters  = TempVoterId.objects.all()
    districts   = sorted(set(v.district for v in all_voters))
    divisions   = sorted(set(v.division for v in all_voters))

    total = TempVoterId.objects.all().count()
    voted = sum(1 for v in TempVoterId.objects.all() if v.has_voted)

    return render(request, 'voting/voter_id_list.html', {
        'voters':    voters,
        'query':     query,
        'district':  district,
        'division':  division,
        'has_voted': has_voted,
        'districts': districts,
        'divisions': divisions,
        'total':     total,
        'voted':     voted,
    })


@_admin_required
def voter_id_create(request):
    """Create a single temporary voter ID."""
    # Build district/division choices from polling stations
    stations  = PollingStation.objects.filter(is_active=True)
    districts = sorted(set((s.district_number, s.district_name) for s in stations), key=lambda x: x[0])
    divisions_by_district = {}
    for s in stations:
        divisions_by_district.setdefault(s.district_name, []).append(s.division_name)

    if request.method == 'POST':
        voter_id  = request.POST.get('voter_id', '').strip().upper()
        full_name = request.POST.get('full_name', '').strip()
        district  = request.POST.get('district', '').strip()
        division  = request.POST.get('division', '').strip()

        if not all([voter_id, full_name, district, division]):
            messages.error(request, 'All fields are required.')
        elif TempVoterId.objects.filter(voter_id=voter_id).first():
            messages.error(request, f'Voter ID "{voter_id}" already exists.')
        else:
            TempVoterId.objects.create(
                voter_id=voter_id,
                full_name=full_name,
                district=district,
                division=division,
            )
            _write_audit(
                AuditLog.EventType.VOTER_CREATED,
                request=request,
                details=f"Created voter ID: {voter_id} ({full_name})",
            )
            messages.success(request, f'Voter ID "{voter_id}" created successfully.')
            return redirect('voter_id_list')

    return render(request, 'voting/voter_id_form.html', {
        'districts': districts,
        'divisions_json': json.dumps(divisions_by_district),
        'action': 'Create',
    })


@_admin_required
def voter_id_bulk(request):
    """Bulk create voter IDs from a pasted CSV block."""
    stations  = PollingStation.objects.filter(is_active=True)
    districts = sorted(set((s.district_number, s.district_name) for s in stations), key=lambda x: x[0])
    divisions_by_district = {}
    for s in stations:
        divisions_by_district.setdefault(s.district_name, []).append(s.division_name)

    if request.method == 'POST':
        raw_data = request.POST.get('bulk_data', '')
        district = request.POST.get('district', '').strip()
        division = request.POST.get('division', '').strip()

        created = 0
        skipped = 0
        errors  = []

        for line_num, line in enumerate(raw_data.strip().splitlines(), 1):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                errors.append(f"Line {line_num}: need at least voter_id, full_name")
                skipped += 1
                continue
            voter_id  = parts[0].upper()
            full_name = parts[1]
            # Allow overriding district/division per line
            row_district = parts[2] if len(parts) > 2 else district
            row_division  = parts[3] if len(parts) > 3 else division

            if not voter_id or not full_name:
                skipped += 1
                continue

            if TempVoterId.objects.filter(voter_id=voter_id).first():
                skipped += 1
                continue

            try:
                TempVoterId.objects.create(
                    voter_id=voter_id,
                    full_name=full_name,
                    district=row_district,
                    division=row_division,
                )
                created += 1
            except Exception as e:
                errors.append(f"Line {line_num}: {e}")
                skipped += 1

        if created:
            _write_audit(
                AuditLog.EventType.VOTER_CREATED,
                request=request,
                details=f"Bulk created {created} voter IDs",
            )
            messages.success(request, f'Created {created} voter ID(s). Skipped {skipped}.')
        else:
            messages.warning(request, f'No records created. Skipped {skipped}.')

        if errors:
            messages.error(request, 'Errors: ' + '; '.join(errors[:5]))

        return redirect('voter_id_list')

    return render(request, 'voting/voter_id_bulk.html', {
        'districts': districts,
        'divisions_json': json.dumps(divisions_by_district),
    })


@_admin_required
def voter_id_delete(request, voter_id):
    """Delete a single voter ID."""
    voter = get_object_or_404(TempVoterId, voter_id=voter_id)
    if request.method == 'POST':
        _write_audit(
            AuditLog.EventType.VOTER_DELETED,
            request=request,
            details=f"Deleted voter ID: {voter.voter_id} ({voter.full_name})",
        )
        voter.delete()
        messages.success(request, f'Voter ID "{voter_id}" deleted.')
        return redirect('voter_id_list')
    return render(request, 'voting/voter_id_confirm_delete.html', {'voter': voter})
