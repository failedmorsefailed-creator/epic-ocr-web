from flask import Flask, render_template, request, send_file
import pytesseract
from PIL import Image
import os
import pandas as pd
import io

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ocr', methods=['POST'])
def ocr():
    if 'image' not in request.files:
        return "No file part"

    file = request.files['image']
    if file.filename == '':
        return "No selected file"

    filepath = os.path.join('uploads', file.filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(filepath)

    # Perform OCR with data output
    img = Image.open(filepath)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DATAFRAME)

    # Clean DataFrame (drop NaNs, empty)
    df = data[['level','page_num','block_num','par_num','line_num','word_num','left','top','width','height','conf','text']].dropna(subset=['text'])
    df = df[df['text'].str.strip() != '']

    # Save to Excel in memory
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    os.remove(filepath)  # delete temp file

    return send_file(
        output,
        as_attachment=True,
        download_name='ocr_output.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
