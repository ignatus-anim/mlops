# Inference service image
FROM python:3.11-slim

# Arguments
ARG PIP_NO_CACHE_DIR=1

# Set workdir
WORKDIR /app

# Install system packages required by pandas/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt /app/

# Install Python dependencies from requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source code
COPY . /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Expose Flask port
EXPOSE 6001

# Default command
CMD ["python", "inference_api.py"]