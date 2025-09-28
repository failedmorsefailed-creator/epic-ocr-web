# Voter List OCR → Excel (Tesseract + Google Vision)

A Streamlit web app that extracts printed + handwritten voter-roll data (Odia & English) into a structured Excel sheet. Supports phone camera capture and file upload.

---

## Files included
- `app.py` — Streamlit app (select Tesseract or Google Vision OCR)
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `.gitignore`

---

## Quick start (local, without Docker)

1. Install Tesseract (system package):
   - **Ubuntu/Debian**
     ```bash
     sudo apt update
     sudo apt install -y tesseract-ocr libtesseract-dev
     # try installing Oriya (ori) if available:
     sudo apt install -y tesseract-ocr-ori || true
     # if 'ori' not available, download traineddata:
     sudo mkdir -p /usr/share/tessdata
     sudo curl -L -o /usr/share/tessdata/ori.traineddata \
       https://github.com/tesseract-ocr/tessdata/raw/main/ori.traineddata
     ```
   - **macOS (Homebrew)**
     ```bash
     brew install tesseract
     # copy ori.traineddata into /usr/local/share/tessdata if needed
     ```

2. Create and activate Python virtualenv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
