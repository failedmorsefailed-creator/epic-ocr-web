import tempfile
import subprocess
import os
import pytesseract
from PIL import Image
import io
from .preprocess import preprocess_image_pil
import json


TESSERACT_LANG = 'eng+ori'


def ocr_image_bytes(img_bytes: bytes):
pil = Image.open(io.BytesIO(img_bytes)).convert('RGB')
proc = preprocess_image_pil(pil)
custom_config = '--psm 3'
text = pytesseract.image_to_string(proc, lang=TESSERACT_LANG, config=custom_config)
data = pytesseract.image_to_data(proc, lang=TESSERACT_LANG, config=custom_config, output_type=pytesseract.Output.DICT)
return {
'text': text,
'words': data,
}


def ocr_pdf_bytes(pdf_bytes: bytes):
with tempfile.TemporaryDirectory() as tmp:
in_path = os.path.join(tmp, 'in.pdf')
out_pdf = os.path.join(tmp, 'out.pdf')
with open(in_path, 'wb') as f:
f.write(pdf_bytes)
cmd = ['ocrmypdf', '--force-ocr', '--deskew', '--clean', '--output-type', 'pdfa', '--language', 'eng+ori', in_path, out_pdf]
subprocess.check_call(cmd)
proc = subprocess.run(['pdftotext', out_pdf, '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
text = proc.stdout.decode('utf-8', errors='ignore')
return {'text': text, 'pdf': out_pdf}
