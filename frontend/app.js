let capturedBlob = null;
// Replace with your backend URL on Render after deploy:
const BACKEND_URL = "https://YOUR-BACKEND-URL.onrender.com/ocr";

document.getElementById('uploadBtn').addEventListener('click', sendFile);
document.getElementById('snapBtn').addEventListener('click', snapPhoto);
document.getElementById('downloadBtn').addEventListener('click', downloadText);

async function sendFile() {
  const fileInput = document.getElementById('fileInput');
  let file = fileInput.files[0];

  if (!file && capturedBlob) {
    file = new File([capturedBlob], 'photo.jpg', {type: 'image/jpeg'});
  }

  if (!file) {
    alert("Please select or capture a file");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error('OCR request failed: ' + errText);
    }

    const data = await response.json();
    document.getElementById("result").value = data.text;
  } catch (err) {
    alert("Error: " + err.message);
  }
}

function snapPhoto() {
  const video = document.getElementById('camera');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    capturedBlob = blob;
    alert("Photo captured. Click Upload & OCR to process.");
  }, 'image/jpeg', 0.9);
}

async function initCamera() {
  try {
    const video = document.getElementById('camera');
    const stream = await navigator.mediaDevices.getUserMedia({video: { facingMode: "environment"}});
    video.srcObject = stream;
  } catch (e) {
    console.warn("Camera not available: " + e);
  }
}

function downloadText() {
  const text = document.getElementById("result").value;
  const blob = new Blob([text], {type: "text/plain"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = "ocr_result.txt";
  a.click();
  URL.revokeObjectURL(url);
}

initCamera();
