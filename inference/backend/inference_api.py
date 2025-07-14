from flask import Flask, request, jsonify
import util
import os
from log_db import log_request

app = Flask(__name__)

@app.route('/api/get_location_names', methods=['GET'])
def get_location_names():
    response = jsonify({
        'locations': util.get_location_names()
    })
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

@app.route('/api/predict_home_price', methods=['GET', 'POST'])
def predict_home_price():
    total_sqft = float(request.form['total_sqft'])
    location = request.form['location']
    bhk = int(request.form['bhk'])
    bath = int(request.form['bath'])

    pred = util.get_estimated_price(location,total_sqft,bhk,bath)
    # log to DB
    variant = os.getenv("MODEL_PREFIX", "best_model")
    try:
        log_request(variant, location, total_sqft, bhk, bath, pred)
    except Exception as e:
        app.logger.warning("log_request failed: %s", e)

    response = jsonify({'estimated_price': pred})
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response

if __name__ == "__main__":
    print("Starting Python Flask Server For Home Price Prediction on port 6001...")
    util.load_saved_artifacts()
    app.run(host="0.0.0.0", port=6001)