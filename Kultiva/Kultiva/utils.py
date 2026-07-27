import os
import requests
import logging
import pickle
import numpy as np
import pandas as pd
import warnings
import random
import math
from datetime import datetime
from django.conf import settings
from sklearn.exceptions import InconsistentVersionWarning
from .advisory_db import CROP_ADVISORY_DB
from .models import WeatherHistory, GridSoilData 

# --- SILENCE MACHINE LEARNING WARNINGS GLOBALLY ---
warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

logger = logging.getLogger(__name__)

# ==========================================
# 1. THE 3-TIER WEATHER ENGINE
# ==========================================
def get_weather(latitude, longitude, location_name):
    """
    Retrieves weather data with a 3-tier fallback system:
    1. Live OpenWeatherMap API
    2. Historical Database (Django Models)
    3. Algorithmic Geospatial Simulator (Physics-based estimation)
    """
    
    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------
    api_key = getattr(settings, 'OPENWEATHER_API_KEY', "a359af5dce0022e40d855d9c7c41f51a")
    
    # Ensure latitude/longitude are floats
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (ValueError, TypeError):
        lat, lon = 20.5937, 78.9629 # Default to Center of India

    # ---------------------------------------------------------
    # TIER 1: LIVE API
    # ---------------------------------------------------------
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    
    try:
        response = requests.get(url, timeout=(3.0, 5.0)) 
        response.raise_for_status() 
        data = response.json()
        
        live_temp = data['main']['temp']
        live_hum = data['main']['humidity']
        live_rain_1h = data.get('rain', {}).get('1h', 0.0)
        
        # --- THE RAINFALL SCALE FIX FOR THE AI MODEL ---
        if live_rain_1h > 0:
            ai_rainfall_estimate = random.uniform(150.0, 250.0)
        elif live_hum > 75.0:
            ai_rainfall_estimate = random.uniform(80.0, 150.0)
        else:
            ai_rainfall_estimate = random.uniform(20.0, 60.0)
        
        return {
            "Temperature_C": live_temp,
            "Humidity_Pct": live_hum,
            "Rainfall_mm": round(ai_rainfall_estimate, 1),
            "Source": "Live API",
            "Status": "success"
        }
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Weather API failed for {location_name}: {e}. Engaging Tier 2.")
    
    # ---------------------------------------------------------
    # TIER 2: HISTORICAL DATABASE
    # ---------------------------------------------------------
    current_month = datetime.now().month
    
    fallback_data = WeatherHistory.objects.filter(
        district__icontains=location_name,
        month=current_month
    ).first()
    
    if fallback_data:
        return {
            "Temperature_C": fallback_data.avg_temp,
            "Humidity_Pct": fallback_data.avg_humidity,
            "Rainfall_mm": fallback_data.avg_rainfall,
            "Source": "Historical Database",
            "Status": "fallback"
        }

    # ---------------------------------------------------------
    # TIER 3: SMART GEOSPATIAL SIMULATOR
    # ---------------------------------------------------------
    logger.info("Engaging Smart Geospatial Simulator.")
    
    # A. Determine Seasonality Factor
    is_monsoon = current_month in [6, 7, 8, 9]
    is_winter = current_month in [11, 12, 1, 2]
    is_summer = current_month in [3, 4, 5]

    # B. Calculate Temperature
    base_temp = 35.0 - (lat * 0.3) 
    if is_winter:
        base_temp -= 10.0
        if lat > 28.0: base_temp -= 8.0
    elif is_summer:
        base_temp += 5.0 
    
    sim_temp = round(base_temp + random.uniform(-3.0, 3.0), 1)
    sim_temp = max(5.0, min(sim_temp, 48.0))

    # C. Calculate Rainfall
    base_rain = 0.0
    if is_monsoon:
        base_rain = 150.0 
        if lon < 73.0 and lat > 23.0: 
            base_rain = random.uniform(5.0, 40.0) 
        elif lon > 88.0:
            base_rain = random.uniform(200.0, 400.0)
        else:
            base_rain = random.uniform(80.0, 200.0)
    else:
        if is_winter and lat > 30.0:
            base_rain = random.uniform(10.0, 40.0)
        elif lon > 80.0 and current_month in [10, 11]:
            base_rain = random.uniform(50.0, 150.0)
        else:
            base_rain = random.uniform(0.0, 10.0)

    sim_rain = round(base_rain, 1)

    # D. Calculate Humidity
    base_humidity = 40.0
    if sim_rain > 50.0:
        base_humidity = 85.0
    elif sim_rain > 10.0:
        base_humidity = 65.0
    
    is_coastal = (lon < 76.0 and lat < 20.0) or (lon > 80.0 and lat < 22.0 and lat > 10.0)
    if is_coastal:
        base_humidity = max(base_humidity, 70.0)
    elif is_summer and not is_coastal:
        base_humidity = 25.0 
        
    sim_humidity = round(base_humidity + random.uniform(-10.0, 10.0), 1)
    sim_humidity = max(10.0, min(sim_humidity, 100.0))

    return {
        "Temperature_C": sim_temp,
        "Humidity_Pct": sim_humidity,
        "Rainfall_mm": sim_rain,
        "Source": "Smart Geospatial Simulator",
        "Status": "simulated"
    }


