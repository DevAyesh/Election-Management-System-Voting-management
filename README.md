# Project Report: Election Portal

**Date:** 2025-12-05
**Status:** Operational / Development
**Python Version:** 3.13.2

## 1. Project Overview
The **Election Portal** is a Django-based web application designed to manage candidate registrations for an election. It currently features a public-facing registration form that collects candidate details, validates eligibility (age), and stores the data in a MongoDB database.

## 2. Technology Stack
-   **Backend Framework:** Django 5.2.9
-   **Database:** MongoDB (Database name: `election_portal_db`)
-   **Database Connector:** `django-mongodb-backend` (Modern connector compatible with Django 5+ and Python 3.13)
-   **Language:** Python 3.13
-   **Frontend:** Django Templates (HTML/CSS)
-   **Encryption:** `cryptography` library (Fernet symmetric encryption)

## 3. Application Structure
The project consists of a main project folder `election_portal` and one application `candidates`.

### Core Components
-   **`candidates/models.py`**: Defines the `Candidate` data model.
    -   Uses `ObjectIdAutoField` for MongoDB compatibility.
    -   Fields: NIC, Name, Sinhala Name, DOB, Nomination Type, Party, Symbol (Image).
    -   Validation: Enforces a minimum age of 35 years.
-   **`candidates/views.py`**: Handles the logic.
    -   `register_candidate`: Renders the form and handles POST submissions.
    -   `registration_success`: Displays a success message.
-   **`candidates/forms.py`**: ModelForm for the Candidate model.
-   **`voting/models.py`**: Defines the `Vote` model.
    -   Stores encrypted preferences.
-   **`voting/views.py`**: Handles voting logic.
    -   `index`: Renders the voting interface.
    -   `submit_vote`: Encrypts and saves votes.
    -   `results`: Decrypts and counts votes.
-   **`election_portal/settings.py`**: Project configuration.
    -   Configured for MongoDB.
    -   **Note**: Django Admin and Auth apps are currently **disabled** to ensure compatibility with the non-relational MongoDB backend without complex user model customization.

## 4. Database Configuration
The project is configured to connect to a local MongoDB instance.

-   **Engine**: `django_mongodb_backend`
-   **Host**: `localhost`
-   **Port**: `27017`
-   **Database Name**: `election_portal_db`

## 5. Recent Updates & Fixes
### Issue: MongoDB Connection & Python 3.13 Compatibility
**Problem**: The project initially failed to connect to MongoDB because the `djongo` connector is outdated and incompatible with Python 3.13 and Django 5.x.
**Solution**:
1.  Migrated dependencies to `django-mongodb-backend`.
2.  Updated `settings.py` to use the new engine.
3.  Modified the `Candidate` model to explicitly use `ObjectIdAutoField` for primary keys (required for MongoDB).
4.  Disabled conflicting Django contrib apps (`admin`, `auth`, `messages`) to resolve `AutoField` and context processor errors.

### Issue: 500 Internal Server Error
**Problem**: The templates tried to access `user` and `messages` context variables, which were unavailable because the respective apps were disabled.
**Solution**: Removed `auth` and `messages` context processors from `settings.py`.

### Feature: Voting System Integration
**Goal**: Integrate the standalone `vote.py` interface into the Django app.
**Implementation**:
1.  Created `voting` app.
2.  Ported Tkinter UI to HTML/CSS.
3.  Implemented `Vote` model with encryption.
4.  Added `cryptography` dependency and configured `ENCRYPTION_KEY`.
5.  Exposed interface at `/voting/`.

## 6. How to Run
1.  **Activate Virtual Environment**:
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
2.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```
3.  **Start MongoDB**: Ensure MongoDB Compass or the MongoDB service is running locally.
4.  **Run Server**:
    ```powershell
    python manage.py runserver
    ```
5.  **Access App**: 
    -   Registration: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
    -   Voting: [http://127.0.0.1:8000/voting/](http://127.0.0.1:8000/voting/)
    -   Results: [http://127.0.0.1:8000/voting/results/](http://127.0.0.1:8000/voting/results/)

## 7. Known Limitations & Future Work
-   **Admin Panel**: The built-in Django Admin is disabled. To manage data, you will need to use MongoDB Compass or build custom management views.
-   **User Authentication**: The default Django User model is disabled. If login functionality is needed, a custom User model compatible with MongoDB will need to be implemented.
