"""Production crop-prediction service boundary.

The predictor now owns feature translation, artifact loading and ranking. The
legacy utility remains a compatibility caller until dashboard views are migrated.
"""
import logging
import os

import joblib
import numpy as np
import pandas as pd

from django.conf import settings

from backend.apps.advisory.services import get_crop_advisory

logger = logging.getLogger(__name__)
_MODEL_CACHE = {"model": None}


def _get_or_load_model_artifacts():
    if _MODEL_CACHE["model"] is None:
        model_path = os.path.join(
            settings.BASE_DIR, "Kultiva", "ml_models", "kultiva_agri_brain.joblib"
        )
        _MODEL_CACHE["model"] = joblib.load(model_path)
        logger.info("Loaded Kultiva crop model into memory")
    return _MODEL_CACHE["model"]


def predict_best_crop(weather_data: dict, soil_data: dict) -> dict:
    try:
        if not weather_data or not soil_data:
            raise ValueError("Missing critical meteorological or soil data")

        raw_n = float(soil_data.get("N", 0))
        raw_p = float(soil_data.get("P", 0))
        raw_k = float(soil_data.get("K", 0))
        n_val = np.clip((raw_n / 300.0) * 140.0, 0.0, 140.0)
        p_val = np.clip((raw_p / 100.0) * 145.0, 5.0, 145.0)
        k_val = np.clip((raw_k / 400.0) * 205.0, 5.0, 205.0)
        temp_val = np.clip(float(weather_data.get("Temperature_C", 25.0)), -20.0, 60.0)
        hum_val = np.clip(float(weather_data.get("Humidity_Pct", 50.0)), 0.0, 100.0)
        ph_val = np.clip(float(soil_data.get("pH", 7.0)), 0.0, 14.0)
        rain_val = np.clip(float(weather_data.get("Rainfall_mm", 0.0)), 0.0, 1000.0)

        columns = [
            "Nitrogen", "Phosphorus", "Potassium", "Temperature",
            "Humidity", "pH_Value", "Rainfall",
        ]
        features = pd.DataFrame(
            [[n_val, p_val, k_val, temp_val, hum_val, ph_val, rain_val]],
            columns=columns,
            dtype=np.float32,
        )
        model = _get_or_load_model_artifacts()
        probabilities = model.predict_proba(features)[0]
        top_indices = np.argsort(probabilities)[::-1][:3]
        ranked = []
        for idx in top_indices:
            confidence = float(np.clip(round(probabilities[idx] * 100, 1), 0.0, 100.0))
            if confidence >= 1.5:
                ranked.append({"name": str(model.classes_[idx]).capitalize(), "confidence": confidence})
        if not ranked:
            raise ValueError("Model predicted no realistic outcome")

        best_crop = ranked[0]["name"]
        return {
            "success": True,
            "crop": best_crop,
            "predictions": ranked,
            "advisory": get_crop_advisory(best_crop) or {},
            "status": "Lightweight AI Ranked Prediction Completed Successfully",
        }
    except Exception as exc:
        logger.error("Crop prediction failure: %s", exc, exc_info=True)
        return {
            "success": False,
            "crop": "Analysis Pending",
            "predictions": [],
            "advisory": {},
            "status": "System currently undergoing maintenance or missing data.",
        }


__all__ = ["predict_best_crop"]
