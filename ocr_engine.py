import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
from io import BytesIO
from PIL import Image

# Config: tweak these for your documents
MIN_CELL_WIDTH = 30
MIN_CELL_HEIGHT = 15
ROW_TOLERANCE = 12

def load_pages(path):
    """Return list of OpenCV BGR images for an image or a PDF."""
    if path.lower().endswith('.pdf'):
        pil_pages = convert_from_path(path)
        images = [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pil_pages]
    else:
        img = cv2.imread(path)
        images = [img]
    return images

def preprocess_for_table(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 8
    )
    return thresh

def detect_table_cells(thresh):
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

    detect_horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    detect_vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)

    mask = cv2.add(detect_horizontal, detect_vertical)

    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > MIN_CELL_WIDTH and h > MIN_CELL_HEIGHT:
            boxes.append((x, y, w, h))

    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    return boxes

def group_boxes_to_rows(boxes):
    rows = []
    current_row = []
    current_y = -999
    for (x, y, w, h) in boxes:
        if current_y == -999:
            current_y = y
        if abs(y - current_y) > ROW_TOLERANCE:
            rows.append(sorted(current_row, key=lambda b: b[0]))
            current_row = []
            current_y = y
        current_row.append((x, y, w, h))
    if current_row:
        rows.append(sorted(current_row, key=lambda b: b[0]))
    return rows

def ocr_cell(image, box):
    x, y, w, h = box
    pad = 3
    h_img, w_img = image.shape[:2]
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w_img, x + w + pad)
    y2 = min(h_img, y + h + pad)
    cell = image[y1:y2, x1:x2]
    cell_pil = Image.fromarray(cv2.cvtColor(cell, cv2.COLOR_BGR2RGB))
    text = pytesseract.image_to_string(cell_pil, config='--psm 6 --oem 3')
    return text.strip()

def rows_to_dataframe(rows, image):
    data = []
    max_cols = 0
    for r in rows:
        row_texts = [ocr_cell(image, box) for box in r]
        data.append(row_texts)
        max_cols = max(max_cols, len(row_texts))
    for i in range(len(data)):
        if len(data[i]) < max_cols:
            data[i].extend([''] * (max_cols - len(data[i])))
    return pd.DataFrame(data)

def process_image_page(path_or_img):
    if isinstance(path_or_img, str):
        images = load_pages(path_or_img)
    else:
        images = [path_or_img]

    all_frames = []
    for img in images:
        thresh = preprocess_for_table(img)
        boxes = detect_table_cells(thresh)
        if not boxes:
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            text = pytesseract.image_to_string(pil, config='--psm 4')
            lines = [l for l in text.splitlines() if l.strip()]
            df = pd.DataFrame([l.split() for l in lines])
        else:
            rows = group_boxes_to_rows(boxes)
            df = rows_to_dataframe(rows, img)
        all_frames.append(df)

    if len(all_frames) == 1:
        return all_frames[0]
    else:
        return pd.concat(all_frames, ignore_index=True)

def process_file_to_excel(path):
    df = process_image_page(path)
    out = BytesIO()
    df.to_excel(out, index=False, header=False)
    out.seek(0)
    return out