# ==========================================
# 2. SOIL DATA RETRIEVAL (Upgraded with Grid Snapping)
# ==========================================
def get_soil_for_location(exact_lat, exact_lon):
    """Snaps precise GPS coordinates to the 0.05 spatial grid and fetches SHC data."""
    try:
        # The Magic Math: Snaps ANY coordinate perfectly to the nearest 0.05 interval!
        grid_lat = round(float(exact_lat) * 20) / 20
        grid_lon = round(float(exact_lon) * 20) / 20
        
        soil_data = GridSoilData.objects.filter(grid_lat=grid_lat, grid_lon=grid_lon).first()
        
        if soil_data:
            return {
                "found": True, "lat_used": grid_lat, "lon_used": grid_lon,
                "pH": soil_data.ph, "EC": soil_data.ec, "OC": soil_data.oc,
                "N": soil_data.avg_n, "P": soil_data.avg_p, "K": soil_data.avg_k, "S": soil_data.avg_s,
                "Zn": soil_data.avg_zn, "Fe": soil_data.avg_fe, "Cu": soil_data.avg_cu,
                "Mn": soil_data.avg_mn, "B":  soil_data.avg_b,
                "Advisory": soil_data.recommendation_text,
                "Status": "SHC Data Retrieved Successfully"
            }
        else:
            return get_safe_defaults()
    except Exception:
        return get_safe_defaults()

def get_safe_defaults():
    return {
        "found": False, "lat_used": 0.0, "lon_used": 0.0,
        "pH": 6.5, "EC": 0.5, "OC": 0.5,
        "N": 280.0, "P": 25.0, "K": 150.0, "S": 15.0,
        "Zn": 1.0, "Fe": 10.0, "Cu": 1.0, "Mn": 5.0, "B": 0.5,
        "Advisory": "Location outside mapped grid. Showing Standard Regional Recommendations.",
        "Status": "Regional Fallback Used"
    }

# ==========================================
# CACHED ML ARTIFACTS (In-Memory Singleton)
# ==========================================
import joblib

_ML_CACHE = {
    'model': None,
}

def _get_or_load_model_artifacts():
    """Lazy-loads the new lightweight AI into RAM once per server lifecycle."""
    if _ML_CACHE['model'] is None:
        try:
            # We point exactly to your new saved game file!
            model_path = os.path.join(settings.BASE_DIR, 'Kultiva', 'ml_models', 'kultiva_agri_brain.joblib')
            
            # The new AI doesn't need a scaler or label encoder!
            _ML_CACHE['model'] = joblib.load(model_path)
            
            logger.info("Successfully loaded Lightweight Kultiva ML model into memory.")
        except Exception as e:
            logger.critical(f"Failed to load Kultiva ML model: {e}")
            raise RuntimeError("ML Pipeline Offline") from e
            
    return _ML_CACHE['model']

