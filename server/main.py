from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pyspark import SparkContext, SparkConf
import cv2
import numpy as np
import io

# Flask app and CORS setup
app = Flask(__name__)
cors = CORS(app, origins="*")

# Spark setup
conf = SparkConf().setAppName("DistributedImageProcessor").setMaster("local[*]")
sc = SparkContext(conf=conf)

# Image processing function using OpenCV
def apply_averaging_filter(image_bytes):
    img_array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    blurred = cv2.blur(img, (5, 5))
    _, processed_bytes = cv2.imencode('.jpg', blurred)
    return processed_bytes.tobytes()

# Main image processing route
@app.route('/process', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files['image']
    image_bytes = image_file.read()

    # Optional filter type (future-ready)
    filter_type = request.form.get('filter', 'average')

    # Currently only "average" is supported
    if filter_type != 'average':
        return jsonify({"error": "Unsupported filter type"}), 400

    # Distribute and process image using Spark
    image_rdd = sc.parallelize([image_bytes])
    processed_bytes = image_rdd.map(apply_averaging_filter).collect()[0]

    # Return the processed image as a downloadable file
    return send_file(
        io.BytesIO(processed_bytes),
        mimetype='image/jpeg',
        as_attachment=False,
        download_name='processed.jpg'
    )

# Run server
if __name__ == '__main__':
    app.run(debug=True, port=8080)
