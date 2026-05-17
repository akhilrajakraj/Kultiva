import os
import django
import random
import numpy as np

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kultiva.settings')
django.setup()

from Kultiva.models import GridSoilData

# --- CONFIGURATION ---
GRID_STEP = 0.05  # Approx 5.5km grid.

INDIAN_REGIONS = {
    "KERALA_TN (South - Acidic/Red Soil)": {
        "lat_range": (8.0, 13.5), "lon_range": (74.5, 80.3),
        "base": {'n': 240, 'p': 12, 'k': 110, 'ph': 5.2, 'ec': 0.1, 'oc': 0.45, 's': 10, 'fe': 15.0} 
    },
    "PUNJAB_HARYANA (North - Alluvial/Intensive)": {
        "lat_range": (28.4, 32.5), "lon_range": (73.8, 77.0),
        "base": {'n': 200, 'p': 35, 'k': 250, 'ph': 7.5, 'ec': 0.8, 'oc': 0.35, 's': 18, 'fe': 6.0} 
    },
    "MAHARASHTRA_MP (Central - Black Cotton Soil)": {
        "lat_range": (18.0, 24.0), "lon_range": (72.6, 80.0),
        "base": {'n': 260, 'p': 15, 'k': 350, 'ph': 8.0, 'ec': 0.4, 'oc': 0.5, 's': 20, 'fe': 4.5} 
    },
    "RAJASTHAN_GUJARAT (West - Arid/Sandy)": {
        "lat_range": (23.0, 29.0), "lon_range": (69.0, 75.0),
        "base": {'n': 120, 'p': 20, 'k': 300, 'ph': 8.8, 'ec': 1.2, 'oc': 0.2, 's': 25, 'fe': 3.5} 
    },
    "WB_ASSAM (East - Deltaic/Alluvial)": {
        "lat_range": (21.5, 27.0), "lon_range": (86.0, 93.0),
        "base": {'n': 320, 'p': 28, 'k': 140, 'ph': 6.2, 'ec': 0.3, 'oc': 0.7, 's': 14, 'fe': 9.0} 
    }
}

CRITICAL_LIMITS = {'N': 280, 'P': 10, 'K': 108, 'OC': 0.5, 'Ph_Low': 6.0, 'Ph_High': 8.5}

def get_smart_recommendation(params):
    advisory = []
    if params['ph'] < 5.5: advisory.append("Acidic Soil: Apply Lime/Dolomite.")
    elif params['ph'] > 8.5: advisory.append("Alkaline Soil: Apply Gypsum.")
    if params['oc'] < 0.5: advisory.append("Low Organic Carbon: Apply FYM/Compost.")
    if params['n'] < CRITICAL_LIMITS['N']: advisory.append("Low Nitrogen: Increase Urea 25%.")
    if params['p'] < CRITICAL_LIMITS['P']: advisory.append("Low Phosphorus: Apply DAP.")
    if params['k'] < CRITICAL_LIMITS['K']: advisory.append("Low Potash: Apply MOP.")
    if params['fe'] < 4.5: advisory.append("Iron Deficiency: Foliar spray FeSO4.")
    if params['zn'] < 0.6: advisory.append("Zinc Deficiency: Apply ZnSO4.")
    return " | ".join(advisory) if advisory else "Soil Health is Good. Maintain standard NPK dosage."

def generate_india_grid():
    print("Clearing old grid data...")
    GridSoilData.objects.all().delete()
    print(f"Generating Pan-India Soil Grid (Resolution: {GRID_STEP} deg)...")

    batch_data = []
    total_count = 0

    for region_name, data in INDIAN_REGIONS.items():
        print(f"Processing Region: {region_name}...")
        lats = np.arange(data['lat_range'][0], data['lat_range'][1], GRID_STEP)
        lons = np.arange(data['lon_range'][0], data['lon_range'][1], GRID_STEP)
        base = data['base']

        for lat in lats:
            for lon in lons:
                ph = round(base['ph'] + random.gauss(0, 0.4), 2)
                fe_adj = base['fe'] - (2.0 if ph > 7.5 else 0)
                
                row = {
                    'ph': ph,
                    'ec': round(base['ec'] + abs(random.gauss(0, 0.1)), 2),
                    'oc': round(base['oc'] + random.gauss(0, 0.1), 2),
                    'n': round(max(10, base['n'] + random.gauss(0, 30)), 1),
                    'p': round(max(5, base['p'] + random.gauss(0, 8)), 1),
                    'k': round(max(20, base['k'] + random.gauss(0, 40)), 1),
                    's': round(max(2, base['s'] + random.gauss(0, 5)), 1),
                    'zn': round(max(0.1, 0.8 + random.gauss(0, 0.2)), 2),
                    'fe': round(max(0.5, fe_adj + random.gauss(0, 3)), 2),
                    'cu': round(max(0.1, 1.0 + random.uniform(-0.5, 0.5)), 2),
                    'mn': round(max(1.0, 5.0 + random.uniform(-2, 2)), 2),
                    'b':  round(max(0.1, 0.5 + random.uniform(-0.2, 0.2)), 2),
                }

                batch_data.append(GridSoilData(
                    grid_lat=round(lat, 3),
                    grid_lon=round(lon, 3), 
                    ph=row['ph'], ec=row['ec'], oc=row['oc'],
                    avg_n=row['n'], avg_p=row['p'], avg_k=row['k'], avg_s=row['s'],
                    avg_zn=row['zn'], avg_fe=row['fe'], avg_cu=row['cu'],
                    avg_mn=row['mn'], avg_b=row['b'],
                    recommendation_text=get_smart_recommendation(row)
                ))
                
                total_count += 1
                if len(batch_data) >= 2000:
                    GridSoilData.objects.bulk_create(batch_data, ignore_conflicts=True)
                    batch_data = []

    if batch_data:
        GridSoilData.objects.bulk_create(batch_data)

    print(f"DONE! Generated {total_count} localized soil grid points covering major Indian regions.")

if __name__ == '__main__':
    generate_india_grid()