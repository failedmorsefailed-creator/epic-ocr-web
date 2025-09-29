FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
tesseract-ocr \
tesseract-ocr-eng \
tesseract-ocr-ori \
poppler-utils \
ghostscript \
qpdf \
build-essential \
libjpeg-dev \
zlib1g-dev \
libssl-dev \
&& rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ./app /app/app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
