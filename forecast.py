import time
import numpy as np
import joblib
from tensorflow.keras.models import load_model
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

# FIREBASE INITIALIZATION
cred = credentials.Certificate("air-quality.json")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://air-quality226-default-rtdb.firebaseio.com/"
    })

sensor_ref = db.reference("sensor")
fan_ref = db.reference("actuator/fan")
mode_ref = db.reference("actuator/mode")
prediction_ref = db.reference("prediction")

# LOAD MODELS (ONLY ONCE)
lstm_model = load_model("lstm_model.keras", compile=False)
xgb_model = joblib.load("xgboost_model.pkl")

# SETTINGS
SEQ_LEN = 5
POLL_INTERVAL = 10
ALPHA = 0.35
MAX_CHANGE = 0.15

history = []
last_fan_state = None

# CATEGORY FUNCTION
def cat_pm25(pm):
    if  pm<= 15:
        return "Good"
    elif pm <= 35.4:
        return "Moderate"
    elif pm <= 55.4:
        return "Unhealthy for Sensitive Groups"
    elif pm <= 150.4:
        return "Unhealthy"
    elif pm <= 250.4:
        return "Very Unhealthy"
    else:
        return "Hazardous"

# CAP FUNCTION
def cap(cur, pred):
    lo = cur * (1 - MAX_CHANGE)
    hi = cur * (1 + MAX_CHANGE)
    return float(np.clip(pred, lo, hi))
# MAIN LOOP
print("🚀 Forecast backend started (Optimized Version)")

while True:
    start_time = time.time()

    # ================= READ SENSOR =================
    data = sensor_ref.get()
    if not data:
        time.sleep(POLL_INTERVAL)
        continue

    # ================= READ MODE =================
    current_mode = mode_ref.get() or "AUTO"

    try:
        co = float(data["co_ppm"])
        hum = float(data["hum"])
        mq7 = float(data["mq7_raw"])
        pm1 = float(data["pm1"])
        pm10 = float(data["pm10"])
        pm25 = float(data["pm25"])
        temp = float(data["temp"])
    except Exception as e:
        print("⚠️ Sensor error:", e)
        time.sleep(POLL_INTERVAL)
        continue

    print(f"📡 LIVE → PM2.5={pm25:.1f}, PM10={pm10:.1f}, CO={co:.2f}")

    # ================= HISTORY =================
    history.append([co, hum, mq7, pm1, pm10, pm25, temp])

    if len(history) > SEQ_LEN:
        history.pop(0)

    if len(history) < SEQ_LEN:
        print(f"⏳ Buffer {len(history)}/{SEQ_LEN}")
        time.sleep(POLL_INTERVAL)
        continue

    # ================= MODEL =================
    X_lstm = np.array(history).reshape(1, SEQ_LEN, 7)
    lstm_feat = lstm_model.predict(X_lstm, verbose=0)

    now = datetime.now()
    context = np.array([[0, now.weekday(), 0]])

    hybrid = np.hstack([lstm_feat, context])
    raw = xgb_model.predict(hybrid)[0]

    raw_pm25 = float(raw[5])
    raw_pm10 = float(raw[4])
    raw_co = float(raw[0])

    # ================= BLENDED =================
    pm25_f = cap(pm25, ALPHA * raw_pm25 + (1 - ALPHA) * pm25)
    pm10_f = cap(pm10, ALPHA * raw_pm10 + (1 - ALPHA) * pm10)
    co_f = cap(co, ALPHA * raw_co + (1 - ALPHA) * co)

    pm25_cat = cat_pm25(pm25_f)

    # ================= FAN CONTROL =================
    if current_mode == "EMERGENCY":
        fan = 1
    elif current_mode == "FORCE_OFF":
        fan = 0
    else:
        fan = pm25_cat in {"Unhealthy", "Very Unhealthy", "Hazardous"}

    # Only update Firebase if state changed
    if fan != last_fan_state:
        fan_ref.set(int(fan))
        last_fan_state = fan

    # ================= FIREBASE OUTPUT =================
    prediction_ref.set({
        "pm25": [
            round(pm25, 2),
            round(pm25_f, 2),
            round(pm25_f * 1.02, 2),
            round(pm25_f * 1.04, 2)
        ],
        "pm10": [
            round(pm10, 2),
            round(pm10_f, 2),
            round(pm10_f * 1.01, 2),
            round(pm10_f * 1.02, 2)
        ],
        "co": [
            round(co, 2),
            round(co_f, 2),
            round(co_f * 1.01, 2),
            round(co_f * 1.02, 2)
        ],
        "timestamp": int(time.time())
    })

    print(f"🔮 PM2.5 forecast → {pm25_f:.1f} ({pm25_cat})")
    print(f"🌀 FAN → {'ON' if fan else 'OFF'} | Mode: {current_mode}")
    print("--------------------------------------------------")

    # Maintain fixed interval
    elapsed = time.time() - start_time
    time.sleep(max(0, POLL_INTERVAL - elapsed))