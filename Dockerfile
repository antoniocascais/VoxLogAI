FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY transcriber.py .
COPY templates/ templates/
COPY LICENSE .

EXPOSE 5000

# Configure Gunicorn to forward logs to stdout with increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level=info", "--access-logfile=-", "--error-logfile=-", "--timeout", "300", "app:app"]
