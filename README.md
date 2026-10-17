# Pet Donation

A Django project for managing pets available for adoption or donation.

## Features

- Email-based user registration and login
- Pet records with name, age, background, Google Maps URL, image, category, and availability status

## Setup

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Apply the database migrations and start the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in a browser. Registration is at `/register/` and login is at `/login/`.

For production, set the `DJANGO_SECRET_KEY` environment variable and set `DEBUG=False`.
