FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# collectstatic needs settings to load; these build-time values are never used at runtime.
RUN DJANGO_SECRET_KEY=build-only DJANGO_BUILD=1 python manage.py collectstatic --noinput \
    && useradd --system --uid 1000 --no-create-home app \
    && chown -R app /app
# Run as an unprivileged user, never root.
USER app

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn servicehub.wsgi -b 0.0.0.0:8000 -w 3 --access-logfile -"]
