from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "OCR backend running"}

@app.post("/ocr")  # or "/api/ocr" if you prefer
async def ocr_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename.lower()

    images = []
    if filename.endswith(".pdf"):
        images = convert_from_bytes(content)
    else:
        images = [Image.open(io.BytesIO(content))]

    text_results = []
    for img in images:
        text = pytesseract.image_to_string(img, lang="eng+ori")
        text_results.append(text)

    return JSONResponse({"text": "\n".join(text_results)})
