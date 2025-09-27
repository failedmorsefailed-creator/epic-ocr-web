from flask import Flask, request, render_template_string, send_file, redirect, url_for
import os
from ocr_engine import process_file_to_excel
from io import BytesIO

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

INDEX_HTML = '''
<!doctype html>
<title>OCR → Excel</title>
<h2>Upload image or PDF with a table</h2>
<form method=post enctype=multipart/form-data action="/upload">
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
<p>Or run test image: <a href="/test">Use example image</a></p>
'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/test')
def test():
    # Use the developer-provided image in container
    sample = '/mnt/data/1000389622.jpg'
    if not os.path.exists(sample):
        return 'Sample image not found on server at /mnt/data/1000389622.jpg', 404
    out_buf = process_file_to_excel(sample)
    out_buf.seek(0)
    return send_file(
        out_buf,
        as_attachment=True,
        download_name='extracted_table.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    f = request.files['file']
    if f.filename == '':
        return redirect(url_for('index'))
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
    f.save(save_path)
    out_buf = process_file_to_excel(save_path)
    out_buf.seek(0)
    return send_file(
        out_buf,
        as_attachment=True,
        download_name='extracted_table.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
