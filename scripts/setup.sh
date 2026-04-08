#!/bin/bash
set -e

echo "======================================"
echo "    Sentinel V3 Setup Script          "
echo "======================================"

echo "[1/4] Installing Python Requirements..."
pip install -r requirements.txt

echo "[2/4] Downloading NLP Models (Spacy)..."
python -m spacy download en_core_web_sm

echo "[3/4] Pre-caching HuggingFace Models for ML Risk Scorer and Sentinel Core..."
# Using python inline to pre-cache the models so FastAPI worker doesn't freeze/OOM on boot.
python -c "
import transformers
print('Downloading DistilBERT...')
transformers.pipeline('text-classification', model='distilbert-base-uncased')
print('Downloading T5 (Adversarial Rephrase)...')
transformers.AutoModelForSeq2SeqLM.from_pretrained('t5-small')
transformers.AutoTokenizer.from_pretrained('t5-small')
print('Downloading BART (Intent Classifier)...')
transformers.pipeline('zero-shot-classification', model='facebook/bart-large-mnli')
print('Models successfully downloaded and cached to ~/.cache/huggingface!')
" || { echo "Model download failed. Out of memory?"; exit 1; }

echo "[4/4] Environment Check..."
# We generate a default .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating default .env file..."
    cat > .env << EOL
KAFKA_BOOTSTRAP_SERVERS=localhost:29092
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://sentinel:password@localhost:5432/sentinel
METRICS_ENABLED=True
EOL
fi

echo "======================================"
echo "Setup Complete!"
echo "Make sure Docker is running, then start the infrastructure using:"
echo "    docker-compose up -d --build"
echo "Then boot up the gateway:"
echo "    fastapi run sentinel/gateway/main.py"
echo "======================================"
