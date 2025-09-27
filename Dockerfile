FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y tesseract-ocr poppler-utils libglib2.0-0 libsm6 libxrender1 libxext6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
