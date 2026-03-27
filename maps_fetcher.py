import os
import time
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse

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


def _extract_domain(website: str) -> str:
    """Return bare domain from URL."""
    if not website:
        return ""
    parsed = urlparse(website if website.startswith("http") else f"https://{website}")
    return parsed.netloc.replace("www.", "").lower().strip()


def fetch_places_page(lat: float, lng: float, page_token: str = None) -> tuple[list, str | None]:
    """
    Fetch a single page of nearby businesses.
    Returns (results_list, next_page_token_or_None).
    """
    params = {
        "location": f"{lat},{lng}",
        "radius": SEARCH_RADIUS_METERS,
        "keyword": SEARCH_QUERY,
        "key": GOOGLE_MAPS_API_KEY,
    }
    if page_token:
        params["pagetoken"] = page_token
        time.sleep(2)   # Google requires a short delay before using a page token

    resp = requests.get(PLACES_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", []), data.get("next_page_token")


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
    Basic lead fetch — returns up to MAX_LEADS businesses.
    Does NOT filter against the tracker DB (use get_fresh_leads for that).
    """
    print(f"[Maps] Geocoding '{SEARCH_LOCATION}'...")
    lat, lng = geocode_location(SEARCH_LOCATION)

    print(f"[Maps] Searching for '{SEARCH_QUERY}' near {lat:.4f},{lng:.4f}...")

    places = []
    next_token = None
    while len(places) < MAX_LEADS:
        page, next_token = fetch_places_page(lat, lng, next_token)
        places.extend(page)
        if not next_token:
            break

    places = places[:MAX_LEADS]
    print(f"[Maps] Found {len(places)} businesses. Fetching details...")

    leads = []
    for place in places:
        details = get_place_details(place["place_id"])
        leads.append({
            "name":    details.get("name", place.get("name", "")),
            "address": details.get("formatted_address", ""),
            "phone":   details.get("formatted_phone_number", ""),
            "website": details.get("website", ""),
        })

    print(f"[Maps] Done. {len(leads)} leads collected.")
    return leads


def get_fresh_leads(known_domains: set = None) -> list[dict]:
    """
    Fetch leads, skipping any whose domain is already in known_domains.
    Keeps fetching more Google Maps pages until MAX_LEADS fresh leads are found
    or there are no more results.

    known_domains: set of domain strings from lead_tracker.get_known_domains()
    """
    if known_domains is None:
        known_domains = set()

    print(f"[Maps] Geocoding '{SEARCH_LOCATION}'...")
    lat, lng = geocode_location(SEARCH_LOCATION)
    print(f"[Maps] Searching for '{SEARCH_QUERY}' near {lat:.4f},{lng:.4f}...")
    print(f"[Maps] Skipping {len(known_domains)} already-known domains...")

    fresh_leads = []
    skipped = 0
    next_token = None
    page_num = 0

    while len(fresh_leads) < MAX_LEADS:
        page_num += 1
        page, next_token = fetch_places_page(lat, lng, next_token)

        if not page:
            break

        for place in page:
            if len(fresh_leads) >= MAX_LEADS:
                break

            details = get_place_details(place["place_id"])
            website = details.get("website", "")
            domain = _extract_domain(website)

            if domain and domain in known_domains:
                print(f"[Maps] ⏭️  Skipping known lead: {details.get('name', '')} ({domain})")
                skipped += 1
                continue

            fresh_leads.append({
                "name":    details.get("name", place.get("name", "")),
                "address": details.get("formatted_address", ""),
                "phone":   details.get("formatted_phone_number", ""),
                "website": website,
            })

        if not next_token:
            print(f"[Maps] No more pages available after page {page_num}.")
            break

    print(f"[Maps] Done. {len(fresh_leads)} fresh leads found, {skipped} known leads skipped.")
    return fresh_leads
