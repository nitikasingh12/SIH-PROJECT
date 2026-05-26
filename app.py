"""
app.py
Complete prototype:
- YOLOv8 people detection
- Flask server + Flask-SocketIO
- MJPEG video stream of annotated frames
- heatmap generation (saved to static/heatmap.png)
- optional IoT alert: Raspberry Pi GPIO OR Arduino serial
- simple SQLite logger (optional)

Run:
$ pip install -r requirements.txt
$ python app.py
Open http://<server-ip>:5000
"""

import io
import time
import threading
import datetime
import os

from flask import Flask, render_template, Response, send_from_directory
from flask_socketio import SocketIO
import cv2
import numpy as np
from ultralytics import YOLO
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Optional: SQLite logger
from sqlalchemy import create_engine, Column, Integer, DateTime, Table, MetaData
from sqlalchemy.sql import insert

# Optional serial for Arduino alerts
import serial  # pip install pyserial

# Optional Raspberry Pi GPIO (import will fail on non-RPi — guarded later)
try:
    import RPi.GPIO as GPIO
    ON_RPI = True
except Exception:
    ON_RPI = False

# ---------------- CONFIG ----------------
VIDEO_SOURCE = 0                # 0 = webcam, or RTSP URL "rtsp://user:pass@ip:554/stream"
MODEL_WEIGHTS = "yolov8n.pt"    # yolov8n is small & fast; ultralytics will auto-download
FRAME_WIDTH = 640
FRAME_HEIGHT = 360

# thresholds (count)
THRESHOLD_SAFE = 50
THRESHOLD_RISK = 100

# heatmap grid size (coarse)
HEAT_ROWS = 6
HEAT_COLS = 8

# heatmap update/save interval (seconds)
HEATMAP_SAVE_INTERVAL = 3.0

# IoT config (choose one)
USE_RPI_GPIO = False       # set True if running on Raspberry Pi GPIO
RPI_GPIO_PIN = 18

USE_ARDUINO_SERIAL = False  # set True if using Arduino serial to beep buzzer
ARDUINO_SERIAL_PORT = "/dev/ttyUSB0"  # change to your USB-serial port (Windows COMx)
ARDUINO_BAUDRATE = 9600

# web server
HOST = "0.0.0.0"
PORT = 5000
# ----------------------------------------

# Create necessary folders
if not os.path.exists("static"):
    os.makedirs("static")

# Initialize SQLite logger (optional)
engine = create_engine('sqlite:///counts.db', echo=False)
meta = MetaData()
counts_table = Table(
    'counts', meta,
    Column('id', Integer, primary_key=True),
    Column('timestamp', DateTime),
    Column('count', Integer),
)
meta.create_all(engine)

# Flask + SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Shared frame & lock
output_frame = None
frame_lock = threading.Lock()

# Heatmap accumulator (coarse grid)
heatmap = np.zeros((HEAT_ROWS, HEAT_COLS), dtype=np.float32)
last_heatmap_save = 0.0

# IoT setup
arduino_serial = None
if USE_ARDUINO_SERIAL:
    try:
        arduino_serial = serial.Serial(ARDUINO_SERIAL_PORT, ARDUINO_BAUDRATE, timeout=1)
        print("Arduino serial opened on", ARDUINO_SERIAL_PORT)
    except Exception as e:
        print("Could not open Arduino serial:", e)
        arduino_serial = None

if USE_RPI_GPIO and ON_RPI:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RPI_GPIO_PIN, GPIO.OUT)
    GPIO.output(RPI_GPIO_PIN, GPIO.LOW)

# load model
print("Loading YOLO model...")
model = YOLO(MODEL_WEIGHTS)   # will download weights if missing
print("Model loaded.")

# Video capture
cap = cv2.VideoCapture(VIDEO_SOURCE)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)


def classify_status(count):
    if count < THRESHOLD_SAFE:
        return "Safe", "green"
    elif count <= THRESHOLD_RISK:
        return "Risk", "yellow"
    else:
        return "Danger", "red"


def trigger_iot_alert(state):
    """
    state = True (danger) or False (not danger)
    Two examples shown: Raspberry Pi GPIO and Arduino serial command.
    """
    # Raspberry Pi GPIO
    if USE_RPI_GPIO and ON_RPI:
        GPIO.output(RPI_GPIO_PIN, GPIO.HIGH if state else GPIO.LOW)

    # Arduino via serial (send a short string)
    if USE_ARDUINO_SERIAL and arduino_serial:
        try:
            cmd = b'ALARM\n' if state else b'OK\n'
            arduino_serial.write(cmd)
        except Exception as e:
            print("Arduino write failed:", e)


