# Lightweight Python base image
FROM python:3.11-slim

# Avoid interactive prompts when installing packages
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file first (better cache usage)
COPY requirements.txt .

# Install system dependencies required for pandas, psycopg2, and Excel handling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        python3-dev \
        build-essential \
        libffi-dev \
        libssl-dev \
        curl \
        && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the code
COPY . .

# Expose the FastAPI port
EXPOSE 8484

# Startup command (adjusted to the app path)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8484"]
