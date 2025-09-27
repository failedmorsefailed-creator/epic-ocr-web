import cv2
import numpy as np
import pytesseract
from pytesseract import Output
import pandas as pd
from PIL import Image
import io, traceback

def load_image(path):
    img = cv2.imread(path)
    return img

def preprocess_for_lines(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # adaptive invert threshold (helps line detection)
    try:
        binary = cv2.adaptiveThreshold(~gray, 255,
                                       cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, 15, -2)
    except Exception:
        _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    return binary

def detect_table_mask(binary):
    rows, cols = binary.shape
    horiz_size = max(10, cols // 30)
    vert_size = max(10, rows // 30)

    hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horiz_size, 1))
    ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vert_size))

    horizontal = cv2.erode(binary, hor_kernel)
    horizontal = cv2.dilate(horizontal, hor_kernel)

    vertical = cv2.erode(binary, ver_kernel)
    vertical = cv2.dilate(vertical, ver_kernel)

    mask = cv2.add(horizontal, vertical)
    return mask, horizontal, vertical

def extract_boxes_from_mask(mask, img_shape):
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    rows, cols = img_shape[:2]
    boxes = []
    for c in contours:
        x,y,w,h = cv2.boundingRect(c)
        if w > 40 and h > 12 and w < 0.98*cols and h < 0.98*rows:
            boxes.append((x,y,w,h))
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    return boxes

def group_boxes_to_rows(boxes, tol=12):
    rows = []
    cur = []
    last_y = None
    for b in boxes:
        x,y,w,h = b
        if last_y is None:
            cur = [b]
            last_y = y
        elif abs(y - last_y) <= tol:
            cur.append(b)
            last_y = int((last_y + y) / 2)
        else:
            rows.append(sorted(cur, key=lambda bb: bb[0]))
            cur = [b]
            last_y = y
    if cur:
        rows.append(sorted(cur, key=lambda bb: bb[0]))
    return rows

def ocr_crop(img, box):
    x,y,w,h = box
    pad = 2
    x1 = max(0, x-pad)
    y1 = max(0, y-pad)
    x2 = min(img.shape[1], x + w + pad)
    y2 = min(img.shape[0], y + h + pad)
    crop = img[y1:y2, x1:x2]
    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    try:
        txt = pytesseract.image_to_string(pil, config="--psm 6 --oem 3")
    except Exception:
        txt = ""
    return txt.strip()

def fallback_tesseract_table(img):
    # Use pytesseract.image_to_data and cluster by left positions to create columns
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    try:
        data = pytesseract.image_to_data(pil, output_type=Output.DICT)
    except Exception as e:
        raise RuntimeError("Tesseract image_to_data failed: " + str(e))

    n = len(data['text'])
    tokens = []
    for i in range(n):
        txt = str(data['text'][i]).strip()
        try:
            conf = int(float(data['conf'][i]))
        except Exception:
            conf = -1
        if txt and conf > -1:
            left = int(data['left'][i])
            top = int(data['top'][i])
            line = int(data.get('line_num', [0]*n)[i])
            tokens.append((line, left, top, txt))

    if not tokens:
        return pd.DataFrame()

    img_w = img.shape[1]
    bucket = max(30, img_w // 12)
    # get ordered unique buckets
    lefts = np.array([t[1] for t in tokens])
    groups = np.round(lefts / bucket).astype(int)
    uniq_groups = sorted(list(dict.fromkeys(groups.tolist())))

    from collections import defaultdict
    lines_dict = defaultdict(lambda: defaultdict(list))
    for line,left,top,txt in tokens:
        g = int(round(left / bucket))
        lines_dict[line][g].append((left, txt))

    rows = []
    for line in sorted(lines_dict.keys()):
        row = []
        for g in uniq_groups:
            parts = sorted(lines_dict[line].get(g, []), key=lambda x: x[0])
            cell = " ".join([p[1] for p in parts]).strip()
            row.append(cell)
        rows.append(row)

    df = pd.DataFrame(rows)
    return df

def process_file_to_dataframe(path):
    """Return (DataFrame, debug_text)"""
    debug_lines = []
    try:
        img = load_image(path)
        if img is None:
            return pd.DataFrame(), f"ERROR: Could not load image: {path}"

        debug_lines.append(f"Loaded image: {path} size={img.shape}")

        binary = preprocess_for_lines(img)
        debug_lines.append("Preprocessed for lines (adaptive threshold).")

        mask, hor, ver = detect_table_mask(binary)
        debug_lines.append("Detected horizontal & vertical masks.")

        boxes = extract_boxes_from_mask(mask, img.shape)
        debug_lines.append(f"Found {len(boxes)} candidate boxes from mask.")

        if not boxes or len(boxes) < 2:
            debug_lines.append("Grid detection produced too few boxes; falling back to Tesseract image_to_data clustering.")
            df = fallback_tesseract_table(img)
            debug_lines.append(f"Fallback produced dataframe with shape {df.shape}.")
            return df.fillna(""), "\n".join(debug_lines)
        else:
            rows = group_boxes_to_rows(boxes, tol=12)
            debug_lines.append(f"Grouped into {len(rows)} rows.")
            table = []
            for r in rows:
                row_texts = [ocr_crop(img, b) for b in r]
                table.append(row_texts)
            # normalize
            maxc = max(len(r) for r in table)
            for r in table:
                if len(r) < maxc:
                    r.extend(['']*(maxc - len(r)))
            df = pd.DataFrame(table)
            debug_lines.append(f"Grid OCR produced dataframe with shape {df.shape}.")
            return df.fillna(""), "\n".join(debug_lines)

    except Exception as e:
        tb = traceback.format_exc()
        debug_lines.append("Exception during OCR: " + str(e))
        debug_lines.append(tb)
        # attempt fallback final time
        try:
            img = load_image(path)
            df = fallback_tesseract_table(img)
            debug_lines.append(f"Final fallback produced dataframe with shape {df.shape}.")
            return df.fillna(""), "\n".join(debug_lines)
        except Exception as e2:
            debug_lines.append("Final fallback failed: " + str(e2))
            return pd.DataFrame(), "\n".join(debug_lines)
