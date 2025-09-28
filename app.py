import os
import tempfile
from flask import Flask, request, render_template_string, send_file
from google.cloud import vision
import pytesseract
from PIL import Image
import pandas as pd

# Flask app
app = Flask(__name__)

# HTML Upload UI
HTML_TEMPLATE = """
<!doctype html>
<title>OCR App</title>
<h1>Upload an image for OCR</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=image>
  <input type=submit value=Upload>
</form>
{% if table %}
  <h2>Extracted Data</h2>
  {{ table|safe }}
  <a href="/download">Download Excel</a>
{% endif %}
"""

# Save extracted data
extracted_data = None

# Google Vision OCR
def extract_text_google_vision(image_path):
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

# Tesseract OCR
def extract_text_tesseract(image_path):
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang="eng+ori")  # English + Odia

# Parse extracted text into structured rows (simplified example)
def parse_text_to_table(text):
    rows = []
    for line in text.split("\n"):
        if line.strip():
            rows.append([line.strip()])
    df = pd.DataFrame(rows, columns=["Extracted Text"])
    return df

@app.route("/", methods=["GET", "POST"])
def upload_image():
    global extracted_data
    if request.method == "POST":
        file = request.files["image"]
        if file:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file.save(tmp.name)

                # Try Vision first
                text = extract_text_google_vision(tmp.name)

                # Fallback to Tesseract if Vision fails
                if not text.strip():
                    text = extract_text_tesseract(tmp.name)

                extracted_data = parse_text_to_table(text)
                table_html = extracted_data.to_html(index=False)

                return render_template_string(HTML_TEMPLATE, table=table_html)

    return render_template_string(HTML_TEMPLATE)

@app.route("/download")
def download_excel():
    global extracted_data
    if extracted_data is None:
        return "No data available, please upload an image first."
    output_file = "output.xlsx"
    extracted_data.to_excel(output_file, index=False)
    return send_file(output_file, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
