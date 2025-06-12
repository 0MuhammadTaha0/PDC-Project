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

def apply_edge(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

def apply_brightness(img, value=30):
    value = int(value)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    v = v.astype(np.int16)
    v = np.clip(v + value, 0, 255)
    v = v.astype(np.uint8)
    final_hsv = cv2.merge((h, s, v))
    return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)

def process_images_per_image(image_rdd, selected_enhancements, compression_value, brightness_level):
    return image_rdd.map(
        lambda tup: process_image_pipeline(tup[0], selected_enhancements, tup[1], compression_value, brightness_level)
    ).collect()

def split_image_into_chunks(img, chunk_size=256):
    h, w = img.shape[:2]
    chunks = []
    for y in range(0, h, chunk_size):
        for x in range(0, w, chunk_size):
            chunk = img[y:y+chunk_size, x:x+chunk_size]
            chunks.append(((y, x), chunk))
    return chunks, h, w

def merge_chunks(chunks, h, w, chunk_size=256):
    result = np.zeros((h, w, 3), dtype=np.uint8)
    for (y, x), chunk in chunks:
        result[y:y+chunk.shape[0], x:x+chunk.shape[1]] = chunk
    return result

def process_images_per_chunk(image_rdd, selected_enhancements, compression_value, brightness_level):
    def process_chunks(image_bytes, filename):
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        chunks, h, w = split_image_into_chunks(img)
        processed_chunks = []
        for (y, x), chunk in chunks:
            for enh in selected_enhancements:
                if enh == 'brightness':
                    chunk = apply_brightness(chunk, value=brightness_level)
                elif enh in ENHANCEMENT_FUNCTIONS:
                    chunk = ENHANCEMENT_FUNCTIONS[enh](chunk)
                chunk = ensure_bgr(chunk)
            processed_chunks.append(((y, x), chunk))
        merged = merge_chunks(processed_chunks, h, w)
        compression_quality = 100 - compression_value if compression_value is not None else 95
        _, processed_bytes = cv2.imencode('.jpg', merged, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        return (unique_name, processed_bytes.tobytes())
    return image_rdd.map(lambda tup: process_chunks(tup[0], tup[1])).collect()

def process_images_pipeline(image_rdd, selected_enhancements, compression_value, brightness_level):
    def pipeline(img):
        for enh in selected_enhancements:
            if enh == 'brightness':
                img = apply_brightness(img, value=brightness_level)
            elif enh in ENHANCEMENT_FUNCTIONS:
                img = ENHANCEMENT_FUNCTIONS[enh](img)
            img = ensure_bgr(img)
        return img

    def process(image_bytes, filename):
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        img = pipeline(img)
        compression_quality = 100 - compression_value if compression_value is not None else 95
        _, processed_bytes = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        return (unique_name, processed_bytes.tobytes())
    return image_rdd.map(lambda tup: process(tup[0], tup[1])).collect()

ENHANCEMENT_FUNCTIONS = {
    'average': apply_averaging_filter,
    'grayscale': apply_grayscale,
    'sharpen': apply_sharpen,
    'denoise': apply_denoise,
    'edge': apply_edge,
    'brightness': apply_brightness
}

# Map frontend enhancement names to backend functions
ENHANCEMENT_MAP = {
    'smoothing': 'average',
    'blackwhite': 'grayscale',
    'clarity': 'sharpen',
    'noise-reduction': 'denoise',
    'edge-detection': 'edge',
    'brightness': 'brightness'
}

def process_image_pipeline(image_bytes, selected_enhancements, filename, compression, brightness_level=30):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    for i, enh in enumerate(selected_enhancements):
        if enh == 'brightness':
            img = apply_brightness(img, value=brightness_level)
        elif enh in ENHANCEMENT_FUNCTIONS:
            img = ENHANCEMENT_FUNCTIONS[enh](img)
        if i < len(selected_enhancements) - 1:
            img = ensure_bgr(img)

    img = ensure_bgr(img)
    compression_quality = 100 - compression if compression is not None else 95
    _, processed_bytes = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    return (unique_name, processed_bytes.tobytes())

# def process_individual_enhancements(image_bytes, selected_enhancements, filename, compression, brightness_level=30):
#     img_array = np.frombuffer(image_bytes, dtype=np.uint8)
#     img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

#     results = []
#     for enh in selected_enhancements:
#         if enh == 'brightness':
#             processed = apply_brightness(img, value=brightness_level)
#         elif enh in ENHANCEMENT_FUNCTIONS:
#             processed = ENHANCEMENT_FUNCTIONS[enh](img)
#         else:
#             continue
#         processed = ensure_bgr(processed)
#         compression_quality = 100 - compression if compression is not None else 95
#         _, processed_bytes = cv2.imencode('.jpg', processed, [int(cv2.IMWRITE_JPEG_QUALITY), compression_quality])
#         unique_name = f"{uuid.uuid4().hex}_{enh}_{filename}"
#         results.append((unique_name, processed_bytes.tobytes()))
#     return results

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

    # getting brightness level from form data

    brightness_level = 30  # Default value
    if 'brightness_level' in request.form:
        try:
            brightness_level = int(request.form['brightness_level'])
        except ValueError:
            brightness_level = 30

    # If no enhancements and no compression, return error
    if not selected_enhancements and not compression_enabled:
        return jsonify({"error": "No enhancements or compression selected"}), 400

    compression_value = compression_percent if compression_enabled else None

    # Strategy Selection:
    strategy = request.form.get('strategy', 'per-image')
    
    # mode = request.form.get('mode', 'pipeline')


    # # Only allow 'pipeline' or 'independent' modes
    # if mode not in ['pipeline', 'independent']:
    #     mode = 'pipeline'
        
    images_data = [(f.read(), f.filename) for f in image_files]
    image_rdd = sc.parallelize(images_data)
    
    if strategy == 'per-image':
        result_lists = process_images_per_image(image_rdd, selected_enhancements, compression_value, brightness_level)
    elif strategy == 'per-chunk':
        result_lists = process_images_per_chunk(image_rdd, selected_enhancements, compression_value, brightness_level)
    elif strategy == 'pipeline':
        result_lists = process_images_pipeline(image_rdd, selected_enhancements, compression_value, brightness_level)
    else:
        return jsonify({"error": "Unknown processing strategy"}), 400

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