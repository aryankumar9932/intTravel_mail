"""
FastAPI backend for the IntTravel "travel-guard" trip planner.

This replaces trip_planner_app.py (the original http.server-based backend)
with a FastAPI app. Same routes, same JSON shapes, same business logic —
so the existing frontend (frontend/index.html + app.js) keeps working
without any changes.

What you get by moving to FastAPI:
  - Auto-generated interactive docs at /docs and /redoc (great for
    integrating this API into another project — anyone can see every
    endpoint, its request body, and try it live).
  - Request validation via Pydantic models (bad payloads get a clear
    422 error instead of a raw exception).
  - CORS enabled, so another app running on a different origin/port
    can call this API directly from the browser.
  - Runs on a proper ASGI server (uvicorn) with async-ready routing.

Where this file goes:
  Put this file directly inside the `travel-guard/` folder, next to
  ml_recommender.py, so the import `from ml_recommender import TripRecommender`
  resolves correctly. Do not move ml_recommender.py, phase2_data/, or
  frontend/ — this file expects them exactly where they already are.
"""

import json
import os
import random
import urllib.request
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml_recommender import TripRecommender

# --------------------------------------------------------------------------
# Paths & startup data (identical to the original trip_planner_app.py)
# --------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
DATA_DIR = os.path.join(ROOT, "phase2_data")


def load_data(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as source:
        return json.load(source)


SAFETY = load_data("safety_alerts.json")
HOTELS = load_data("hotels.json")
GUIDES = load_data("guides.json")
RECOMMENDER = TripRecommender(ROOT)
bookings: List[dict] = []

# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------

app = FastAPI(
    title="Travel Guard API",
    description=(
        "AI/ML-assisted trip planning with safety-aware rerouting, "
        "hotel/guide lookups, and POI recommendations."
    ),
    version="1.0.0",
)

# Lets another project (a different domain/port, e.g. a separate React app
# or another backend) call this API straight from the browser or server.
# Tighten allow_origins to your real frontend's URL(s) before going to
# production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Request/response models
# --------------------------------------------------------------------------

class PlanRequest(BaseModel):
    destination: str
    days: int = 3
    travelerType: str = "solo"


class DisruptionRequest(BaseModel):
    destination: str
    location: str
    days: int
    travelerType: str = "solo"
    score: int = 25
    message: str = "Simulated live safety disruption."


class BookGuideRequest(BaseModel):
    guide_id: str
    day: int
    destination: Optional[str] = None


# --------------------------------------------------------------------------
# Business logic (unchanged from trip_planner_app.py)
# --------------------------------------------------------------------------

def gemini_draft(destination, days, traveler_type):
    prompt = (
        "Create a concise JSON itinerary for a trip to {} for {} days. "
        "Traveler type: {}. Return an array of days with title, stops, and "
        "description. Use well-known attractions and no markdown.".format(
            destination, days, traveler_type
        )
    )
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent?key={}".format(api_key),
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text), "Gemini 2.0 Flash"
        except (OSError, KeyError, IndexError, ValueError):
            pass

    attractions = {
        "jaipur": ["Amber Fort", "Hawa Mahal", "City Palace", "Jantar Mantar"],
        "goa": ["Baga Beach", "Fontainhas", "Dudhsagar Falls", "Panaji Market"],
        "delhi": ["India Gate", "Red Fort", "Humayun's Tomb", "Lodhi Garden"],
    }
    stops = attractions.get(destination.lower(), ["Old Town", "City Museum", "Local Market"])
    draft = []
    for index in range(days):
        day_stops = [stops[index % len(stops)], stops[(index + 1) % len(stops)]]
        draft.append(
            {
                "day": index + 1,
                "title": "Day {} in {}".format(index + 1, destination.title()),
                "stops": day_stops,
                "description": "A balanced {} day with local experiences and flexible time.".format(
                    traveler_type
                ),
            }
        )
    return draft, "Local itinerary generator"


def safety_for(stop, destination, extra_alerts):
    all_alerts = SAFETY + extra_alerts
    for alert in all_alerts:
        if alert["destination"].lower() == destination.lower() and (
            alert["location"].lower() == stop.lower()
            or alert["location"].lower() in stop.lower()
            or stop.lower() in alert["location"].lower()
        ):
            return dict(alert)
    return {
        "destination": destination,
        "location": stop,
        "score": 92,
        "level": "Good",
        "message": "No active safety alerts for this stop.",
    }


