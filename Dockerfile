# --- Builder stage: install Python deps with build tools ---
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
COPY app.py .

RUN pip install --no-cache-dir .

# --- Runtime stage: lean image with only runtime deps ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ src/
COPY app.py .
COPY pyproject.toml .

# Copy pre-built data artifacts (indexes, vectorstore, discovery report)
COPY data/discovery/ data/discovery/
COPY data/indexes/ data/indexes/
COPY data/vectorstore/ data/vectorstore/

EXPOSE 8501 8000

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.headless=true", "--server.address=0.0.0.0"]
