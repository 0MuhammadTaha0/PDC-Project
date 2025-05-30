from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pyspark import SparkContext, SparkConf
import cv2
import numpy as np
import io
import zipfile
import uuid

# Flask app setup
app = Flask(__name__)
cors = CORS(app, origins="*")

# Spark setup
conf = SparkConf().setAppName("DistributedImageProcessor").setMaster("local[*]")
sc = SparkContext(conf=conf)

# Filter functions
def apply_averaging_filter(img):
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return cv2.blur(img, (5, 5))

def apply_grayscale(img):
    if len(img.shape) == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def apply_sharpen(img):
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
    return cv2.filter2D(img, -1, kernel)

def apply_denoise(img):
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

def ensure_bgr(img):
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img

FILTER_FUNCTIONS = {
    'average': apply_averaging_filter,
    'grayscale': apply_grayscale,
    'sharpen': apply_sharpen,
    'denoise': apply_denoise
}

# Process pipeline filters (in sequence)
def process_image_pipeline(image_bytes, selected_filters, filename):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    for i, f in enumerate(selected_filters):
        if f in FILTER_FUNCTIONS:
            img = FILTER_FUNCTIONS[f](img)
            if i < len(selected_filters) - 1:
                img = ensure_bgr(img)

    img = ensure_bgr(img)
    _, processed_bytes = cv2.imencode('.jpg', img)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    return (unique_name, processed_bytes.tobytes())

# Process each filter separately
def process_individual_filters(image_bytes, selected_filters, filename):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    results = []
    for f in selected_filters:
        if f in FILTER_FUNCTIONS:
            processed = FILTER_FUNCTIONS[f](img)
            processed = ensure_bgr(processed)
            _, processed_bytes = cv2.imencode('.jpg', processed)
            unique_name = f"{uuid.uuid4().hex}_{f}_{filename}"
            results.append((unique_name, processed_bytes.tobytes()))
    return results

@app.route('/process', methods=['POST'])
def process_image():
    if 'images' not in request.files:
        return jsonify({"error": "No images uploaded"}), 400

    image_files = request.files.getlist('images')
    if not image_files:
        return jsonify({"error": "No valid image files found"}), 400

    filters_string = request.form.get('filters', 'average')
    selected_filters = [f.strip() for f in filters_string.split(',') if f.strip() in FILTER_FUNCTIONS]
    if not selected_filters:
        return jsonify({"error": "No valid filters selected"}), 400

    mode = request.form.get('mode', 'pipeline')  # 'pipeline' or 'independent'
    images_data = [(f.read(), f.filename) for f in image_files]

    image_rdd = sc.parallelize(images_data)

    if mode == 'independent':
        result_lists = image_rdd.flatMap(lambda tup: process_individual_filters(tup[0], selected_filters, tup[1])).collect()
    else:
        result_lists = image_rdd.map(lambda tup: process_image_pipeline(tup[0], selected_filters, tup[1])).collect()

    # Create in-memory zip file
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
