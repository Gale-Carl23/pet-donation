# Service Hub

A field service and preventive-maintenance (PMS) system for a water treatment company. Office staff see which filters, membranes, UV lamps and tests are due at every customer, book visits and assign technicians. Technicians open their jobs on a phone, tick off the checklist, record TDS, pH and pressure, get the customer's name as sign-off and complete the job. Completing a job resets each serviced part's due date and produces a service report to send to the customer.

Built with Django 6.1 and PostgreSQL.

## Features

| Area | What it does |
|---|---|
| Overview | Components overdue or due within 14 days, which are already booked, today's visits, jobs completed this month |
| Schedule | All visits by day, filtered by technician and status |
| Field app | A technician's jobs for today, carried-over jobs and the next 7 days, with a phone-friendly job sheet |
| Job sheet | Checklist, water readings checked against PNSDW limits (pH 6.5–8.5, TDS ≤ 600 mg/L), RO salt-rejection check, parts used, notes, customer sign-off, copyable service report |
| Customers | Customers, their installed systems (RO, refilling station, softener, multimedia, UV) and each component's service interval |
| Reminders | A ready-to-send SMS or Viber message listing what's due |
| Settings | Company name, reminder wording, staff list, audit log (administrators only) |

### Roles

| Role | Can do |
|---|---|
| Administrator | Everything, plus settings, staff accounts (in the admin area) and the audit log |
| Office / dispatcher | Customers, systems, booking, rescheduling, cancelling, all jobs |
| Field technician | Only the jobs assigned to them: start, record readings, complete |

## Run it locally (Windows PowerShell)

```powershell
cd flowline-service-hub
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_DEBUG = "true"
python manage.py migrate
python manage.py seed_demo        # optional: sample customers, jobs and 4 demo accounts
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. `seed_demo` prints a temporary password for each demo account, and each account must choose a new password at first sign-in. Without `seed_demo`, create the first administrator with `python manage.py createsuperuser`.

Local development uses SQLite. Production uses PostgreSQL.

Run the tests with:

```powershell
$env:DJANGO_TESTING = "1"; $env:DJANGO_SECRET_KEY = "test"; $env:DJANGO_HTTPS = "false"; $env:DJANGO_ALLOWED_HOSTS = "testserver"
python manage.py test
```

## Deploy to production

1. Copy `.env.example` to `.env` and fill in every value. Generate the secret key with `python -c "import secrets; print(secrets.token_urlsafe(60))"` and use a long random database password.
2. Start the app and database with `docker compose up -d --build`. The app listens on `127.0.0.1:8000` only.
3. Put an HTTPS reverse proxy in front of it, such as Caddy, nginx with Let's Encrypt, or your host's load balancer.
4. Create the first administrator with `docker compose exec web python manage.py createsuperuser`.
5. Check the configuration with `docker compose exec web python manage.py check --deploy`. It should report no issues.
6. Set up daily database backups (`pg_dump`) and store them off the server.

The app refuses to start in production without `DJANGO_SECRET_KEY` and `DATABASE_URL`.

## Security

| Threat | Protection |
|---|---|
| Stolen or guessed passwords | Argon2 password hashing. Minimum 12 characters, with common and all-numeric passwords rejected. Temporary passwords must be changed at first sign-in. |
| Brute-force sign-in | django-axes locks an email + IP pair after 5 failed attempts for 30 minutes. All sign-ins and failures are logged. |
| Pages opened without signing in | `LoginRequiredMiddleware` makes every page require sign-in unless it explicitly opts out (only the sign-in page does). |
| Staff seeing more than they should | Role checks on every office and admin view. Technicians can only load their own jobs, and other jobs return "not found" so job numbers can't be probed. |
| Tampered forms | The system and customer of a booking come from the URL, not the form. Components must belong to that system. Readings have range limits. Closed jobs can't be edited. Every change is a POST. |
| Cross-site request forgery | Django CSRF tokens on every form. SameSite and HttpOnly cookies. Logout is POST-only. |
| Cross-site scripting | Templates escape all output. A strict Content Security Policy allows no inline scripts and no third-party scripts. |
| SQL injection | All database access goes through the Django ORM with parameterised queries. |
| Clickjacking | `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'`. |
| Snooping on the network | HTTPS redirect, HSTS for one year, and Secure cookies. |
| Session theft | Sessions end when the browser closes or after 10 hours. Changing a password signs out other sessions. |
| Leaked secrets | Secrets come only from environment variables. `.env` is git-ignored. `DEBUG` is off by default. |
| Admin area discovery | The admin lives at a secret path (`DJANGO_ADMIN_URL`) and needs an administrator account. |
| Lost accountability | An append-only audit log records who created, changed, completed or cancelled what, from which IP, plus every sign-in. |
| Server compromise | The container runs as a non-root user, with a read-only filesystem and no privilege escalation. The database is not exposed outside Docker. |
| Oversized requests | Request bodies are capped at 1 MB and there are no file uploads. |

Things still to do before go-live:

- Turn on two-factor sign-in for administrators, for example with `django-otp`.
- Turn on encrypted, automated off-site backups and test a restore.
- Register under the Philippine Data Privacy Act (RA 10173) if required, appoint a Data Protection Officer, and publish a privacy notice. The system stores customer names, phone numbers and addresses.
- Keep dependencies updated (`pip list --outdated`) and re-run `check --deploy` after each change.
