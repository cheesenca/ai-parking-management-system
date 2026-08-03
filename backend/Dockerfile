FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging for Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Upgrade pip and install Python dependencies without caching
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code into the container
COPY . .

# Create non-root user for container security
RUN useradd -m appuser && chown -R appuser:appuser /backend
USER appuser

# Expose the API port
EXPOSE 8000

# Start the Uvicorn server to run the FastAPI/ASGI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]