def build_plan(destination, days, traveler_type, extra_alerts=None):
    extra_alerts = extra_alerts or []
    draft, source = gemini_draft(destination, days, traveler_type)
    plan_days = []
    raw_route = []
    for item in draft:
        reviewed_stops = []
        for stop in item["stops"]:
            raw_route.append({"day": item["day"], "location": stop})
            safety = safety_for(stop, destination, extra_alerts)
            reviewed_stops.append(
                {
                    "name": stop,
                    "original_name": stop,
                    "safety": safety,
                    "flagged": safety["score"] < 60,
                    "rerouted": False,
                }
            )
        plan_days.append(dict(item, stops=reviewed_stops))

    for item in plan_days:
        for stop in item["stops"]:
            if stop["flagged"]:
                replacement = next(
                    (
                        candidate
                        for candidate in ["City Palace", "City Museum", "Local Market"]
                        if safety_for(candidate, destination, extra_alerts)["score"] >= 60
                    ),
                    "Hotel and indoor cultural activities",
                )
                stop["name"] = replacement
                stop["safety"] = safety_for(replacement, destination, extra_alerts)
                stop["flagged"] = False
                stop["rerouted"] = True

    matching_hotels = [
        hotel for hotel in HOTELS if hotel["destination"].lower() == destination.lower()
    ]
    hotels_by_place = {}
    for item in plan_days:
        for stop in item["stops"]:
            hotels_by_place[stop["name"]] = [
                hotel for hotel in matching_hotels
                if hotel.get("place", "").lower() == stop["name"].lower()
            ][:2]
    matching_guides = [
        guide for guide in GUIDES if guide["destination"].lower() == destination.lower()
    ]
    expected_route = [
        {"day": item["day"], "locations": [stop["name"] for stop in item["stops"]]}
        for item in plan_days
    ]
    return {
        "destination": destination,
        "days": plan_days,
        "hotels": matching_hotels,
        "hotels_by_place": hotels_by_place,
        "guides": matching_guides,
        "source": source,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_itinerary": draft,
        "raw_route": raw_route,
        "expected_route": expected_route,
        "filtering": {
            "safety_alerts_checked": True,
            "low_safety_stops_rerouted": True,
            "verified_guides_only": True,
        },
        "ml_recommendations": RECOMMENDER.recommend(destination=destination, limit=12),
        "ml_model": RECOMMENDER.metadata(),
    }


# --------------------------------------------------------------------------
# Routes — same paths/behavior as the original http.server app
# --------------------------------------------------------------------------

@app.get("/api/datasets", tags=["data"])
def get_datasets():
    return {"safety": SAFETY, "hotels": HOTELS, "guides": GUIDES}


@app.get("/api/ml-status", tags=["data"])
def get_ml_status():
    return RECOMMENDER.metadata()


@app.get("/api/data-overview", tags=["data"])
def get_data_overview():
    return RECOMMENDER.dataset_overview()


@app.post("/api/plan", tags=["planning"])
def create_plan(payload: PlanRequest):
    destination = payload.destination.strip()
    if not destination:
        raise HTTPException(status_code=400, detail="Destination is required.")
    days = max(1, min(14, payload.days))
    return build_plan(destination, days, payload.travelerType)


@app.post("/api/disruptions", tags=["planning"])
def create_disruption(payload: DisruptionRequest):
    alert = {
        "destination": payload.destination,
        "location": payload.location,
        "score": payload.score,
        "level": "Critical",
        "message": payload.message,
    }
    SAFETY.append(alert)
    plan = build_plan(payload.destination, payload.days, payload.travelerType, [alert])
    return {"alert": alert, "plan": plan}


@app.post("/api/book-guide", tags=["planning"])
def book_guide(payload: BookGuideRequest):
    if not payload.guide_id or not payload.day:
        raise HTTPException(status_code=400, detail="Guide and itinerary day are required.")
    booking = payload.dict()
    booking["booking_id"] = "BOOK-{}".format(random.randint(1000, 9999))
    bookings.append(booking)
    return {"booking": booking}


# --------------------------------------------------------------------------
# Static frontend — served exactly like the original app
# (index.html requests /static/styles.css and /static/app.js)
# --------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/", tags=["frontend"])
def serve_index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


# --------------------------------------------------------------------------
# Local run: `python main.py` (mirrors the old PORT/HOST env vars)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    # Default to 127.0.0.1 so the terminal prints a URL you can click straight
    # into the browser. When deploying (Render, Docker, etc.), set the HOST
    # env var to "0.0.0.0" so the server accepts connections from outside.
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("main:app", host=host, port=port, reload=False)