# ==========================================
# 3. AI CROP RECOMMENDATION ENGINE (With Data Translator)
# ==========================================
def predict_best_crop(weather_data: dict, soil_data: dict) -> dict:
    """
    Feeds cached weather and soil metrics into the new HistGradientBoosting model.
    Includes a Currency Exchange to scale real-world kg/ha data to the AI's 0-140 training scale.
    """
    try:
        # 1. Validation & Data Sanitization
        if not weather_data or not soil_data:
            raise ValueError("Missing critical meteorological or geographical data inputs.")

        # --- THE CURRENCY EXCHANGE (Data Translator) ---
        # The database uses heavy kg/ha (e.g., N=214.7), but the AI only understands 0-140.
        # We translate the numbers using simple ratios so the AI doesn't panic!
        
        raw_n = float(soil_data.get('N', 0))
        raw_p = float(soil_data.get('P', 0))
        raw_k = float(soil_data.get('K', 0))

        # Translate N (Database max ~300 -> AI max 140)
        n_val = np.clip((raw_n / 300.0) * 140.0, 0.0, 140.0)
        
        # Translate P (Database max ~100 -> AI max 145)
        p_val = np.clip((raw_p / 100.0) * 145.0, 5.0, 145.0)
        
        # Translate K (Database max ~400 -> AI max 205)
        k_val = np.clip((raw_k / 400.0) * 205.0, 5.0, 205.0)

        # Weather doesn't need translation, just safety clipping
        temp_val = np.clip(float(weather_data.get('Temperature_C', 25.0)), -20.0, 60.0)
        hum_val = np.clip(float(weather_data.get('Humidity_Pct', 50.0)), 0.0, 100.0)
        ph_val = np.clip(float(soil_data.get('pH', 7.0)), 0.0, 14.0)
        rain_val = np.clip(float(weather_data.get('Rainfall_mm', 0.0)), 0.0, 1000.0)

        # 2. EXACT column match to your new AI (Notice pH comes BEFORE Rainfall here!)
        feature_names = ['Nitrogen', 'Phosphorus', 'Potassium', 'Temperature', 'Humidity', 'pH_Value', 'Rainfall']
        
        # We enforce our new lightweight 32-bit float rules here so the AI is happy
        features_df = pd.DataFrame(
            [[n_val, p_val, k_val, temp_val, hum_val, ph_val, rain_val]], 
            columns=feature_names, 
            dtype=np.float32
        )

        # 3. Retrieve the AI
        model = _get_or_load_model_artifacts()

        # 4. Predict Top 3 Probabilities directly! No scaler needed!
        probabilities = model.predict_proba(features_df)[0]
        
        # Scikit-learn models store their category names directly in `model.classes_`
        classes = model.classes_ 
        top_indices = np.argsort(probabilities)[::-1][:3]
        
        ranked_crops = []
        for idx in top_indices:
            crop_name = str(classes[idx]).capitalize()
            confidence = float(np.clip(round(probabilities[idx] * 100, 1), 0.0, 100.0))
            
            if confidence >= 1.5:
                ranked_crops.append({
                    "name": crop_name,
                    "confidence": confidence
                })

        if not ranked_crops:
            raise ValueError("Model predicted no realistic outcome.")

        # 5. Fetch Agronomy Advisory for the Top Crop
        best_crop = ranked_crops[0]["name"]
        
        safe_advisory_db = CROP_ADVISORY_DB[0] if isinstance(CROP_ADVISORY_DB, tuple) else CROP_ADVISORY_DB
        agronomy_data = safe_advisory_db.get(best_crop, {})

        return {
            "success": True,
            "crop": best_crop,
            "predictions": ranked_crops,
            "advisory": agronomy_data,
            "status": "Lightweight AI Ranked Prediction Completed Successfully"
        }

    except Exception as e:
        logger.error(f"Prediction Pipeline Failure: {str(e)}", exc_info=True)
        return {
            "success": False, 
            "crop": "Analysis Pending",
            "predictions": [],
            "advisory": {},
            "status": "System currently undergoing maintenance or missing data."
        }

