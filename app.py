# app.py
import os
import io
import re
from flask import Flask, render_template, request, jsonify, send_file
from pdf2image import convert_from_bytes
import pytesseract
import cv2
import numpy as np
import pandas as pd
from PIL import Image

app = Flask(__name__)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Patterns & helpers
EPIC_PATTERNS = [
    re.compile(r"[A-Z]{3}\d{7}"),                   # AAA1234567
    re.compile(r"[A-Z0-9]+(?:\/\d+)+"),             # OR/02/009/22647 or similar with slashes
    re.compile(r"[A-Z0-9]{6,}")                     # fallback alphanum
]
RELATIONS = ["Father","Mother","Son","Daughter","Brother","Sister","Husband","Wife"]

def pil_to_cv(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def find_entry_blocks(cv_img, debug=False):
    """
    Find rectangular blocks (rows) likely containing one EPIC entry.
    Returns list of (x,y,w,h) sorted top-to-bottom.
    """
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    # Use adaptive threshold + invert to get text and lines
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = 255 - th

    # Morphology tuned for horizontal rows: wide kernel
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (120, 9))
    morph = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
    # Dilate to merge small gaps
    kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
    morph = cv2.dilate(morph, kernel2, iterations=1)

    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h_img, w_img = cv_img.shape[:2]
    boxes = []
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        # filters (tweakable)
        if w < 200 or h < 30:
            continue
        if h > h_img*0.9 and w > w_img*0.9:
            continue
        boxes.append((x,y,w,h))

    # If we got nothing, fallback: split horizontally into equal strips
    if not boxes:
        approx_rows = max(10, h_img // 60)
        strip_h = max(60, h_img // approx_rows)
        boxes = [(0, i*strip_h, w_img, strip_h) for i in range(approx_rows)]

    # sort top->bottom
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    if debug:
        # Save debug overlay
        vis = cv_img.copy()
        for i,(x,y,w,h) in enumerate(boxes):
            cv2.rectangle(vis, (x,y), (x+w,y+h), (0,255,0), 2)
            cv2.putText(vis, str(i+1), (x+5,y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        os.makedirs(os.path.join(UPLOAD_DIR,"debug"), exist_ok=True)
        cv2.imwrite(os.path.join(UPLOAD_DIR,"debug","page_blocks.png"), vis)
    return boxes

def clean_text(s):
    return re.sub(r'[\r\n\t]+', ' ', s).strip()

def find_epic_in_text(text):
    for pat in EPIC_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return ""

def extract_fields_from_block(block_img):
    """
    Given a cropped block image (BGR), run OCR and heuristics to extract fields.
    Returns a dict with desired columns.
    """
    # upscale a bit to help tesseract
    h,w = block_img.shape[:2]
    scale = 1.5
    big = cv2.resize(block_img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # full-text
    config = '--psm 6'  # assume block is a single text line or small paragraph
    raw_text = pytesseract.image_to_string(th, config=config)
    raw_text = clean_text(raw_text)

    # word-level dataframe for position/confidence
    try:
        df_words = pytesseract.image_to_data(th, output_type=pytesseract.Output.DATAFRAME)
    except Exception:
        # fallback: get plain text tokens
        words = re.split(r'\s+', raw_text)
        df_words = pd.DataFrame({'text': words})

    # drop empty tokens
    if 'text' in df_words.columns:
        df_words = df_words[df_words['text'].notnull() & (df_words['text'].str.strip() != '')]

    joined = " ".join(df_words['text'].astype(str).tolist()) if not df_words.empty else raw_text

    # Extract EPIC (multiple possible patterns)
    epic = find_epic_in_text(joined)

    # Extract relation
    relation = ""
    for r in RELATIONS:
        if re.search(r'\b' + re.escape(r) + r'\b', joined, re.IGNORECASE):
            relation = r
            break

    # Find handwritten letter (single A/B)
    handwritten_letter = ""
    for token in df_words['text'].astype(str).tolist():
        if re.fullmatch(r'[A-Za-z]', token):
            handwritten_letter = token.upper()
            break

    # Find numeric tokens and numeric ranges
    nums = re.findall(r'\b\d{1,6}\b', joined)
    first_num, last_num = "", ""
    hrange = re.search(r'(\d{1,6})\s*[-–—]\s*(\d{1,6})', joined)
    if hrange:
        first_num, last_num = hrange.group(1), hrange.group(2)
    else:
        if len(nums) >= 1:
            first_num = nums[0]
        if len(nums) >= 2:
            last_num = nums[-1]

    # Heuristic mapping for AC_NO, PART_NO, SERIAL_IN_PART:
    # If we have at least 3 numeric tokens on the same line -> assume AC, PART, SERIAL
    ac_no = ""
    part_no = ""
    serial_in_part = ""
    # Try to examine lines instead of whole-joined
    raw_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    # look for a line containing 2-4 numbers
    mapped = False
    for line in raw_lines:
        line_nums = re.findall(r'\b\d{1,6}\b', line)
        if len(line_nums) >= 3:
            ac_no, part_no, serial_in_part = line_nums[0], line_nums[1], line_nums[2]
            mapped = True
            break
    if not mapped and len(nums) >= 3:
        # fallback to first three numeric tokens
        ac_no, part_no, serial_in_part = nums[0], nums[1], nums[2] if len(nums) >= 3 else ("","")
    if not mapped and len(nums) == 2:
        ac_no, part_no = nums[0], nums[1]

    # Category (A/B) detection: single 'A'/'B' tokens or words
    category = ""
    cat_match = re.search(r'\b([AB])\b', joined)
    if cat_match:
        category = cat_match.group(1)

    result = {
        "EPIC_NO": epic,
        "AC_NO": ac_no,
        "PART_NO": part_no,
        "SERIAL_NO_IN_PART": serial_in_part,
        "Category_A/B": category,
        "Handwritten_Letter": handwritten_letter,
        "Handwritten_First_Number": first_num,
        "Handwritten_Last_Number": last_num,
        "Relation": relation,
        "RawText": joined
    }
    return result

def process_file_bytes(file_bytes, filename, dpi=300, debug=False):
    """
    Accepts bytes (pdf or image) and returns list of extracted rows (dicts).
    """
    ext = filename.rsplit('.',1)[1].lower()
    images = []
    if ext == 'pdf':
        pil_pages = convert_from_bytes(file_bytes, dpi=dpi)
        images = [pil_to_cv(p) for p in pil_pages]
    else:
        arr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode image")
        images = [img]

    results = []
    for pidx, img in enumerate(images):
        boxes = find_entry_blocks(img, debug=debug)
        for bidx, (x,y,w,h) in enumerate(boxes):
            crop = img[y:y+h, x:x+w]
            fields = extract_fields_from_block(crop)
            fields['Page'] = pidx + 1
            fields['BlockIndex'] = bidx + 1
            results.append(fields)
            # optionally save the cropped block for debugging
            if debug:
                debug_dir = os.path.join(UPLOAD_DIR, "debug_blocks")
                os.makedirs(debug_dir, exist_ok=True)
                cv2.imwrite(os.path.join(debug_dir, f"page{pidx+1}_block{bidx+1}.png"), crop)
    return results

# Flask routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return jsonify({"error":"no file part"}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({"error":"empty filename"}), 400

    filename = f.filename
    file_bytes = f.read()

    # debug toggle via form param
    debug = request.form.get('debug','0') in ['1','true','True']

    try:
        rows = process_file_bytes(file_bytes, filename, dpi=350, debug=debug)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Create DataFrame and save excel
    df = pd.DataFrame(rows)
    # Ensure column order
    cols = ["Page","BlockIndex","EPIC_NO","AC_NO","PART_NO","SERIAL_NO_IN_PART","Category_A/B",
            "Handwritten_Letter","Handwritten_First_Number","Handwritten_Last_Number","Relation","RawText"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]

    outpath = os.path.join(UPLOAD_DIR, f"{os.path.splitext(filename)[0]}_epic_extract.xlsx")
    df.to_excel(outpath, index=False)

    # Return JSON rows + download link
    resp = {"rows": df.fillna('').to_dict(orient='records'), "download": "/download/" + os.path.basename(outpath)}
    return jsonify(resp)

@app.route("/download/<path:filename>")
def download(filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(path):
        return "file not found", 404
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
