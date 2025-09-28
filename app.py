# app.py
import streamlit as st
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pandas as pd
import re
import io
import os
import tempfile

st.set_page_config(page_title="Voter List OCR → Excel", layout="wide")

# Allow user to override tesseract path via env var (useful in some deployments)
if "TESSERACT_CMD" in os.environ:
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
else:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# -------------------------
# Helper: Preprocess image
# -------------------------
def preprocess_image_for_ocr(pil_img, high_accuracy=False):
    img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if high_accuracy:
        gray = cv2.medianBlur(gray, 3)
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
    else:
        _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(gray)

# -------------------------
# Engine A: Tesseract OCR
# -------------------------
def ocr_with_tesseract(pil_img, high_accuracy=False, lang="eng+ori"):
    proc = preprocess_image_for_ocr(pil_img, high_accuracy=high_accuracy)
    config = r"--oem 3 --psm 6"
    try:
        text = pytesseract.image_to_string(proc, lang=lang, config=config)
    except Exception:
        # fallback to default lang
        text = pytesseract.image_to_string(proc, config=config)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines

# -------------------------
# Engine B: Google Vision OCR
# -------------------------
def ocr_with_google_vision(pil_img, credentials_file_path=None):
    try:
        from google.cloud import vision
    except Exception as e:
        st.error("google-cloud-vision library is not installed. See README to add it.")
        st.stop()

    # If user provided credentials file path, set env var for this session
    if credentials_file_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_file_path

    client = vision.ImageAnnotatorClient()
    img_bytes = io.BytesIO()
    pil_img.save(img_bytes, format="PNG")
    content = img_bytes.getvalue()
    image = vision.Image(content=content)

    response = client.document_text_detection(image=image)
    if response.error and response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")

    # full_text_annotation has the block/paragraph/line structure; we can take .text
    text = response.full_text_annotation.text if response.full_text_annotation else ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines

# -------------------------
# Parser (same logic as earlier)
# -------------------------
def parse_lines_to_records(lines, ac_no="32 - Jaleswar", part_no="170"):
    records = []
    current = None

    epic_re = re.compile(r"(OR/\S+|CQW\S+|UFN\S+|JDP\S+|RPZ\S+|\b[A-Z]{2}/\d+/\d+/\d+\b)")
    serial_re = re.compile(r"^\d{1,3}$")
    cat_rel_re = re.compile(r"^[ABC]\b", re.IGNORECASE)
    oldpart_re = re.compile(r"\b\d{2}/\d{1,3}\b")

    for line in lines:
        # Serial numbers (boxed, left side) usually appear as a plain number line
        if serial_re.match(line):
            if current:
                records.append(current)
            current = {
                "EPIC No": "",
                "AC No": ac_no,
                "PART No": part_no,
                "SERIAL No": line,
                "CATAGORY A/B": "",
                "RELATION OF THE ELECTOR": "",
                "OLD AC No": "",
                "OLD PART No": "",
                "OLD PART SERIAL No": ""
            }
            continue

        # EPIC detection
        m = epic_re.search(line)
        if m and current is not None:
            current["EPIC No"] = m.group(0)
            continue

        # Category + relation + numeric like 04/345 (handwritten)
        if cat_rel_re.match(line) and current is not None:
            parts = line.split()
            current["CATAGORY A/B"] = parts[0].upper()
            # capture numeric fraction like 04/345
            num = oldpart_re.search(line)
            if num:
                current["OLD PART SERIAL No"] = num.group(0)
            relation_parts = [p for p in parts[1:] if not oldpart_re.match(p)]
            if relation_parts:
                current["RELATION OF THE ELECTOR"] = " ".join(relation_parts)
            continue

        # relation lines (Odia or English)
        if current is not None and (
            "W/O" in line or "W O" in line or "wife" in line.lower()
            or "son" in line.lower() or "daughter" in line.lower()
            or any(ch in line for ch in ["ପିତା","ସ୍ୱାମୀ","ପୁଅ","ଝିଅ","ମହିଳା","ପୁରୁଷ"])
        ):
            if not current["RELATION OF THE ELECTOR"]:
                current["RELATION OF THE ELECTOR"] = line
            else:
                current["RELATION OF THE ELECTOR"] += " " + line
            num = oldpart_re.search(line)
            if num and not current["OLD PART SERIAL No"]:
                current["OLD PART SERIAL No"] = num.group(0)
            continue

        # fallback: numeric code on its own
        num = oldpart_re.match(line)
        if num and current is not None and not current["OLD PART SERIAL No"]:
            current["OLD PART SERIAL No"] = num.group(0)
            continue

    if current:
        records.append(current)
    return records

