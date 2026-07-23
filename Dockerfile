FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright Chromium & Postgres client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt-get/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium headless browser binaries for Scrapling DynamicFetcher
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Execution command
CMD ["python", "run_pipeline.py"]
