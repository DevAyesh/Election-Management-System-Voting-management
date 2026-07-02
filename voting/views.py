from django.shortcuts import render, redirect
from django.http import JsonResponse
from candidates.models import Candidate
from .models import Vote
import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from cryptography.fernet import Fernet
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import update_last_login
from django.utils import timezone

# Disconnect the default update_last_login signal to prevent MongoDB ObjectId save error
user_logged_in.disconnect(update_last_login)

# Initialize Fernet
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

def get_party_color(party_name):
    colors = {
        # Major Parties - Official Colors
        "National People's Power": "#A91D62",  # Purple/Magenta (National People's Power)
        "Sri Lanka Podujana Peramuna": "#800020",  # Maroon (Sri Lanka Podujana Peramuna)
        "United National Party": "#008000",  # Green (United National Party)
        "Samagi Jana Balawegaya": "#008000",  # Green (Samagi Jana Balawegaya - also uses yellow)
        "Sri Lanka Freedom Party": "#0000FF",  # Blue (Sri Lanka Freedom Party)
        "Independent": "#808080",  # Grey
        
        # Sarvajana Balaya / Mawbima Janatha Pakshaya
        "Sarvajana Balaya": "#0066CC",  # Blue (Dilith Jayaweera's alliance)
        "Mawbima Janatha Pakshaya": "#0066CC",  # Blue
        
        # Other Parties
        "Ape Janabala Pakshaya": "#FF6B35",  # Orange
        "Arunalu People's Front": "#4ECDC4",  # Turquoise
        "Democratic United National Front": "#008000",  # Green
        "Democratic Unity Alliance": "#1A535C",  # Dark Teal
        "Jana Setha Peramuna": "#FFD700",  # Gold
        "Jathika Sangwardhena Peramuna": "#8B4513",  # Brown
        "Nawa Sama Samaja Party": "#D62828",  # Red
        "Nawa Sihala Urumaya": "#FF8C00",  # Dark Orange
        "New Independent Front": "#20B2AA",  # Light Sea Green
        "People's Struggle Alliance (Jana Aragala Sandhanaya)": "#9370DB",  # Medium Purple
        "Samabima Party": "#DC143C",  # Crimson
        "Socialist Equality Party": "#8B0000",  # Dark Red
        "Socialist Party of Sri Lanka": "#FF1493",  # Deep Pink
        "Socialist People's Forum": "#4B0082",  # Indigo
        "Sri Lanka Labour Party": "#4169E1",  # Royal Blue
        "National Democratic Front": "#FF4500",  # Orange Red
        "United Lanka People's Party": "#8B008B",  # Dark Magenta
        "United Lanka Podujana Party": "#8B008B",  # Dark Magenta
        "United National Freedom Front": "#DAA520",  # Goldenrod
        "United Socialist Party": "#B22222",  # Fire Brick
        "New Democratic Front": "#4682B4"  # Steel Blue
    }
    return colors.get(party_name, "#666666")



def get_party_symbol(party_name):
    """Map party names to their symbol image filenames"""
    if not party_name:
        return None
    
    symbols = {
        # Short code mappings (for backward compatibility)
        "Samagi Jana Balawegaya": "Samagi Jana Balawegaya.png",
        "Sri Lanka Podujana Peramuna": "Sri Lanka Podujana Peramuna.png",
        "National People's Power": "National People's Power.png",
        "Sri Lanka Freedom Party": "Sri Lanka Freedom Party.png",
        "United National Party": "United National Party.png",
        "Mawbima Janatha Pakshaya": "Mawbima Janatha Pakshaya.png",
        
        # Full party name mappings (matching database entries)
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
        "Socialist People's Forum": "Samabima Party.png",  # Assuming this maps to Samabima
        "Sri Lanka Labour Party": "Sri Lanka Labour Party.png",
        "National Democratic Front": "National Democratic Front.png",
        "United Lanka People's Party": "United Lanka People's Party.png",
        # Keep old name mapping for compatibility with existing data
        "United Lanka Podujana Party": "United Lanka People's Party.png",
        "United National Freedom Front": "United National Freedom Front.png",
        "United Socialist Party": "United Socialist Party.png",
        "New Democratic Front": "new democratic front.png",
    }
    
    # Normalized aliases to handle minor name variations
    normalized_aliases = {
        "people's struggle alliance (jana aragala sandhanaya)": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "people's struggle alliance": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "peoples struggle alliance": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
        "jana aragala sandhanaya": "People's Struggle Alliance (Jana Aragala Sandhanaya).png",
    }
    
    symbol = symbols.get(party_name)
    if symbol:
        return symbol
    
    normalized_name = party_name.strip().lower()
    return normalized_aliases.get(normalized_name, None)

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

@login_required
def results(request):
    candidates_qs = Candidate.objects.all()
    results_data = []
    
    all_votes = Vote.objects.all()
    
    decrypted_votes = []
    for vote in all_votes:
        try:
            decrypted_data = cipher_suite.decrypt(vote.preferences.encode()).decode()
            prefs = json.loads(decrypted_data)
            decrypted_votes.append(prefs)
        except Exception as e:
            print(f"Error decrypting vote {vote.id}: {e}")
            continue
    
    for candidate in candidates_qs:
        c_id = str(candidate.id)
        counts = {1: 0, 2: 0, 3: 0}
        
        for prefs in decrypted_votes:
            
            if prefs.get('1') == c_id:
                counts[1] += 1
            
            if prefs.get('2') == c_id:
                counts[2] += 1
           
            if prefs.get('3') == c_id:
                counts[3] += 1
                
        symbol_filename = get_party_symbol(candidate.party_name)
        if symbol_filename:
            party_symbol_url = f"{settings.MEDIA_URL}party_symbols/{symbol_filename}"
        else:
            party_symbol_url = None
        
        results_data.append({
            'name': candidate.ballot_name or candidate.full_name,
            'party': candidate.party_name or "Independent",
            'color': get_party_color(candidate.party_name),
            'party_symbol_url': party_symbol_url,
            'counts': counts,
            'total_1st': counts[1]
        })
    
    # Sort by 1st preference count descending
    results_data.sort(key=lambda x: x['total_1st'], reverse=True)
    
    return render(request, 'voting/results.html', {'results': results_data})


def success(request):
    """Display the trilingual vote submission success page"""
    return render(request, 'voting/success.html')

def user_login(request):
    """Handle user login with MongoDB-compatible session management"""
    if request.user.is_authenticated:
        return redirect('voting_index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Manually manage session to avoid MongoDB ObjectId save error
            # Instead of using login(request, user), we manually create the session
            from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
            
            # Clear existing session
            request.session.flush()
            
            # Manually set session data
            request.session[SESSION_KEY] = user._get_pk_val()
            request.session[BACKEND_SESSION_KEY] = user.backend
            request.session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            
            # Rotate session key to prevent session fixation attacks
            request.session.cycle_key()
            
            # Update last_login without using update_fields (which causes the error)
            try:
                user.last_login = timezone.now()
                # Use save() without update_fields to avoid the MongoDB pk error
                user.save()
            except Exception as e:
                # If save fails, user is still logged in via session
                print(f"Warning: Could not update last_login: {e}")
                pass
            
            # IMPORTANT: Save the session to persist it
            request.session.save()
            
            # Manually set request.user
            request.user = user
            
            next_url = request.POST.get('next') or request.GET.get('next') or 'voting_index'
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    
    return render(request, 'voting/login.html')

def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')

