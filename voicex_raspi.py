import serial
import time
import os
import json
import threading
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
from flask import Flask, render_template, request, jsonify
import logging
from datetime import datetime

SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
DATA_DIR = os.path.expanduser('~/voicex_data')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
LOG_FILE = os.path.join(DATA_DIR, 'usage_log.csv')
PHRASES_DIR = os.path.join(DATA_DIR, 'phrases')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PHRASES_DIR, exist_ok=True)

serial_conn = None
collected_data = []
is_collecting = False
current_config = {
    'threshold': 500,
    'base_frequency': 100,
    'mod_frequency': 200,
    'filter_alpha': 20,
    'min_activity_duration': 200
}

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config():
    global current_config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                current_config = json.load(f)
            logging.info("Configuration loaded")
        else:
            save_config()
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_config, f, indent=4)
        logging.info("Configuration saved")
    except Exception as e:
        logging.error(f"Error saving configuration: {e}")

def setup_serial():
    global serial_conn
    try:
        serial_conn = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logging.info(f"Connected to ESP32 on {SERIAL_PORT}")
        return True
    except Exception as e:
        logging.error(f"Error connecting to ESP32: {e}")
        return False

def send_config_to_esp32():
    if not serial_conn:
        logging.error("No connection to ESP32")
        return False
    
    try:
        for key, value in current_config.items():
            command = f"CONFIG:{key},{value}\n"
            serial_conn.write(command.encode('utf-8'))
            time.sleep(0.1)
        
        logging.info("Settings sent to ESP32")
        return True
    except Exception as e:
        logging.error(f"Error sending settings: {e}")
        return False

def read_serial_data():
    global collected_data, is_collecting
    
    if not serial_conn:
        logging.error("No connection to ESP32")
        return
    
    while True:
        try:
            if serial_conn.in_waiting > 0:
                line = serial_conn.readline().decode('utf-8').strip()
                
                if line.startswith("DEBUG:"):
                    debug_data = line[6:].split(',')
                    if is_collecting and len(debug_data) >= 3:
                        try:
                            values = [float(x) for x in debug_data]
                            collected_data.append(values)
                            
                            if len(collected_data) > 1000:
                                collected_data = collected_data[-1000:]
                        except ValueError:
                            pass
                
                elif line.startswith("SPEECH_START"):
                    log_usage_event("speech_start")
                    is_collecting = True
                
                elif line.startswith("SPEECH_END"):
                    duration = line.split(':')[1] if ':' in line else "unknown"
                    log_usage_event("speech_end", {"duration": duration})
                    is_collecting = False
                
                elif line.startswith("ERROR:"):
                    error_msg = line[6:]
                    logging.error(f"ESP32 reports error: {error_msg}")
        
        except Exception as e:
            logging.error(f"Error reading data: {e}")
            time.sleep(1)
        
        time.sleep(0.01)

def log_usage_event(event_type, additional_data=None):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                f.write("timestamp,event_type,additional_data\n")
        
        with open(LOG_FILE, 'a') as f:
            additional = json.dumps(additional_data) if additional_data else ""
            f.write(f"{timestamp},{event_type},{additional}\n")
    
    except Exception as e:
        logging.error(f"Error writing to log: {e}")

def send_phrase_to_esp32(phrase_id):
    phrase_file = os.path.join(PHRASES_DIR, f"{phrase_id}.json")
    
    if not os.path.exists(phrase_file):
        logging.error(f"Phrase with ID {phrase_id} not found")
        return False
    
    try:
        with open(phrase_file, 'r') as f:
            phrase_data = json.load(f)
        
        if serial_conn:
            command = f"PLAY_PHRASE:{phrase_id}\n"
            serial_conn.write(command.encode('utf-8'))
            logging.info(f"Sent command to play phrase {phrase_id}")
            return True
    
    except Exception as e:
        logging.error(f"Error sending phrase: {e}")
    
    return False

@app.route('/')
def index():
    phrases = []
    for filename in os.listdir(PHRASES_DIR):
        if filename.endswith('.json'):
            phrase_id = filename.split('.')[0]
            try:
                with open(os.path.join(PHRASES_DIR, filename), 'r') as f:
                    phrase_data = json.load(f)
                    phrases.append({
                        'id': phrase_id,
                        'name': phrase_data.get('name', phrase_id),
                        'description': phrase_data.get('description', '')
                    })
            except:
                pass
    
    return render_template('index.html', 
                           config=current_config,
                           phrases=phrases,
                           connected=(serial_conn is not None))

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    global current_config
    
    if request.method == 'GET':
        return jsonify(current_config)
    
    elif request.method == 'POST':
        try:
            new_config = request.json
            for key, value in new_config.items():
                if key in current_config:
                    current_config[key] = value
            
            save_config()
            if serial_conn:
                send_config_to_esp32()
            
            return jsonify({"status": "success", "config": current_config})
        
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/visualize')
def api_visualize():
    return render_template('visualize.html')

@app.route('/api/data')
def api_data():
    global collected_data
    return jsonify(collected_data[-100:] if collected_data else [])

@app.route('/api/phrase', methods=['POST'])
def api_save_phrase():
    try:
        phrase_data = request.json
        phrase_id = phrase_data.get('id', str(int(time.time())))
        
        with open(os.path.join(PHRASES_DIR, f"{phrase_id}.json"), 'w') as f:
            json.dump(phrase_data, f, indent=4)
        
        return jsonify({"status": "success", "id": phrase_id})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/play_phrase/<phrase_id>')
def api_play_phrase(phrase_id):
    success = send_phrase_to_esp32(phrase_id)
    return jsonify({"status": "success" if success else "error"})

@app.route('/api/stats')
def api_stats():
    try:
        usage_stats = {
            'total_sessions': 0,
            'total_duration': 0,
            'average_duration': 0,
            'daily_usage': {}
        }
        
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()[1:]
                
                sessions = 0
                total_duration = 0
                current_day = None
                
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        timestamp, event_type = parts[0], parts[1]
                        day = timestamp.split()[0]
                        
                        if event_type == "speech_start":
                            sessions += 1
                        
                        if event_type == "speech_end" and len(parts) >= 3:
                            try:
                                additional_data = json.loads(parts[2])
                                duration = float(additional_data.get("duration", 0))
                                total_duration += duration
                            except:
                                pass
                        
                        if day != current_day:
                            current_day = day
                            if day not in usage_stats['daily_usage']:
                                usage_stats['daily_usage'][day] = 0
                        
                        if event_type == "speech_start":
                            usage_stats['daily_usage'][day] = usage_stats['daily_usage'].get(day, 0) + 1
                
                usage_stats['total_sessions'] = sessions
                usage_stats['total_duration'] = total_duration
                if sessions > 0:
                    usage_stats['average_duration'] = total_duration / sessions
        
        return jsonify(usage_stats)
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def main():
    load_config()
    
    if setup_serial():
        send_config_to_esp32()
        
        serial_thread = threading.Thread(target=read_serial_data, daemon=True)
        serial_thread.start()
    
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)

if __name__ == "__main__":
    main()