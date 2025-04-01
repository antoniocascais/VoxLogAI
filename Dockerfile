FROM python:3.12-slim

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /bin/bash app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY transcriber.py .
COPY ocr.py .
COPY templates/ templates/
COPY LICENSE .

# Set correct permissions
RUN chown -R app:app /app

# Switch to non-root user
USER app

EXPOSE 5000

# Configure Gunicorn to forward logs to stdout with increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level=info", "--access-logfile=-", "--error-logfile=-", "--timeout", "300", "app:app"]
