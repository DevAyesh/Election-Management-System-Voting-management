"""
RateLimitMiddleware
===================
Thread-safe in-process rate limiter. No Redis required.

Rules
-----
- /voting/station/login/  POST → max 5 attempts per IP per RATE_LIMIT_WINDOW seconds
- /voting/submit/         POST → 1 vote per session (enforced in view via session flag)

On breach: HTTP 429 JSON or redirect back with error message.
"""
import threading
import time
from collections import defaultdict
from django.http import JsonResponse
from django.conf import settings


# ---------------------------------------------------------------------------
# In-memory store:  ip_address  →  {'count': int, 'window_start': float}
# ---------------------------------------------------------------------------
_lock   = threading.Lock()
_store  = defaultdict(lambda: {'count': 0, 'window_start': time.time()})


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _is_rate_limited(ip: str, max_attempts: int, window_seconds: int) -> bool:
    """Return True if this IP has exceeded its allowance for this window."""
    now = time.time()
    with _lock:
        entry = _store[ip]
        if now - entry['window_start'] > window_seconds:
            # New window — reset
            entry['count']        = 1
            entry['window_start'] = now
            return False
        entry['count'] += 1
        return entry['count'] > max_attempts


class RateLimitMiddleware:
    """Applied globally but only rate-limits specific paths."""

    STATION_LOGIN_PATH = '/voting/station/login/'
    MAX_ATTEMPTS       = getattr(settings, 'RATE_LIMIT_STATION_LOGIN',    5)
    WINDOW_SECONDS     = getattr(settings, 'RATE_LIMIT_WINDOW_SECONDS', 600)  # 10 min

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == 'POST'
            and request.path == self.STATION_LOGIN_PATH
        ):
            ip = _get_client_ip(request)
            if _is_rate_limited(ip, self.MAX_ATTEMPTS, self.WINDOW_SECONDS):
                # Write audit log without crashing if DB not available yet
                try:
                    from .models import AuditLog
                    AuditLog.objects.create(
                        event_type='RATE_LIMITED',
                        ip_address=ip,
                        details=f"Too many station login attempts from {ip}",
                    )
                except Exception:
                    pass

                if request.headers.get('Accept', '').startswith('application/json'):
                    return JsonResponse(
                        {'status': 'error', 'message': 'Too many attempts. Try again in 10 minutes.'},
                        status=429,
                    )

                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(
                    request,
                    'Too many failed login attempts. Please wait 10 minutes before trying again.',
                )
                return redirect('station_login')

        return self.get_response(request)
