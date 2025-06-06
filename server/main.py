from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pyspark import SparkContext, SparkConf
import cv2
import numpy as np
import io
import zipfile
import uuid
import time
import math
import json

app = Flask(__name__)
CORS(app)

conf = SparkConf().setAppName("DistributedImageProcessor").setMaster("local[*]")
sc = SparkContext(conf=conf)

# Filters (Enhancements)
def apply_averaging_filter(img):
    return cv2.blur(img, (5, 5))

def apply_grayscale(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def apply_sharpen(img):
    kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
    return cv2.filter2D(img, -1, kernel)

def apply_denoise(img):
    return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

def ensure_bgr(img):
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img

ENHANCEMENT_FUNCTIONS = {
    'average': apply_averaging_filter,
    'grayscale': apply_grayscale,
    'sharpen': apply_sharpen,
    'denoise': apply_denoise
}

# Map frontend enhancement names to backend functions
ENHANCEMENT_MAP = {
    'smoothing': 'average',
    'blackwhite': 'grayscale',
    'clarity': 'sharpen',
    'noise-reduction': 'denoise'
}

def process_image_pipeline(image_bytes, selected_enhancements, filename, compression):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    for i, enh in enumerate(selected_enhancements):
        if enh in ENHANCEMENT_FUNCTIONS:
            img = ENHANCEMENT_FUNCTIONS[enh](img)
            if i < len(selected_enhancements) - 1:
                img = ensure_bgr(img)

    img = ensure_bgr(img)
    compression_quality = 100 - compression if compression is not None else 95
    _, processed_bytes = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    return (unique_name, processed_bytes.tobytes())

def process_individual_enhancements(image_bytes, selected_enhancements, filename, compression):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    results = []
    for enh in selected_enhancements:
        if enh in ENHANCEMENT_FUNCTIONS:
            processed = ENHANCEMENT_FUNCTIONS[enh](img)
            processed = ensure_bgr(processed)
            compression_quality = 100 - compression if compression is not None else 95
            _, processed_bytes = cv2.imencode('.jpg', processed, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
            unique_name = f"{uuid.uuid4().hex}_{enh}_{filename}"
            results.append((unique_name, processed_bytes.tobytes()))
    return results

@app.route('/process', methods=['POST'])
def process_images():
    if 'images' not in request.files:
        return jsonify({"error": "No images uploaded"}), 400

    image_files = request.files.getlist('images')
    if not image_files:
        return jsonify({"error": "No valid image files found"}), 400

    # Get and map frontend enhancement names to backend functions
    enhancements_string = request.form.get('enhancements', '')
    frontend_enhancements = [e.strip() for e in enhancements_string.split(',') if e.strip()]
    
    # Map frontend enhancement names to backend function names
    selected_enhancements = []
    for enhancement in frontend_enhancements:
        if enhancement in ENHANCEMENT_MAP:
            selected_enhancements.append(ENHANCEMENT_MAP[enhancement])
    
    compression_enabled = request.form.get('compression_enabled', 'false').lower() == 'true'
    try:
        compression_percent = int(request.form.get('compression_percent', 0))
    except ValueError:
        compression_percent = 0

    # If no enhancements and no compression, return error
    if not selected_enhancements and not compression_enabled:
        return jsonify({"error": "No enhancements or compression selected"}), 400

    compression_value = compression_percent if compression_enabled else None
    mode = request.form.get('mode', 'pipeline')
    
    # Only allow 'pipeline' or 'independent' modes
    if mode not in ['pipeline', 'independent']:
        mode = 'pipeline'
        
    images_data = [(f.read(), f.filename) for f in image_files]
    image_rdd = sc.parallelize(images_data)
    
    result_lists = []
    
    if mode == 'independent' and selected_enhancements:
        result_lists = image_rdd.flatMap(
            lambda tup: process_individual_enhancements(tup[0], selected_enhancements, tup[1], compression_value)
        ).collect()
    else:
        result_lists = image_rdd.map(
            lambda tup: process_image_pipeline(tup[0], selected_enhancements, tup[1], compression_value)
        ).collect()

    # Handle case where no results were produced
    if not result_lists:
        return jsonify({"error": "No images were successfully processed"}), 500

    memory_zip = io.BytesIO()
    with zipfile.ZipFile(memory_zip, 'w') as zipf:
        for fname, img_bytes in result_lists:
            zipf.writestr(fname, img_bytes)
    memory_zip.seek(0)

    return send_file(
        memory_zip,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_images.zip'
    )

if __name__ == '__main__':
    app.run(debug=True, port=8080)