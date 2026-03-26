import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "plumber")
SEARCH_LOCATION = os.getenv("SEARCH_LOCATION", "Austin, Texas")
SEARCH_RADIUS_METERS = int(os.getenv("SEARCH_RADIUS_METERS", 10000))
MAX_LEADS = int(os.getenv("MAX_LEADS", 20))

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def geocode_location(location: str) -> tuple[float, float]:
    """Convert a city/address string to lat/lng coordinates."""
    params = {"address": location, "key": GOOGLE_MAPS_API_KEY}
    resp = requests.get(GEOCODE_URL, params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        raise ValueError(f"Could not geocode location: {location}")
    coords = results[0]["geometry"]["location"]
    return coords["lat"], coords["lng"]


def fetch_places(lat: float, lng: float) -> list[dict]:
    """Fetch nearby businesses matching the search query."""
    params = {
        "location": f"{lat},{lng}",
        "radius": SEARCH_RADIUS_METERS,
        "keyword": SEARCH_QUERY,
        "key": GOOGLE_MAPS_API_KEY,
    }
    businesses = []
    next_page_token = None

    while len(businesses) < MAX_LEADS:
        if next_page_token:
            params["pagetoken"] = next_page_token
        resp = requests.get(PLACES_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        businesses.extend(data.get("results", []))
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    return businesses[:MAX_LEADS]


def get_place_details(place_id: str) -> dict:
    """Get detailed info (website, phone) for a single place."""
    params = {
        "place_id": place_id,
        "fields": "name,website,formatted_phone_number,formatted_address",
        "key": GOOGLE_MAPS_API_KEY,
    }
    resp = requests.get(DETAILS_URL, params=params)
    resp.raise_for_status()
    return resp.json().get("result", {})


def get_leads() -> list[dict]:
    """
    Main function — returns a list of lead dicts:
    {name, address, phone, website}
    """
    print(f"[Maps] Geocoding '{SEARCH_LOCATION}'...")
    lat, lng = geocode_location(SEARCH_LOCATION)

    print(f"[Maps] Searching for '{SEARCH_QUERY}' near {lat:.4f},{lng:.4f}...")
    places = fetch_places(lat, lng)
    print(f"[Maps] Found {len(places)} businesses. Fetching details...")

    leads = []
    for place in places:
        details = get_place_details(place["place_id"])
        leads.append({
            "name": details.get("name", place.get("name", "")),
            "address": details.get("formatted_address", ""),
            "phone": details.get("formatted_phone_number", ""),
            "website": details.get("website", ""),
        })

    print(f"[Maps] Done. {len(leads)} leads collected.")
    return leads