# -------------------------
# UI: Upload / camera / options
# -------------------------
st.title("📋 Voter List OCR → Excel (Tesseract + Google Vision)")

col_a, col_b = st.columns([2,1])
with col_a:
    uploaded = st.file_uploader("Upload image (jpg/png)", type=["jpg","jpeg","png"], accept_multiple_files=False)
with col_b:
    camera_img = st.camera_input("Or take a photo with your phone (mobile)")

engine = st.radio("Choose OCR engine", ("Tesseract (offline)", "Google Vision (online, higher accuracy)"))

high_acc = st.checkbox("High accuracy preprocessing (slower)", value=True)

# Optional: let user upload service account JSON for quick test (not saved in repo)
st.markdown("**Google Vision credentials (optional for quick testing):** upload service-account JSON here *only* for quick runs — don't commit it to Git.")
svc_file = st.file_uploader("Optional: Upload service-account JSON (Google Cloud)", type=["json"], key="svc")

ac_no = st.text_input("AC No (header)", value="32 - Jaleswar")
part_no = st.text_input("PART No (header)", value="170")

# prepare image object if available
img_in = None
if camera_img is not None:
    img_in = Image.open(camera_img)
elif uploaded is not None:
    try:
        img_in = Image.open(uploaded)
    except Exception:
        st.error("Cannot open uploaded image. Try another file.")

if img_in is not None:
    st.subheader("Image preview")
    st.image(img_in, use_column_width=True)

    if st.button("Run OCR & Parse"):
        # If service account JSON uploaded, write to temp path and set env var
        credentials_path = None
        if svc_file is not None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            tmp.write(svc_file.read())
            tmp.flush()
            credentials_path = tmp.name
            st.info("Temporary credentials file created for this session (not saved to repo).")

        try:
            with st.spinner("Running OCR..."):
                if engine == "Tesseract (offline)":
                    lines = ocr_with_tesseract(img_in, high_accuracy=high_acc, lang="eng+ori")
                else:
                    # use Google Vision
                    lines = ocr_with_google_vision(img_in, credentials_file_path=credentials_path)

            if st.checkbox("Show raw OCR lines (debug)", value=False):
                st.text_area("OCR raw lines", "\n".join(lines), height=300)

            records = parse_lines_to_records(lines, ac_no=ac_no, part_no=part_no)
            if not records:
                st.warning("No structured records found. Try toggling preprocessing or upload a clearer photo.")
            else:
                df = pd.DataFrame(records, columns=[
                    "EPIC No", "AC No", "PART No", "SERIAL No",
                    "CATAGORY A/B", "RELATION OF THE ELECTOR",
                    "OLD AC No", "OLD PART No", "OLD PART SERIAL No"
                ])

                st.subheader("Extracted Table (Preview)")
                try:
                    st.data_editor(df, num_rows="dynamic")
                except Exception:
                    st.dataframe(df)

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="voters")
                buf.seek(0)
                st.download_button("📥 Download Excel (.xlsx)", data=buf,
                                   file_name="voterlist_extracted.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                st.success(f"Finished — {len(records)} record(s) extracted.")
        except Exception as e:
            st.error(f"OCR or parsing error: {e}")
else:
    st.info("Upload an image above or use camera to capture a photo, then click 'Run OCR & Parse'.")
