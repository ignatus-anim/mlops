from flask import Flask, request, jsonify, session
import util
import os
import uuid
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from log_db import log_request, log_feedback, get_conn, ENGINE_STR
from sqlalchemy import create_engine, text
import psutil
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Prometheus metrics
variant = os.getenv("MODEL_PREFIX", "unknown")
REQUEST_COUNT = Counter('predictions_total', 'Total predictions', ['variant', 'endpoint'])
REQUEST_LATENCY = Histogram('prediction_duration_seconds', 'Prediction latency', ['variant'])
ERROR_COUNT = Counter('prediction_errors_total', 'Total prediction errors', ['variant', 'error_type'])
SYSTEM_CPU = Gauge('system_cpu_percent', 'CPU usage percentage', ['variant'])
SYSTEM_MEMORY = Gauge('system_memory_percent', 'Memory usage percentage', ['variant'])
FEEDBACK_COUNT = Counter('feedback_total', 'Total feedback received', ['variant', 'feedback_type'])

@app.route('/api/get_location_names', methods=['GET'])
def get_location_names():
    return jsonify({
        'locations': util.get_location_names()
    })

@app.route('/api/predict_home_price', methods=['GET', 'POST'])
def predict_home_price():
    REQUEST_COUNT.labels(variant=variant, endpoint='predict').inc()
    
    try:
        total_sqft = float(request.form['total_sqft'])
        location = request.form['location']
        bhk = int(request.form['bhk'])
        bath = int(request.form['bath'])
        
        # Generate session ID if not exists
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Measure prediction time
        start_time = time.time()
        pred = util.get_estimated_price(location,total_sqft,bhk,bath)
        end_time = time.time()
        prediction_time_ms = (end_time - start_time) * 1000
        
        # Record latency in Prometheus
        REQUEST_LATENCY.labels(variant=variant).observe(end_time - start_time)
    
        # Log to DB with session, IP, and timing
        user_ip = request.remote_addr
        try:
            prediction_id = log_request(variant, location, total_sqft, bhk, bath, pred, 
                                      prediction_time_ms, session['session_id'], user_ip)
            session['last_prediction_id'] = prediction_id  # Store for feedback
        except Exception as e:
            app.logger.warning("log_request failed: %s", e)
            ERROR_COUNT.labels(variant=variant, error_type='db_log_failed').inc()
            prediction_id = None

    return jsonify({
        'estimated_price': pred,
        'prediction_id': prediction_id,
        'response_time_ms': round(prediction_time_ms, 2)
    })

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Endpoint for user feedback submission"""
    try:
        data = request.get_json()
        prediction_id = data.get('prediction_id') or session.get('last_prediction_id')
        feedback_type = data.get('feedback_type')  # 'rating', 'too_high', 'too_low', 'accurate'
        feedback_value = data.get('feedback_value')  # 1-5 rating or actual price
        feedback_text = data.get('feedback_text', '')
        
        if not prediction_id or not feedback_type:
            return jsonify({'error': 'Missing prediction_id or feedback_type'}), 400
        
        log_feedback(prediction_id, feedback_type, feedback_value, feedback_text, request.remote_addr)
        FEEDBACK_COUNT.labels(variant=variant, feedback_type=feedback_type).inc()
        
        return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        
    except Exception as e:
        app.logger.error("Feedback submission failed: %s", e)
        return jsonify({'error': 'Failed to record feedback'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with system metrics"""
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Update Prometheus system metrics
        SYSTEM_CPU.labels(variant=variant).set(cpu_percent)
        SYSTEM_MEMORY.labels(variant=variant).set(memory.percent)
        
        # Database connectivity test
        db_status = "healthy"
        try:
            with get_conn() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "model_variant": variant,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / 1024**3, 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / 1024**3, 2)
            },
            "database": db_status
        }
        
        return jsonify(health_data)
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get performance metrics from database"""
    try:
        hours_back = request.args.get('hours', 24, type=int)
        variant = os.getenv("MODEL_PREFIX")
        
        engine = create_engine(ENGINE_STR)
        with engine.begin() as conn:
            # Get prediction metrics
            metrics_data = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_predictions,
                    AVG(prediction_time_ms) as avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prediction_time_ms) as p95_latency_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY prediction_time_ms) as p99_latency_ms,
                    MIN(prediction_time_ms) as min_latency_ms,
                    MAX(prediction_time_ms) as max_latency_ms
                FROM prediction_logs 
                WHERE variant = :variant 
                  AND ts > now() - interval '%s hours'
            """) % hours_back, {"variant": variant}).fetchone()
            
            # Get feedback metrics
            feedback_data = conn.execute(text("""
                SELECT 
                    COUNT(*) as feedback_count,
                    AVG(CASE WHEN feedback_type = 'rating' THEN feedback_value END) as avg_rating,
                    COUNT(CASE WHEN feedback_type = 'accurate' THEN 1 END) as accurate_count,
                    COUNT(CASE WHEN feedback_type = 'too_high' THEN 1 END) as too_high_count,
                    COUNT(CASE WHEN feedback_type = 'too_low' THEN 1 END) as too_low_count
                FROM user_feedback uf
                JOIN prediction_logs pl ON uf.prediction_id = pl.id
                WHERE pl.variant = :variant 
                  AND uf.feedback_ts > now() - interval '%s hours'
            """) % hours_back, {"variant": variant}).fetchone()
        
        metrics = {
            "variant": variant,
            "time_period_hours": hours_back,
            "timestamp": datetime.utcnow().isoformat(),
            "predictions": {
                "total_count": metrics_data[0] or 0,
                "avg_latency_ms": round(metrics_data[1] or 0, 2),
                "p95_latency_ms": round(metrics_data[2] or 0, 2),
                "p99_latency_ms": round(metrics_data[3] or 0, 2),
                "min_latency_ms": round(metrics_data[4] or 0, 2),
                "max_latency_ms": round(metrics_data[5] or 0, 2)
            },
            "feedback": {
                "total_count": feedback_data[0] or 0,
                "avg_rating": round(feedback_data[1] or 0, 2),
                "accurate_count": feedback_data[2] or 0,
                "too_high_count": feedback_data[3] or 0,
                "too_low_count": feedback_data[4] or 0
            }
        }
        
        return jsonify(metrics)
        
    except Exception as e:
        app.logger.error(f"Metrics endpoint failed: {e}")
        return jsonify({'error': 'Failed to fetch metrics'}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent logs from JSON files"""
    try:
        log_type = request.args.get('type', 'predictions')  # 'predictions' or 'feedback'
        limit = request.args.get('limit', 100, type=int)
        
        log_dir = Path('/app/logs')
        if log_type == 'predictions':
            log_file = log_dir / 'predictions.jsonl'
        elif log_type == 'feedback':
            log_file = log_dir / 'feedback.jsonl'
        else:
            return jsonify({'error': 'Invalid log type. Use predictions or feedback'}), 400
        
        if not log_file.exists():
            return jsonify({
                'logs': [],
                'count': 0,
                'message': f'No {log_type} log file found'
            })
        
        # Read last N lines from file
        logs = []
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'log_type': log_type,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Logs endpoint failed: {e}")
        return jsonify({'error': 'Failed to fetch logs'}), 500

@app.route('/api/logs/tail', methods=['GET'])
def tail_logs():
    """Get live log stream (last few entries)"""
    try:
        log_type = request.args.get('type', 'predictions')
        lines = request.args.get('lines', 10, type=int)
        
        log_dir = Path('/app/logs')
        log_file = log_dir / f'{log_type}.jsonl'
        
        if not log_file.exists():
            return jsonify({'error': f'Log file {log_type}.jsonl not found'}), 404
        
        # Get last N lines
        import subprocess
        result = subprocess.run(['tail', '-n', str(lines), str(log_file)], 
                              capture_output=True, text=True)
        
        logs = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        return jsonify({
            'logs': logs,
            'count': len(logs),
            'log_type': log_type,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print("Starting Python Flask Server For Home Price Prediction on port 6001...")
    util.load_saved_artifacts()
    app.run(host="0.0.0.0", port=6001)
@app.route('/metrics', methods=['GET'])
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}