def save_heatmap_image(hmap, out_path="static/heatmap.png"):
    global last_heatmap_save
    now = time.time()
    # only save every HEATMAP_SAVE_INTERVAL seconds
    if now - last_heatmap_save < HEATMAP_SAVE_INTERVAL:
        return
    last_heatmap_save = now

    # normalize & plot
    h = hmap.copy()
    if h.max() > 0:
        h = h / h.max()
    plt.figure(figsize=(4, 3))
    plt.imshow(h, interpolation='nearest', origin='lower')
    plt.title('Crowd Heatmap (coarse grid)')
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def log_count(count):
    # optional: log to SQLite
    try:
        with engine.connect() as conn:
            stmt = insert(counts_table).values(timestamp=datetime.datetime.now(), count=int(count))
            conn.execute(stmt)
    except Exception as e:
        print("SQLite log failed:", e)


def detector_thread():
    """
    Capture frames, run YOLO person detection, annotate frame,
    update heatmap and shared output_frame, and emit SocketIO updates.
    """
    global output_frame, heatmap

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Video source not available. Retrying in 1s...")
            time.sleep(1.0)
            continue

        # resize for speed
        h_original, w_original = frame.shape[:2]
        frame_resized = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # Run YOLO; filter class 0 (person)
        # Passing `classes=[0]` will make the model only detect persons.
        results = model(frame_resized, classes=[0], verbose=False)  # returns a Results object or list
        res0 = results[0]  # single frame

        # collect boxes (xyxy) and confidences
        boxes = []
        try:
            # ultralytics v8: res0.boxes.xyxy, res0.boxes.conf
            xyxy = res0.boxes.xyxy.cpu().numpy()  # shape (n,4)
            confs = res0.boxes.conf.cpu().numpy()
            # If class is available, you can check res0.boxes.cls
            for i, box in enumerate(xyxy):
                x1, y1, x2, y2 = box.astype(int)
                conf = float(confs[i])
                boxes.append((x1, y1, x2, y2, conf))
        except Exception:
            # fallback: maybe res0.boxes.xyxy already numpy array
            try:
                xyxy = np.array(res0.boxes.xyxy)
                for box in xyxy:
                    x1, y1, x2, y2 = [int(x) for x in box[:4]]
                    boxes.append((x1, y1, x2, y2, 0.0))
            except Exception:
                boxes = []

        # annotate frame
        annotated = frame_resized.copy()
        count_people = len(boxes)
        for (x1, y1, x2, y2, conf) in boxes:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"Person:{conf:.2f}" if conf else "Person"
            cv2.putText(annotated, label, (x1, max(y1 - 6, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # update heatmap (coarse grid): map center point to grid cell
        for (x1, y1, x2, y2, _) in boxes:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            col = int(cx / FRAME_WIDTH * HEAT_COLS)
            row = int(cy / FRAME_HEIGHT * HEAT_ROWS)
            col = max(0, min(HEAT_COLS - 1, col))
            row = max(0, min(HEAT_ROWS - 1, row))
            heatmap[row, col] += 1.0

        # smooth heatmap decay over time so old crowds fade
        heatmap *= 0.97

        # generate heatmap image periodically
        save_heatmap_image(heatmap, out_path="static/heatmap.png")

        # overlay count & status on annotated frame
        status_text, color_name = classify_status(count_people)
        color_bgr = (0, 255, 0) if color_name == "green" else ((0, 255, 255) if color_name == "yellow" else (0, 0, 255))
        cv2.putText(annotated, f"Count: {count_people}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_bgr, 2)
        cv2.putText(annotated, f"Status: {status_text}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_bgr, 2)

        # encode frame to jpeg bytes
        ret2, jpeg = cv2.imencode('.jpg', annotated)
        if ret2:
            with frame_lock:
                output_frame = jpeg.tobytes()

        # emit socketio update (so frontend updates count/status quickly)
        socketio.emit('count_update', {'count': int(count_people), 'status': status_text})

        # log to sqlite (optional, but can be enabled)
        # log_count(count_people)

        # IoT alert if Danger
        is_danger = count_people > THRESHOLD_RISK
        trigger_iot_alert(is_danger)

        # small sleep to avoid 100% CPU; detection model runtime dominates
        # no heavy sleep here; detection costs time itself.
        # but yield to eventlet/event loop
        socketio.sleep(0.01)


# video streaming generator (MJPEG)
def generate_mjpeg():
    global output_frame
    while True:
        with frame_lock:
            if output_frame is None:
                # create a blank image
                blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
                cv2.putText(blank, "Starting...", (20, FRAME_HEIGHT // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                ret2, jpeg = cv2.imencode('.jpg', blank)
                frame = jpeg.tobytes()
            else:
                frame = output_frame
        # outer boundary + frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        socketio.sleep(0.03)


# Flask routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')


# optional static heatmap fetch (already saved to static/heatmap.png)
@app.route('/heatmap.png')
def heatmap_png():
    return send_from_directory('static', 'heatmap.png')


# start detector thread before first request
@socketio.on('connect')
def client_connect():
    print("Client connected")


if __name__ == "__main__":
    # start detector background thread
    t = threading.Thread(target=detector_thread, daemon=True)
    t.start()
    print(f"Starting server on http://{HOST}:{PORT}")
    socketio.run(app, host=HOST, port=PORT)
