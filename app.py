from flask import Flask, render_template, request
import pytesseract
from PIL import Image
import os

app = Flask(__name__)

# route for home page
@app.route('/')
def index():
    return render_template('index.html')

# route for OCR
@app.route('/ocr', methods=['POST'])
def ocr():
    if 'image' not in request.files:
        return "No file part"

    file = request.files['image']
    if file.filename == '':
        return "No selected file"

    # Save temporarily
    filepath = os.path.join("uploads", file.filename)
    os.makedirs("uploads", exist_ok=True)
    file.save(filepath)

    # Perform OCR
    text = pytesseract.image_to_string(Image.open(filepath))

    # Delete temp file
    os.remove(filepath)

    return f"<h2>Extracted Text:</h2><pre>{text}</pre>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
