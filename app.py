import os
import io
import pandas as pd
from flask import Flask, render_template_string, request, send_file
from google.cloud import vision
import pytesseract
from PIL import Image

app = Flask(__name__)

# HTML template (very simple)
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>EPIC OCR Web</title>
</head>
<body>
    <h2>Upload EPIC Page Image</h2>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="image" accept="image/*" capture="environment">
        <button type="submit">Upload</button>
    </form>
    {% if table %}
        <h3>Extracted Data Preview</h3>
        {{ table|safe }}
        <form method="post" action="/download">
            <button type="submit">Download Excel</button>
        </form>
    {% endif %}
</body>
</html>
"""

# Store extracted dataframe temporarily
extracted_df = None

def extract_text_google(image_path):
    """Extract text using Google Vision API"""
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

def extract_text_tesseract(image_path):
    """Fallback OCR using pytesseract"""
    img = Image.open(image_path)
    return pytesseract.image_to_string(img)

@app.route("/", methods=["GET", "POST"])
def index():
    global extracted_df
    table_html = None

    if request.method == "POST":
        file = request.files["image"]
        if file:
            filepath = os.path.join("temp.jpg")
            file.save(filepath)

            # Try Google Vision first
            try:
                text = extract_text_google(filepath)
            except Exception:
                text = extract_text_tesseract(filepath)

            # Dummy parsing (replace with your parsing logic)
            rows = []
            for line in text.split("\n"):
                if line.strip():
                    rows.append({
                        "EPIC No.": line.strip(),
                        "AC No": "32 - Jashipur",
                        "PART No": "170",
                        "SERIAL No": "01",
                        "CATEGORY A/B": "A",
                        "RELATION OF THE ELECTOR": "",
                        "OLD AC No": "",
                        "OLD PART No": "",
                        "OLD PART SERIAL No": ""
                    })

            extracted_df = pd.DataFrame(rows)

            # Show preview
            table_html = extracted_df.to_html(index=False)

    return render_template_string(TEMPLATE, table=table_html)

@app.route("/download", methods=["POST"])
def download():
    global extracted_df
    if extracted_df is None:
        return "No data to download."
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        extracted_df.to_excel(writer, index=False, sheet_name="Sheet1")
    output.seek(0)

    return send_file(output,
                     as_attachment=True,
                     download_name="epic_data.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
