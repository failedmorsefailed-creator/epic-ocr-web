FROM python:3.11-slim

# Install system deps for Tesseract + poppler (for PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    pkg-config \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
