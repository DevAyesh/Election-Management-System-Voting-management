from django.shortcuts import render
from django.http import JsonResponse
from candidates.models import Candidate
from .models import Vote
import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from cryptography.fernet import Fernet

# Initialize Fernet
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

def get_party_color(party_name):
    colors = {
        "SJB": "#008000", # Green
        "UNP": "#008000", # Green
        "SLPP": "#800000", # Maroon
        "NPP": "#cc0000", # Red
        "SLFP": "#0000FF", # Blue
        "Independent": "#808080" # Grey
    }
    return colors.get(party_name, "#666666")

def get_party_symbol(party_name):
    """Map party names to their symbol image filenames"""
    symbols = {
        "SJB": "SJB.png",
        "SLPP": "SLPP.png",
        "NPP": "NPP.png",
        "SLFP": "SLFP.png",
        "UNP": "Democratic United National Front.png",  # Assuming UNP uses this
        "MJP": "MJP.png",
    }
    return symbols.get(party_name, None)

@ensure_csrf_cookie
def index(request):
    candidates_qs = Candidate.objects.all()
    candidates = []
    for c in candidates_qs:
        # Add color and party symbol attributes dynamically for the template
        c.color = get_party_color(c.party_name)
        symbol_filename = get_party_symbol(c.party_name)
        if symbol_filename:
            c.party_symbol_url = f"{settings.MEDIA_URL}party_symbols/{symbol_filename}"
        else:
            c.party_symbol_url = None
        
        # Extract short English name (first and last name only)
        name_parts = c.full_name.split()
        if len(name_parts) >= 2:
            c.short_name = f"{name_parts[0]} {name_parts[-1]}"
        else:
            c.short_name = c.full_name
        
        candidates.append(c)
        
    return render(request, 'voting/index.html', {'candidates': candidates})

def submit_vote(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            preferences = data.get('preferences', {})
            
            if not preferences:
                return JsonResponse({'status': 'error', 'message': 'No preferences selected'}, status=400)
            
            # Encrypt Preferences
            json_str = json.dumps(preferences)
            encrypted_data = cipher_suite.encrypt(json_str.encode()).decode()
            
            # Create Vote
            Vote.objects.create(preferences=encrypted_data)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

def results(request):
    candidates_qs = Candidate.objects.all()
    results_data = []
    
    # Fetch all votes once
    all_votes = Vote.objects.all()
    
    # Decrypt votes
    decrypted_votes = []
    for vote in all_votes:
        try:
            decrypted_data = cipher_suite.decrypt(vote.preferences.encode()).decode()
            prefs = json.loads(decrypted_data)
            decrypted_votes.append(prefs)
        except Exception as e:
            print(f"Error decrypting vote {vote.id}: {e}")
            # Skip invalid/unencrypted votes (e.g. from before encryption was added)
            continue
    
    for candidate in candidates_qs:
        c_id = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        
        for prefs in decrypted_votes:
            # Check rank 1
            if prefs.get('1') == c_id:
                counts[1] += 1
            # Check rank 2
            if prefs.get('2') == c_id:
                counts[2] += 1
            # Check rank 3
            if prefs.get('3') == c_id:
                counts[3] += 1
                
        results_data.append({
            'name': candidate.ballot_name or candidate.full_name,
            'party': candidate.party_name or "Independent",
            'color': get_party_color(candidate.party_name),
            'counts': counts,
            'total_1st': counts[1]
        })
    
    # Sort by 1st preference count descending
    results_data.sort(key=lambda x: x['total_1st'], reverse=True)
    
    return render(request, 'voting/results.html', {'results': results_data})

def success(request):
    """Display the trilingual vote submission success page"""
    return render(request, 'voting/success.html')
