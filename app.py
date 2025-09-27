from flask import Flask, request, render_template_string, send_file, redirect, url_for
import os
from ocr_engine import process_file_to_dataframe
import pandas as pd

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

PREVIEW_HTML = '''
<!doctype html>
<title>Preview - OCR → Excel</title>
<style>
  body { font-family: Arial, sans-serif; padding: 16px; }
  .topbar { margin-bottom:12px; }
  table { border-collapse: collapse; width: 100%; }
  table td, table th { border: 1px solid #ccc; padding: 6px; font-size: 12px; }
  pre { background: #f5f5f5; padding: 8px; max-height:200px; overflow:auto; }
</style>
<div class="topbar">
  <a href="/">⬅ Back</a> |
  <a href="{{ download_url }}">Download Excel</a>
</div>
<h3>Extracted table preview</h3>
<div>{{ table_html|safe }}</div>
<h4>OCR debug (truncated)</h4>
<pre>{{ debug }}</pre>
'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/test')
def test():
    # Uses the example file inside container (must exist)
    sample = '/mnt/data/1000389622.jpg'
    if not os.path.exists(sample):
        return 'Sample image not found at /mnt/data/1000389622.jpg', 404

    df, debug = process_file_to_dataframe(sample)
    filename = 'extracted_' + os.path.basename(sample).rsplit('.', 1)[0] + '.xlsx'
    out_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_excel(out_path, index=False, header=False)

    table_html = df.to_html(index=False, header=False)
    download_url = url_for('download_file', filename=filename)
    return render_template_string(PREVIEW_HTML, table_html=table_html, download_url=download_url, debug=debug[:4000])

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    f = request.files['file']
    if f.filename == '':
        return redirect(url_for('index'))

    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
    f.save(save_path)

    df, debug = process_file_to_dataframe(save_path)

    filename = 'extracted_' + os.path.basename(f.filename).rsplit('.', 1)[0] + '.xlsx'
    out_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_excel(out_path, index=False, header=False)

    table_html = df.to_html(index=False, header=False)
    download_url = url_for('download_file', filename=filename)
    return render_template_string(PREVIEW_HTML, table_html=table_html, download_url=download_url, debug=debug[:4000])

@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(path):
        return 'File not found', 404
    return send_file(path, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
