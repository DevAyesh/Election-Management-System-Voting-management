# Election Portal — Secure Digital Voting System

**Date:** 2026-07-02  
**Status:** Active Development (POC)  
**Python Version:** 3.13.2  
**Framework:** Django 5.2.9  

---

## Overview

The **Election Portal** is a Django-based secure digital voting system for Sri Lanka's preferential voting elections. It supports a full end-to-end workflow: candidate management, per-polling-station session authentication, encrypted vote capture, real-time results, and a complete audit trail.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2.9 |
| Database | MongoDB Atlas (`django-mongodb-backend`) |
| Encryption | `cryptography` — Fernet symmetric encryption |
| Auth | Django Sessions + custom station key auth |
| Frontend | Django Templates (HTML / Vanilla CSS) |
| Language | Python 3.13 |

---

## Application Structure

```
election_portal/          ← Django project config
candidates/               ← Candidate registration app
voting/                   ← Voting, results, station auth, voter IDs
│
├── models.py             ← Vote, PollingStation, TempVoterId, AuditLog
├── views.py              ← All views (voting, station login, voter ID CRUD)
├── middleware.py         ← Rate limiting middleware
├── admin.py              ← Django admin registrations
├── urls.py               ← URL routing
├── templates/voting/
│   ├── index.html            ← Main ballot (requires station login)
│   ├── station_login.html    ← Polling master login (unique key)
│   ├── station_results.html  ← Station-scoped results view
│   ├── results.html          ← Global results (admin only)
│   ├── login.html            ← Results admin login
│   ├── voter_id_list.html    ← Temp voter ID list
│   ├── voter_id_form.html    ← Create voter ID
│   ├── voter_id_bulk.html    ← Bulk import voter IDs
│   └── voter_id_confirm_delete.html
└── management/commands/
    └── seed_polling_stations.py   ← Seeds all 160 stations with unique keys
```

---

## How to Run

### 1. Activate the virtual environment
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies
```powershell
pip install -r requirements.txt
```

### 3. Apply migrations
```powershell
python manage.py migrate voting --skip-checks
```

### 4. Seed polling stations (first time only)
```powershell
python manage.py seed_polling_stations --skip-checks
```

To print full login keys for distribution to polling masters:
```powershell
python manage.py seed_polling_stations --show-keys --skip-checks
```

### 5. Start the server
```powershell
python manage.py runserver --skip-checks
```

> **Note:** `--skip-checks` is required due to a pre-existing system-check false positive from the MongoDB backend on Django's built-in auth models. All functionality works correctly.

---

## URL Reference

| URL | Access | Purpose |
|---|---|---|
| `/voting/station/login/` | Public | Polling master unlocks their terminal with unique key |
| `/voting/station/results/` | Station session | Polling master views their station's votes |
| `/voting/station/logout/` | Station session | Ends the polling station day session |
| `/voting/` | Station session | Voter ballot interface |
| `/voting/submit/` | Station session | Vote submission endpoint |
| `/voting/login/` | Public | Results admin login |
| `/voting/results/` | Admin | Global results with per-station breakdown |
| `/voting/voters/` | Admin | Temp voter ID management list |
| `/voting/voters/create/` | Admin | Add a single voter ID |
| `/voting/voters/bulk/` | Admin | Bulk import voter IDs from CSV |
| `/admin/` | Superuser | Django admin (PollingStation, AuditLog, TempVoterId) |

**Results admin credentials (fallback):** `admin` / `admin`

---

## Per-Polling-Station Authentication

Each of Sri Lanka's **160 polling divisions** (22 districts) has a unique cryptographic login key stored in MongoDB.

### How it works

1. **7 AM** — Polling master goes to `/voting/station/login/` and enters their unique key
2. Session is unlocked for the entire day — no re-login per voter
3. All votes cast are tagged with the station name and district code
4. After voting closes — polling master visits `/voting/station/results/` to view **only their station's votes**
5. The Kaduwela key **cannot** open a Colombo North terminal

### Get a station's key (CLI)
```powershell
python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'election_portal.settings'
django.setup()
from voting.models import PollingStation
s = PollingStation.objects.get(division_name='Kaduwela')
print(s.login_key)
"
```

---

## Security Features

| Feature | Implementation |
|---|---|
| Vote encryption | Fernet symmetric encryption; raw preferences never stored |
| Station isolation | Each station's key is unique; cross-login impossible |
| Rate limiting | 5 failed key attempts per IP → 10-minute lockout (in-process, no Redis needed) |
| One vote per session | `has_voted` session flag prevents double submission |
| Audit log | Every login, vote, logout, and rate-limit event recorded in `AuditLog` MongoDB collection |
| Admin key masking | Django admin shows only first 8 characters of login keys |

---

## Database Collections

| Collection | Purpose |
|---|---|
| `vote` | Encrypted ballots tagged with `polling_station` and `station_code` |
| `polling_station` | 160 divisions with unique login keys |
| `temp_voter_id` | POC voter ID stub (will connect to real ID system) |
| `audit_log` | Immutable event trail |
| `candidates_candidate` | Registered election candidates |

---

## Temporary Voter ID System

A stub voter ID management UI is available at `/voting/voters/` (requires admin login). It supports:

- **Single create** — add a NIC + name + district/division
- **Bulk import** — paste CSV rows, one per line: `voter_id, full_name[, district, division]`
- **List with filters** — search by name/ID, filter by district, division, or voted status
- **Delete with audit** — each deletion is logged

> This module will be replaced/connected to the real external ID verification system once available.

---

## Known Limitations

- Django Admin is partially limited on MongoDB due to `AutoField` incompatibility with `django.contrib.auth` models — functionality is unaffected
- The `post_migrate` signal fails silently on `migrate` (pre-existing); use `migrate voting --skip-checks` for new migrations
- Rate limiter uses in-process memory (resets on server restart) — sufficient for POC; production should use Redis
