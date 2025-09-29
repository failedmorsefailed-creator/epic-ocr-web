let capturedBlob = null;

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

  const response = await fetch("https://YOUR-RENDER-BACKEND-URL/ocr", {
    method: "POST",
    body: formData
  });

  const data = await response.json();
  document.getElementById("result").value = data.text;
}

function snapPhoto() {
  const video = document.getElementById('camera');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    capturedBlob = blob;
    alert("Photo captured. Click Upload & OCR to process.");
  }, 'image/jpeg');
}

async function initCamera() {
  const video = document.getElementById('camera');
  const stream = await navigator.mediaDevices.getUserMedia({video: true});
  video.srcObject = stream;
}

function downloadText() {
  const text = document.getElementById("result").value;
  const blob = new Blob([text], {type: "text/plain"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = "ocr_result.txt";
  a.click();
}

initCamera();
