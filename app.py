import os
import io
import json
import re
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# ---- load service account from env var ----
sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not sa_json:
    raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable. Paste the service account JSON content into that env var on Render / locally.")
service_account_info = json.loads(sa_json)

SCOPES = ['https://www.googleapis.com/auth/drive']
creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)

ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'tif', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def upload_to_drive_and_ocr(file_bytes: bytes, filename: str) -> str:
    """Upload the file bytes to Drive and force-convert to Google Doc for OCR, then export text."""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        mimetype = 'application/pdf'
    elif ext in ('jpg', 'jpeg'):
        mimetype = 'image/jpeg'
    elif ext in ('png',):
        mimetype = 'image/png'
    else:
        mimetype = 'application/octet-stream'

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
    metadata = {
        'name': filename,
        'mimeType': 'application/vnd.google-apps.document'  # ask Drive to convert -> Google Doc
    }

    created = drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
    file_id = created.get('id')

    # export as plain text
    request = drive_service.files().export_media(fileId=file_id, mimeType='text/plain')
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    text = fh.getvalue().decode('utf-8', errors='replace')

    # cleanup: delete temp google doc
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except Exception:
        pass

    return text

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or f.filename == '':
            flash("Please choose a PDF or image file.", "danger")
            return redirect(request.url)
        if not allowed_file(f.filename):
            flash("File type not allowed. Allowed: pdf, png, jpg, jpeg, tif, tiff", "danger")
            return redirect(request.url)

        ac_no = request.form.get('ac_no', '33').strip()
        part_no = request.form.get('part_no', '153').strip()
        booth_name = request.form.get('booth', f'BOOTH_{part_no}')

        filename = secure_filename(f.filename)
        file_bytes = f.read()

        # 1) upload to Drive, convert to doc (OCR), export text
        text = upload_to_drive_and_ocr(file_bytes, filename)

        # 2) lightweight parsing heuristics
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # EPIC patterns:
        epic_re = re.compile(r'\b(?:[A-Z]{1,4}\d{4,}|\b[A-Z]{1,4}/\d{1,3}/\d{1,4}/\d{1,6})\b')
        rows = []
        serial_counter = 1

        for i, line in enumerate(lines):
            m = epic_re.search(line)
            if m:
                epic_no = m.group(0)
                # search for category A/B on same or next few lines
                category = ''
                for j in range(i, min(i+4, len(lines))):
                    cm = re.search(r'\b([AB])\b', lines[j])
                    if cm:
                        category = cm.group(1)
                        break
                # relation words (common)
                relation = ''
                for j in range(i, min(i+6, len(lines))):
                    rm = re.search(r'\b(SON|DAU|DAUGHTER|WIFE|HUSBAND|S/O|D/O)\b', lines[j], flags=re.I)
                    if rm:
                        relation = rm.group(0)
                        break
                old_ac = old_part = old_serial = ''
                for j in range(i, min(i+6, len(lines))):
                    nums = re.findall(r'\b(\d{2,4})\b', lines[j])
                    # if three or more numeric tokens are on same line, assume old AC/part/serial
                    if len(nums) >= 3:
                        old_ac, old_part, old_serial = nums[:3]
                        break

                rows.append({
                    'EPIC_NO': epic_no,
                    'AC_NO': ac_no,
                    'PART_NO': part_no,
                    'SERIAL_NO_IN_PART': serial_counter,
                    'Category': category,
                    'Relation': relation,
                    'OLD_AC_NO': old_ac,
                    'OLD_PART_NO': old_part,
                    'OLD_PART_SERIAL_NO': old_serial
                })
                serial_counter += 1

        if not rows:
            flash("No EPIC-like entries detected. Try a clearer scan or use Google Vision API for better results.", "warning")
            return render_template('index.html')

        df = pd.DataFrame(rows, columns=[
            'EPIC_NO','AC_NO','PART_NO','SERIAL_NO_IN_PART','Category','Relation','OLD_AC_NO','OLD_PART_NO','OLD_PART_SERIAL_NO'
        ])

        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=booth_name[:31])
        out.seek(0)

        return send_file(out,
                         as_attachment=True,
                         download_name=f'{booth_name}_epic_output.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                         )

    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