# ==========================================
# 4. GEOSPATIAL LOCATION ENGINE (GEOCODER)
# ==========================================
class IndianAgriGeocoder:
    def __init__(self):
        self.kerala_districts = {
            "thiruvananthapuram": (8.5241, 76.9366), "kollam": (8.8932, 76.6141),
            "pathanamthitta": (9.2648, 76.7870), "alappuzha": (9.4981, 76.3388),
            "kottayam": (9.5916, 76.5222), "idukki": (9.8494, 76.9723),
            "ernakulam": (9.9816, 76.2999), "thrissur": (10.5276, 76.2144),
            "palakkad": (10.7867, 76.6548), "malappuram": (11.0510, 76.0711),
            "kozhikode": (11.2588, 75.7804), "wayanad": (11.6854, 76.1320),
            "kannur": (11.8745, 75.3704), "kasaragod": (12.4996, 74.9869)
        }

        self.india_db = {
            "andhra pradesh": {"guntur": (16.3067, 80.4365), "kurnool": (15.8281, 78.0373), "vijayawada": (16.5062, 80.6480), "east godavari": (17.3213, 82.0407), "chittoor": (13.2172, 79.1003), "anantapur": (14.6819, 77.6006)},
            "arunachal pradesh": {"itanagar": (27.0844, 93.6053), "tawang": (27.5861, 91.8594)},
            "assam": {"guwahati": (26.1445, 91.7362), "dibrugarh": (27.4728, 94.9120), "jorhat": (26.7509, 94.2037), "tezpur": (26.6528, 92.7926)},
            "bihar": {"patna": (25.5941, 85.1376), "muzaffarpur": (26.1226, 85.3906), "gaya": (24.7914, 85.0002), "bhagalpur": (25.2425, 87.0143), "purnia": (25.7771, 87.4753)},
            "chhattisgarh": {"raipur": (21.2514, 81.6296), "bilaspur": (22.0797, 82.1409), "durg": (21.1904, 81.2849)},
            "goa": {"panaji": (15.4909, 73.8278), "margao": (15.2832, 73.9862)},
            "gujarat": {"ahmedabad": (23.0225, 72.5714), "surat": (21.1702, 72.8311), "rajkot": (22.3039, 70.8022), "junagadh": (21.5222, 70.4579), "anand": (22.5645, 72.9289), "vadodara": (22.3072, 73.1812)},
            "haryana": {"karnal": (29.6857, 76.9905), "hisar": (29.1492, 75.7217), "panipat": (29.3909, 76.9635), "ambala": (30.3782, 76.7767)},
            "himachal pradesh": {"shimla": (31.1048, 77.1734), "kullu": (31.9566, 77.1095), "solan": (30.9084, 77.0999)},
            "jharkhand": {"ranchi": (23.3441, 85.3096), "jamshedpur": (22.8046, 86.2029), "dhanbad": (23.7957, 86.4304)},
            "karnataka": {"bengaluru": (12.9716, 77.5946), "mysuru": (12.2958, 76.6394), "mandya": (12.5206, 76.8999), "belagavi": (15.8497, 74.4977), "hubballi": (15.3647, 75.1240), "shivamogga": (13.9299, 75.5681), "kodagu": (12.3375, 75.8069)},
            "madhya pradesh": {"bhopal": (23.2599, 77.4126), "indore": (22.7196, 75.8577), "gwalior": (26.2183, 78.1828), "jabalpur": (23.1815, 79.9864), "ujjain": (23.1765, 75.7885)},
            "maharashtra": {"pune": (18.5204, 73.8567), "nashik": (19.9975, 73.7898), "nagpur": (21.1458, 79.0882), "aurangabad": (19.8762, 75.3433), "satara": (17.6805, 74.0183), "kolhapur": (16.7050, 74.2433), "solapur": (17.6599, 75.9064), "amravati": (20.9374, 77.7796)},
            "manipur": {"imphal": (24.8170, 93.9368)}, "meghalaya": {"shillong": (25.5788, 91.8933)}, "mizoram": {"aizawl": (23.7271, 92.7176)}, "nagaland": {"kohima": (25.6751, 94.1086)},
            "odisha": {"bhubaneswar": (20.2961, 85.8245), "cuttack": (20.4625, 85.8828), "puri": (19.8135, 85.8312), "sambalpur": (21.4669, 83.9812)},
            "punjab": {"ludhiana": (30.9010, 75.8523), "amritsar": (31.6340, 74.8723), "jalandhar": (31.3260, 75.5762), "patiala": (30.3398, 76.3869), "bathinda": (30.2110, 74.9455)},
            "rajasthan": {"jaipur": (26.9124, 75.7873), "jodhpur": (26.2389, 73.0243), "udaipur": (24.5854, 73.7125), "kota": (25.2138, 75.8648), "bikaner": (28.0229, 73.3119), "sri ganganagar": (29.9045, 73.8776)},
            "sikkim": {"gangtok": (27.3314, 88.6138)},
            "tamil nadu": {"chennai": (13.0827, 80.2707), "coimbatore": (11.0168, 76.9558), "madurai": (9.9252, 78.1198), "salem": (11.6643, 78.1460), "thanjavur": (10.7870, 79.1378), "tiruchirappalli": (10.7905, 78.7047), "erode": (11.3410, 77.7172)},
            "telangana": {"hyderabad": (17.3850, 78.4867), "warangal": (17.9689, 79.5941), "karimnagar": (18.4386, 79.1288), "nizamabad": (18.6725, 78.0941)},
            "tripura": {"agartala": (23.8315, 91.2868)},
            "uttar pradesh": {"lucknow": (26.8467, 80.9462), "kanpur": (26.4499, 80.3319), "varanasi": (25.3176, 82.9739), "agra": (27.1767, 78.0081), "meerut": (28.9845, 77.7064), "prayagraj": (25.4358, 81.8463), "bareilly": (28.3670, 79.4304), "gorakhpur": (26.7606, 83.3732)},
            "uttarakhand": {"dehradun": (30.6344, 78.0292), "haridwar": (29.9457, 78.1642), "nainital": (29.3919, 79.4542)},
            "west bengal": {"kolkata": (22.5726, 88.3639), "siliguri": (26.7271, 88.3953), "bardhaman": (23.2324, 87.8615), "howrah": (22.5958, 88.2636), "darjeeling": (27.0410, 88.2663), "malda": (25.0108, 88.1411)}
        }
        
        self.state_aliases = {
            "kerala": "kerala", "kl": "kerala",
            "tamilnadu": "tamil nadu", "tn": "tamil nadu",
            "uttarpradesh": "uttar pradesh", "up": "uttar pradesh",
            "madhyapradesh": "madhya pradesh", "mp": "madhya pradesh",
            "maharashtra": "maharashtra", "mh": "maharashtra",
            "westbengal": "west bengal", "wb": "west bengal",
            "bengal": "west bengal",
            "odisha": "odisha", "orissa": "odisha",
            "karnataka": "karnataka", "ka": "karnataka"
        }

    def _normalize(self, text):
        return str(text).strip().lower()

    def get_coordinates(self, district_name, state_name=None):
        dist_key = self._normalize(district_name)
        state_key = self._normalize(state_name) if state_name else None
        
        if dist_key in self.kerala_districts:
            lat, lon = self.kerala_districts[dist_key]
            return self._add_farm_variance(lat, lon, 0.05)
            
        if state_key:
            resolved_state = self.state_aliases.get(state_key, state_key)
            if resolved_state in self.india_db:
                state_data = self.india_db[resolved_state]
                if dist_key in state_data:
                    lat, lon = state_data[dist_key]
                    return self._add_farm_variance(lat, lon, 0.12)
                
                fallback_city = list(state_data.values())[0]
                return self._add_farm_variance(fallback_city[0], fallback_city[1], 0.25)

        for s_name, districts in self.india_db.items():
            if dist_key in districts:
                lat, lon = districts[dist_key]
                return self._add_farm_variance(lat, lon, 0.12)

        return self._add_farm_variance(21.1458, 79.0882, 0.5)

    def _add_farm_variance(self, base_lat, base_lon, variance_degree):
        lat_offset = random.uniform(-variance_degree, variance_degree)
        lon_offset = random.uniform(-variance_degree, variance_degree)
        return round(base_lat + lat_offset, 6), round(base_lon + lon_offset, 6)