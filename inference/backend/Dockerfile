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

# Copy inference code
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir \
        flask \
        boto3 \
        numpy \
        pandas \
        scikit-learn \
        sqlalchemy \
        psycopg2-binary

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Expose Flask port
EXPOSE 6001

# Default command
CMD ["python", "inference_api.py"]