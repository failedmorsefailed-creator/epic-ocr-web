# OCR to Excel - Flask app (Deployable to Render)

This repo provides a small Flask app that:
- Accepts an uploaded image or PDF.
- Uses OpenCV + pytesseract to detect tables and extract cell text.
- Exports results to Excel.

## Run locally (with Docker)

```bash
docker build -t ocr-to-excel .
docker run --rm -p 5000:5000 -v /mnt/data:/mnt/data ocr-to-excel
