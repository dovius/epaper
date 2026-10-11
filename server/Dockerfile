# E-Paper Display Server
# Build: docker build -t epaper-server .
# Run:   docker compose up -d   (see docker-compose.yml)

FROM python:3.12-slim

# Python output straight to `docker logs`
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Timezone data, so TZ=Europe/Vilnius works for the clock and timestamps.
# (Pillow wheels already bundle libjpeg/zlib/freetype.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p static templates

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/device/config').raise_for_status()" || exit 1

# Run the server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
