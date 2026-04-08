FROM python:3.11-slim

WORKDIR /app

# System deps for SpaCy + sentence-transformers
RUN apt-get update && apt-get install -y \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download SpaCy model
RUN python -m spacy download en_core_web_sm

COPY . .

# Create data directory for FAISS persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "sentinel.gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
