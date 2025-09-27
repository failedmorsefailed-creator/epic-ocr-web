import cv2
import numpy as np
import pytesseract
import pandas as pd
from pdf2image import convert_from_path
from io import BytesIO
from PIL import Image

def load_pages(path):
    if path.lower().endswith(".pdf"):
        pil_pages = convert_from_path(path, dpi=300)
        return [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pil_pages]
    else:
        return [cv2.imread(path)]

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    return gray

def detect_lines(binary):
    rows, cols = binary.shape

    # horizontal
    horizontal_size = cols // 30
    horizontal_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1))
    horizontal = cv2.erode(binary, horizontal_structure)
    horizontal = cv2.dilate(horizontal, horizontal_structure)

    # vertical
    vertical_size = rows // 30
    vertical_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size))
    vertical = cv2.erode(binary, vertical_structure)
    vertical = cv2.dilate(vertical, vertical_structure)

    mask = horizontal + vertical
    return mask

def extract_cells(img, mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in contours]

    # filter out tiny boxes
    boxes = [(x, y, w, h) for x, y, w, h in boxes if w > 40 and h > 20]

    # sort by row then col
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    return boxes

def group_into_grid(boxes, row_tol=15):
    rows = []
    current_row = []
    last_y = -999
    for b in boxes:
        x, y, w, h = b
        if abs(y - last_y) > row_tol:
            if current_row:
                rows.append(sorted(current_row, key=lambda bb: bb[0]))
            current_row = [b]
            last_y = y
        else:
            current_row.append(b)
    if current_row:
        rows.append(sorted(current_row, key=lambda bb: bb[0]))
    return rows

def ocr_cell(img, box):
    x, y, w, h = box
    crop = img[y:y+h, x:x+w]
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    text = pytesseract.image_to_string(pil, config="--psm 6").strip()
    return text

def process_image_page(path):
    img = load_pages(path)[0]
    binary = preprocess(img)
    mask = detect_lines(binary)
    boxes = extract_cells(img, mask)
    rows = group_into_grid(boxes)

    data = []
    for r in rows:
        data.append([ocr_cell(img, b) for b in r])

    return pd.DataFrame(data)

def process_file_to_excel(path):
    df = process_image_page(path)
    buf = BytesIO()
    df.to_excel(buf, index=False, header=False)
    buf.seek(0)
    return buf
