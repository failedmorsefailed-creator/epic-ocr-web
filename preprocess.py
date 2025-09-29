import cv2
import numpy as np
from PIL import Image


def pil_to_cv(pil):
arr = np.array(pil)
return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def cv_to_pil(cv_img):
cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
return Image.fromarray(cv_img)


def preprocess_image_pil(pil_image: Image.Image) -> Image.Image:
img = pil_to_cv(pil_image)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
cv2.THRESH_BINARY, 31, 10)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
opened = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
coords = np.column_stack(np.where(opened > 0))
angle = 0.0
if coords.size:
rect = cv2.minAreaRect(coords)
angle = rect[-1]
if angle < -45:
angle = -(90 + angle)
else:
angle = -angle
(h, w) = opened.shape
M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
opened = cv2.warpAffine(opened, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
return cv_to_pil(cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR))
