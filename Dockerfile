# Dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TESSDATA_PREFIX=/usr/share/tessdata

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    wget \
    git \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    libjpeg-dev \
    libpng-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Try to install Oriya traineddata; fallback to download from tessdata repo
RUN apt-get update || true
RUN if apt-cache show tesseract-ocr-ori >/dev/null 2>&1; then \
      apt-get install -y --no-install-recommends tesseract-ocr-ori || true; \
    else \
      mkdir -p /usr/share/tessdata && \
      curl -L -o /usr/share/tessdata/ori.traineddata \
        https://github.com/tesseract-ocr/tessdata/raw/main/ori.traineddata || true; \
    fi && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8501

ENV STREAMLIT_SERVER_ENABLECORS=false
ENV PYTHONUNBUFFERED=1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
