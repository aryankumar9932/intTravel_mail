import json
import os
import random
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ml_recommender import TripRecommender


ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
DATA_DIR = os.path.join(ROOT, "phase2_data")
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
BOOKINGS = []
# Kept as an alias for clients that import the legacy module directly.
bookings = BOOKINGS


def load_data(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as source:
        return json.load(source)


SAFETY = load_data("safety_alerts.json")
HOTELS = load_data("hotels.json")
GUIDES = load_data("guides.json")
RECOMMENDER = TripRecommender(ROOT)


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
        "ml_recommendations": RECOMMENDER.recommend(
            destination=destination, limit=12
        ),
        "ml_model": RECOMMENDER.metadata(),
    }


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/datasets":
            self.send_json({"safety": SAFETY, "hotels": HOTELS, "guides": GUIDES})
            return
        if self.path == "/api/ml-status":
            self.send_json(RECOMMENDER.metadata())
            return
        if self.path == "/api/data-overview":
            self.send_json(RECOMMENDER.dataset_overview())
            return
        if self.path in ("/", "/index.html"):
            with open(os.path.join(FRONTEND, "index.html"), "rb") as page:
                body = page.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/static/"):
            filename = os.path.basename(self.path)
            path = os.path.join(FRONTEND, filename)
            if os.path.exists(path):
                with open(path, "rb") as asset:
                    body = asset.read()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "text/css" if filename.endswith(".css") else "application/javascript")
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path == "/api/plan":
            destination = str(data.get("destination", "")).strip()
            days = max(1, min(14, int(data.get("days", 3))))
            traveler_type = str(data.get("travelerType", "solo"))
            if not destination:
                self.send_json({"error": "Destination is required."}, 400)
                return
            self.send_json(build_plan(destination, days, traveler_type))
            return
        if self.path == "/api/disruptions":
            alert = {
                "destination": data["destination"],
                "location": data["location"],
                "score": int(data.get("score", 25)),
                "level": "Critical",
                "message": data.get("message", "Simulated live safety disruption."),
            }
            SAFETY.append(alert)
            self.send_json({"alert": alert, "plan": build_plan(
                data["destination"], int(data["days"]), data.get("travelerType", "solo"), [alert]
            )})
            return
        if self.path == "/api/book-guide":
            if not data.get("guide_id") or not data.get("day"):
                self.send_json({"error": "Guide and itinerary day are required."}, 400)
                return
            booking = dict(data, booking_id="BOOK-{}".format(random.randint(1000, 9999)))
            bookings.append(booking)
            self.send_json({"booking": booking})
            return
        self.send_error(404)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print("AI/ML Trip Planner: http://{}:{}/".format(HOST, PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTrip Planner stopped.")
    finally:
        server.server_close()
