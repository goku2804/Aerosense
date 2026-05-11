# IMPORTS
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

from xgboost import XGBRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

# LOAD DATA
df = pd.read_excel('air.xlsx')

# DATETIME PROCESSING
df['from'] = pd.to_datetime(df['from'])
df['to'] = pd.to_datetime(df['to'])

df['day'] = df['from'].dt.day_name().str[:3]

def time_category(dt):
    hour = dt.hour
    if 5 <= hour < 12:
        return "Mrng"
    elif 12 <= hour < 17:
        return "Noon"
    else:
        return "Evng"

df['time'] = df['to'].apply(time_category)

df.drop(columns=['from', 'to'], inplace=True)
df.drop(columns=['case', 'day type'], inplace=True)

# ENCODING
day_map = {'Sun':0,'Mon':1,'Tue':2,'Wed':3,'Thu':4,'Fri':5,'Sat':6}
place_map = {'Canteen':0,'Parking':1,'Class':2}
time_map = {'Mrng':0,'Noon':1,'Evng':2}

df['day'] = df['day'].map(day_map)
df['place'] = df['place'].map(place_map)
df['time'] = df['time'].map(time_map)

# SORT DATA
df = df.sort_values(['day', 'time'])

# FEATURES & TARGETS
X_context = df[['place', 'day', 'time']].values
Y_targets = df[['co_ppm','hum','mq7_raw','pm1','pm10','pm25','temp']].values

# SEQUENCE CREATION
SEQ_LEN = 5

X_lstm = []
Y_lstm = []

for i in range(len(Y_targets) - SEQ_LEN):
    X_lstm.append(Y_targets[i:i+SEQ_LEN])
    Y_lstm.append(Y_targets[i+SEQ_LEN])

X_lstm = np.array(X_lstm)
Y_lstm = np.array(Y_lstm)

# LSTM MODEL
lstm_model = Sequential([
    LSTM(64, input_shape=(SEQ_LEN, 7), return_sequences=False),
    Dense(32, activation='relu'),
    Dense(7)
])

lstm_model.compile(optimizer='adam', loss='mse')
lstm_model.fit(X_lstm, Y_lstm, epochs=30, batch_size=16)

# EXTRACT FEATURES
lstm_features = lstm_model.predict(X_lstm, verbose=0)

# HYBRID MODEL (XGBOOST)
X_hybrid = np.hstack([lstm_features, X_context[SEQ_LEN:]])

xgb = MultiOutputRegressor(
    XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4
    )
)

xgb.fit(X_hybrid, Y_lstm)

# SAMPLE PREDICTION (ONE CLEAN VERSION)
input_day = "Thu"
input_place = "Canteen"
input_time = "Noon"

last_sensor_readings = [
    [3.16228, 32, 10, 120, 3900, 65, 33.5],
    [5.23832, 33, 14, 125, 2950, 70, 33.7],
    [3.64829, 32, 11, 133, 3024, 71, 33.9],
    [5.809477, 34, 15, 140, 3387, 69, 34.1],
    [6.43168, 35, 17, 145, 3287, 68, 34.3]
]

# Encoding
day_enc = day_map[input_day]
place_enc = place_map[input_place]
time_enc = time_map[input_time]

context_input = np.array([[place_enc, day_enc, time_enc]])

# LSTM prediction
lstm_input = np.array(last_sensor_readings).reshape(1, SEQ_LEN, 7)
lstm_out = lstm_model.predict(lstm_input, verbose=0)

# Final prediction
hybrid_input = np.hstack([lstm_out, context_input])
prediction = xgb.predict(hybrid_input)

sensor_names = ['co_ppm','hum','mq7_raw','pm1','pm10','pm25','temp']

print("\nPredicted Environmental Values:\n")
for name, value in zip(sensor_names, prediction[0]):
    print(f"{name:8s}: {value:.2f}")

# SAVE MODELS
lstm_model.save("lstm_model.keras")
joblib.dump(xgb, "xgboost_model.pkl")

# MODEL EVALUATION
X_lstm_test = []
Y_test = []

for i in range(len(Y_targets) - SEQ_LEN):
    X_lstm_test.append(Y_targets[i:i+SEQ_LEN])
    Y_test.append(Y_targets[i+SEQ_LEN])

X_lstm_test = np.array(X_lstm_test)
Y_test = np.array(Y_test)

lstm_features_test = lstm_model.predict(X_lstm_test, verbose=0)
X_hybrid_test = np.hstack([lstm_features_test, X_context[SEQ_LEN:]])

Y_pred = xgb.predict(X_hybrid_test)

rmse = np.sqrt(mean_squared_error(Y_test, Y_pred))
mae = mean_absolute_error(Y_test, Y_pred)
r2 = r2_score(Y_test, Y_pred)

print("\nHybrid Model Performance")
print(f"RMSE : {rmse:.3f}")
print(f"MAE  : {mae:.3f}")
print(f"R²   : {r2:.3f}")

# CONFUSION MATRIX (PM2.5)
def pm25_to_aqi_category(pm):
    if pm <= 12:
        return 0
    elif pm <= 35.4:
        return 1
    elif pm <= 55.4:
        return 2
    elif pm <= 150.4:
        return 3
    elif pm <= 250.4:
        return 4
    else:
        return 5

actual_pm25 = Y_test[:,5]
pred_pm25 = Y_pred[:,5]

actual_classes = [pm25_to_aqi_category(x) for x in actual_pm25]
pred_classes = [pm25_to_aqi_category(x) for x in pred_pm25]

cm = confusion_matrix(actual_classes, pred_classes)

disp = ConfusionMatrixDisplay(confusion_matrix=cm)
disp.plot(cmap="Blues")
plt.title("AQI Confusion Matrix (PM2.5)")
plt.show()

# ACTUAL vs PREDICTED GRAPH
plt.figure(figsize=(6,6))
plt.scatter(Y_test[:,5], Y_pred[:,5])
plt.xlabel("Actual PM2.5")
plt.ylabel("Predicted PM2.5")
plt.title("Actual vs Predicted PM2.5")
plt.grid(True)
plt.show()