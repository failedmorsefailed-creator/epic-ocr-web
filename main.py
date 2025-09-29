from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import uuid
import os
from .ocr import ocr_image_bytes, ocr_pdf_bytes


app = FastAPI()
app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)


TEMP_DIR = '/tmp/ocr'
os.makedirs(TEMP_DIR, exist_ok=True)


@app.post('/api/ocr')
async def ocr_upload(file: UploadFile = File(...)):
content = await file.read()
filename = file.filename or f"upload_{uuid.uuid4().hex}"
lower = filename.lower()
try:
if lower.endswith('.pdf'):
result = ocr_pdf_bytes(content)
return JSONResponse(result)
else:
text_result = ocr_image_bytes(content)
return JSONResponse(text_result)
except Exception as e:
raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/download/text/{name}')
def download_text(name: str):
path = os.path.join(TEMP_DIR, name)
if not os.path.exists(path):
raise HTTPException(status_code=404, detail='Not found')
return FileResponse(path, media_type='text/plain', filename=name)


if __name__ == '__main__':
uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)
