# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12.13

FROM python:${PYTHON_VERSION}-slim

WORKDIR /code

COPY backend/requirements-prod.txt backend/requirements-prod.txt
RUN pip3 install --no-cache-dir -r backend/requirements-prod.txt

COPY backend /code/backend
COPY frontend /code/frontend

WORKDIR /code/backend
ENV FLASK_APP=wsgi:app
ENV FLASK_ENV=production

EXPOSE 8080

CMD ["sh", "-c", "gunicorn -w 1 --timeout 120 -b 0.0.0.0:${PORT:-8080} wsgi:app"]
