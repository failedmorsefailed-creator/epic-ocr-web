from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pytesseract
from PIL import Image
import io

app = FastAPI()

# Allow your frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def home():
    # This just displays a friendly message or you can serve your frontend file
    return """
    <h1>Odia-English OCR API</h1>
    <p>Use POST /ocr with form field 'file' to extract text.</p>
    """

@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    # Read uploaded file
    contents = await file.read()

    # Open as image
    image = Image.open(io.BytesIO(contents))

    # Perform OCR (English + Odia)
    text = pytesseract.image_to_string(image, lang="eng+ori")

    return {"filename": file.filename, "text": text}
