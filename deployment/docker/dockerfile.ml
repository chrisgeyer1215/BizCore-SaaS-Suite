# deployment/docker/Dockerfile.ml

FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements/ml.txt /app/requirements/ml.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements/ml.txt

# Copy application code
COPY . /app

# Set environment variables
ENV PYTHONPATH="/app"
ENV DJANGO_SETTINGS_MODULE="config.settings.production"

# Create ML models directory
RUN mkdir -p /app/media/ml_models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ml/health/ || exit 1

# Start command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "aiohttp.GunicornWebWorker", "config.wsgi:application"]