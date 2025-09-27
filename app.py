import os
import tempfile
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
import cv2
import pytesseract
from pdf2image import convert_from_path
import numpy as np

app = Flask(__name__)

def find_blocks(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _,thresh = cv2.threshold(gray, 0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(30,30))
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    contours,_ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x,y,w,h = cv2.boundingRect(c)
        if h>50 and w>100:
            boxes.append((x,y,w,h))
    boxes = sorted(boxes, key=lambda b:(b[1],b[0]))
    return boxes

def extract_fields(text):
    import re
    serial = re.search(r'\b\d{1,4}\b',text)
    epic = re.search(r'[A-Z]{3}\d{7}',text)
    letter = re.search(r'\b[A-Z]\b',text)
    nums = re.findall(r'\d+',text)
    relation = None
    for rel in ["Father","Mother","Son","Daughter","Brother","Sister"]:
        if rel.lower() in text.lower():
            relation=rel
            break
    return {
        "SerialNo": serial.group(0) if serial else "",
        "EPIC": epic.group(0) if epic else "",
        "Handwritten_Letter": letter.group(0) if letter else "",
        "Handwritten_First_Number": nums[0] if len(nums)>0 else "",
        "Handwritten_Last_Number": nums[-1] if len(nums)>1 else "",
        "Relation": relation or ""
    }

def process_file(filepath):
    # convert PDF to images or read single image
    images = []
    if filepath.lower().endswith(".pdf"):
        pages = convert_from_path(filepath, dpi=300)
        for p in pages:
            images.append(cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR))
    else:
        images.append(cv2.imread(filepath))
    rows=[]
    for img in images:
        boxes=find_blocks(img)
        for (x,y,w,h) in boxes:
            crop=img[y:y+h,x:x+w]
            text=pytesseract.image_to_string(crop)
            fields=extract_fields(text)
            rows.append(fields)
    df=pd.DataFrame(rows)
    return df

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file=request.files['file']
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        file.save(tmp.name)
        df=process_file(tmp.name)
    out_path=os.path.join(tempfile.gettempdir(),"epic_serial_handwritten.xlsx")
    df.to_excel(out_path,index=False)
    return jsonify({
        "data":df.to_dict(orient="records"),
        "download":"/download"
    })

@app.route("/download")
def download():
    path=os.path.join(tempfile.gettempdir(),"epic_serial_handwritten.xlsx")
    return send_file(path, as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000)
