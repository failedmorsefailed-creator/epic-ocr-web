# app.py
import os
import io
import re
from flask import Flask, render_template, request, jsonify, send_file
from pdf2image import convert_from_bytes
import pytesseract
import cv2
import numpy as np
import pandas as pd
from PIL import Image

app = Flask(__name__)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Patterns & helpers
EPIC_PATTERNS = [
    re.compile(r"[A-Z]{3}\d{7}"),                   # AAA1234567
    re.compile(r"[A-Z0-9]+(?:\/\d+)+"),             # OR/02/009/22647 or similar with slashes
    re.compile
