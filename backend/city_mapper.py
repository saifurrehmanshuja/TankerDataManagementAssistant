"""
City Mapping Utility
Maps latitude/longitude coordinates to Pakistani city names
"""
import math

# Pakistani cities with their coordinates
PAKISTANI_CITIES = {
    # Major cities
    "Karachi": (24.8607, 67.0011),
    "Lahore": (31.5204, 74.3587),
    "Islamabad": (33.6844, 73.0479),
    "Rawalpindi": (33.5651, 73.0169),
    "Faisalabad": (31.4504, 73.1350),
    "Multan": (30.1575, 71.5249),
    "Hyderabad": (25.3960, 68.3578),
    "Peshawar": (34.0151, 71.5249),
    "Quetta": (30.1798, 66.9750),
    "Sukkur": (27.7022, 68.8581),
    "Sialkot": (32.4945, 74.5229),
    "Gujranwala": (32.1617, 74.1883),
    "Bahawalpur": (29.4000, 71.6833),
    "Sargodha": (32.0836, 72.6711),
    "Gujrat": (32.5739, 74.0776),
    "Kasur": (31.1167, 74.4500),
    "Sheikhupura": (31.7167, 73.9833),
    "Jhang": (31.2833, 72.3333),
    "Rahim Yar Khan": (28.4200, 70.3000),
    "Larkana": (27.5590, 68.2120),
    "Mardan": (34.1983, 72.0400),
    "Mingora": (34.7797, 72.3600),
    "Nawabshah": (26.2442, 68.4100),
    "Chiniot": (31.7167, 72.9833),
    "Kotri": (25.3667, 68.3167),
    "Khanpur": (28.6500, 70.6500),
    "Hafizabad": (32.0667, 73.6833),
    "Kohat": (33.5833, 71.4333),
    "Jacobabad": (28.2833, 68.4333),
    "Shikarpur": (27.9500, 68.6333),
    "Muzaffargarh": (30.0667, 71.1833),
    "Khanewal": (30.3000, 71.9333),
    "Hasan Abdal": (33.8167, 72.6833),
    "Kamoke": (31.9667, 74.2167),
    "Sahiwal": (30.6667, 73.1000),
    "Sadiqabad": (28.3000, 70.1333),
    "Burewala": (30.1667, 72.6500),
    "Jhelum": (32.9333, 73.7333),
    "Chakwal": (32.9333, 72.8500),
    "Khuzdar": (27.8000, 66.6167),
    "Gwadar": (25.1264, 62.3225),
    "Turbat": (26.0028, 63.0500),
    "Zhob": (31.3500, 69.4500),
    "Gilgit": (35.9200, 74.3000),
    "Skardu": (35.2972, 75.6333),
}

def get_city_from_coords(lat, lon, threshold_km=50):
    """
    Get city name from latitude/longitude coordinates.
    
    Args:
        lat: Latitude
        lon: Longitude
        threshold_km: Maximum distance in km to match a city (default: 50km)
    
    Returns:
        City name string or "Unknown Location" if no match found
    """
    if lat is None or lon is None:
        return "Unknown Location"
    
    min_distance = float('inf')
    closest_city = "Unknown Location"
    
    for city_name, (city_lat, city_lon) in PAKISTANI_CITIES.items():
        # Calculate distance using Haversine formula
        distance = haversine_distance(lat, lon, city_lat, city_lon)
        
        if distance < min_distance:
            min_distance = distance
            closest_city = city_name
    
    # Only return city if within threshold
    if min_distance <= threshold_km:
        return closest_city
    else:
        return "Unknown Location"

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth.
    Returns distance in kilometers.
    """
    # Radius of Earth in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

def get_all_cities():
    """Get list of all Pakistani cities"""
    return list(PAKISTANI_CITIES.keys())

