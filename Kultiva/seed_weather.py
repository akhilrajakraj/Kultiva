import os
import django
import random

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kultiva.settings')
django.setup()

from Kultiva.models import WeatherHistory

def generate_pan_india_weather():
    """
    Generates synthetic fallback weather data for all 28 States and 8 Union Territories of India.
    Includes specific logic for Kerala districts and a dedicated archetype for North-East India.
    """

    # 1. DEFINE INDIA'S CLIMATIC ARCHETYPES (12 months: Jan-Dec)
    climates = {
        "tropical_coastal": { 
            # Region: Kerala, Goa, TN, Coastal Karnataka, WB, Odisha, Islands
            # Profile: Hot, humid, low temperature variance, dual monsoons for some.
            "temp": [28.0, 29.0, 31.0, 32.0, 31.5, 29.0, 28.5, 28.5, 29.0, 29.5, 29.0, 28.5],
            "rain": [15.0, 25.0, 45.0, 105.0, 230.0, 600.0, 550.0, 350.0, 250.0, 280.0, 150.0, 40.0],
            "hum":  [70.0, 72.0, 75.0, 78.0, 82.0, 88.0, 90.0, 89.0, 85.0, 82.0, 78.0, 72.0]
        },
        "arid_desert": { 
            # Region: Rajasthan, Gujarat, parts of Punjab border
            # Profile: Extreme heat, very low rainfall, dry winters.
            "temp": [15.0, 20.0, 28.0, 35.0, 40.0, 41.0, 37.0, 34.0, 34.0, 31.0, 25.0, 18.0],
            "rain": [5.0,  5.0,  5.0,  10.0, 15.0, 40.0, 140.0, 110.0, 40.0, 10.0, 5.0,  5.0],
            "hum":  [35.0, 30.0, 25.0, 20.0, 25.0, 45.0, 65.0, 60.0, 45.0, 35.0, 30.0, 35.0]
        },
        "central_plains": { 
            # Region: Indo-Gangetic Plains, Central Highlands, Deccan Plateau (UP, MP, Telangana)
            # Profile: Continental climate. Cold winters, scorching summers, defined monsoon.
            "temp": [14.0, 18.0, 26.0, 34.0, 39.0, 37.0, 32.0, 30.0, 30.0, 26.0, 21.0, 15.0],
            "rain": [15.0, 15.0, 10.0, 10.0, 25.0, 110.0, 280.0, 260.0, 160.0, 40.0, 10.0, 10.0],
            "hum":  [60.0, 50.0, 35.0, 30.0, 35.0, 60.0, 82.0, 84.0, 75.0, 60.0, 50.0, 60.0]
        },
        "himalayan": { 
            # Region: J&K, Ladakh, HP, Uttarakhand, Sikkim
            # Profile: Cold to freezing winters, mild summers, snow/rain mix.
            "temp": [4.0,  8.0,  14.0, 20.0, 24.0, 26.0, 24.0, 23.0, 21.0, 16.0, 11.0, 6.0],
            "rain": [50.0, 60.0, 60.0, 40.0, 50.0, 140.0, 280.0, 280.0, 140.0, 40.0, 20.0, 30.0],
            "hum":  [65.0, 60.0, 55.0, 50.0, 55.0, 65.0, 85.0, 85.0, 75.0, 60.0, 60.0, 65.0]
        },
        "northeast_humid": { 
            # Region: Seven Sisters (Assam, Meghalaya, etc.)
            # Profile: Sub-tropical highland, high humidity year-round, extremely heavy monsoon.
            "temp": [16.0, 20.0, 24.0, 27.0, 28.0, 30.0, 31.0, 31.0, 30.0, 28.0, 23.0, 18.0],
            "rain": [20.0, 35.0, 70.0, 180.0, 350.0, 650.0, 700.0, 550.0, 350.0, 180.0, 40.0, 20.0],
            "hum":  [70.0, 65.0, 68.0, 75.0, 80.0, 88.0, 92.0, 90.0, 88.0, 82.0, 78.0, 75.0]
        }
    }

    # 2. MAP STATES & UTs TO ARCHETYPES
    # Note: Kerala is handled via the specific district list below.
    india_states = {
        # --- North & Himalayas ---
        "Jammu & Kashmir": "himalayan",
        "Ladakh": "himalayan",
        "Himachal Pradesh": "himalayan",
        "Uttarakhand": "himalayan",
        
        # --- Central & Plains ---
        "Punjab": "central_plains",
        "Haryana": "central_plains",
        "Chandigarh": "central_plains",
        "Delhi": "central_plains",
        "Uttar Pradesh": "central_plains",
        "Bihar": "central_plains",
        "Madhya Pradesh": "central_plains",
        "Chhattisgarh": "central_plains",
        "Jharkhand": "central_plains",
        
        # --- West & Desert ---
        "Rajasthan": "arid_desert",
        "Gujarat": "arid_desert",
        
        # --- South & Deccan Plateau (Non-Kerala) ---
        "Maharashtra": "tropical_coastal",  # Using coastal profile for Konkan dominance fallback
        "Goa": "tropical_coastal",
        "Karnataka": "tropical_coastal",
        "Telangana": "central_plains",      # Interior semi-arid/hot climate fits 'central_plains' temp profile
        "Andhra Pradesh": "tropical_coastal",
        "Tamil Nadu": "tropical_coastal",
        "Puducherry": "tropical_coastal",
        
        # --- East & Islands ---
        "West Bengal": "tropical_coastal",
        "Odisha": "tropical_coastal",
        "Andaman & Nicobar Islands": "tropical_coastal",
        "Lakshadweep": "tropical_coastal",
        "Dadra and Nagar Haveli and Daman and Diu": "tropical_coastal",

        # --- North East (Seven Sisters + Sikkim) ---
        "Sikkim": "himalayan",
        "Assam": "northeast_humid",
        "Arunachal Pradesh": "northeast_humid",
        "Meghalaya": "northeast_humid",
        "Manipur": "northeast_humid",
        "Mizoram": "northeast_humid",
        "Nagaland": "northeast_humid",
        "Tripura": "northeast_humid"
    }

    # 3. KERALA VIP DISTRICT LIST
    kerala_districts = [
        "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", 
        "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad", 
        "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"
    ]

    print("Clearing old weather data...")
    WeatherHistory.objects.all().delete()
    print("Generating Pan-India Climatic Data...")

    # FUNCTION TO GENERATE AND SAVE A YEAR OF DATA
    def save_yearly_data(location_name, climate_type, is_hilly=False):
        base = climates[climate_type]
        for month in range(1, 13):
            # Add stochastic variance
            temp = base["temp"][month-1] + random.uniform(-1.5, 1.5)
            rain = base["rain"][month-1] + random.uniform(-10.0, 20.0)
            hum = base["hum"][month-1] + random.uniform(-4.0, 4.0)

            # Adjust for hilly terrain (Idukki, Wayanad, or Himalayan states)
            if is_hilly:
                temp -= random.uniform(3.5, 6.0) # Cooler
                rain += random.uniform(20.0, 50.0) # Orographic lift rainfall
            
            # Sanity check
            rain = max(0.0, rain)
            hum = min(100.0, max(10.0, hum))

            WeatherHistory.objects.create(
                district=location_name, # Storing State name or Kerala District name
                month=month,
                avg_temp=round(temp, 1),
                avg_humidity=round(hum, 1),
                avg_rainfall=round(rain, 1)
            )

    # 4. EXECUTE FOR KERALA DISTRICTS
    for district in kerala_districts:
        # Idukki and Wayanad are High-Range districts
        is_hilly = district in ["Idukki", "Wayanad"]
        save_yearly_data(district, "tropical_coastal", is_hilly)

    # 5. EXECUTE FOR REST OF INDIA
    for state, climate_type in india_states.items():
        # Check if the archetype implies hilly terrain naturally (for extra randomness)
        is_hilly_archetype = climate_type == "himalayan"
        save_yearly_data(state, climate_type, is_hilly_archetype)

    total_locations = len(kerala_districts) + len(india_states)
    total_rows = total_locations * 12
    print(f"Success! Generated data for {total_locations} locations.")
    print(f"{total_rows} rows of Pan-India weather data injected.")

if __name__ == '__main__':
    generate_pan_india_weather()