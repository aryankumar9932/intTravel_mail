"""FastAPI entry point for integrating Travel Guard with web applications.

Run locally with:
    uvicorn fastapi_app:app --reload
"""

import os
from typing import Any, Dict, Union

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from trip_planner_app import (
    BOOKINGS,
    GUIDES,
    HOTELS,
    RECOMMENDER,
    SAFETY,
    build_plan,
)


ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
configured_origins = os.environ.get("CORS_ORIGINS")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (
        ",".join(
            filter(
                None,
                [
                    configured_origins or "",
                    "https://tourist-safety-app-one.vercel.app",
                    "http://localhost:5173",
                ],
            )
        )
    ).split(",")
    if origin.strip()
]

app = FastAPI(
    title="Travel Guard API",
    description="Safety-aware itinerary planning and IntTravel recommendations.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class PlanRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=120)
    days: int = Field(default=3, ge=1, le=14)
    traveler_type: str = Field(default="solo", alias="travelerType", max_length=40)

    model_config = {"populate_by_name": True}

    @field_validator("destination", "traveler_type")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value


class DisruptionRequest(PlanRequest):
    location: str = Field(..., min_length=1, max_length=160)
    score: int = Field(default=25, ge=0, le=100)
    message: str = Field(default="Simulated live safety disruption.", max_length=500)

    @field_validator("location", "message")
    @classmethod
    def strip_disruption_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value


class GuideBookingRequest(BaseModel):
    guide_id: Union[str, int]
    day: Union[str, int]
    destination: str = Field(..., min_length=1, max_length=120)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Destination is required.")
        return value


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/health", tags=["system"])
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "travel-guard"}


@app.get("/api", tags=["system"])
def api_info() -> Dict[str, Any]:
    return {
        "service": "Travel Guard API",
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "health": "/health",
    }


@app.get("/api/datasets", tags=["datasets"])
def datasets() -> Dict[str, Any]:
    return {"safety": SAFETY, "hotels": HOTELS, "guides": GUIDES}


@app.get("/api/ml-status", tags=["recommendations"])
def ml_status() -> Dict[str, Any]:
    return RECOMMENDER.metadata()


@app.get("/api/data-overview", tags=["datasets"])
def data_overview() -> Dict[str, Any]:
    return RECOMMENDER.dataset_overview()


@app.get("/api/recommendations", tags=["recommendations"])
def recommendations(
    destination: str = Query(default="", max_length=120),
    user_id: str = Query(default="", max_length=120),
    limit: int = Query(default=12, ge=1, le=100),
) -> Dict[str, Any]:
    return {
        "destination": destination.strip(),
        "user_id": user_id.strip(),
        "recommendations": RECOMMENDER.recommend(
            user_id=user_id.strip(), destination=destination.strip(), limit=limit
        ),
    }


@app.post("/api/plan", tags=["planning"])
def plan(request: PlanRequest) -> Dict[str, Any]:
    return build_plan(
        request.destination, request.days, request.traveler_type
    )


@app.post("/api/disruptions", tags=["planning"])
def disruption(request: DisruptionRequest) -> Dict[str, Any]:
    alert = {
        "destination": request.destination,
        "location": request.location,
        "score": request.score,
        "level": "Critical",
        "message": request.message,
    }
    SAFETY.append(alert)
    return {
        "alert": alert,
        "plan": build_plan(
            request.destination,
            request.days,
            request.traveler_type,
            [alert],
        ),
    }


@app.post("/api/book-guide", tags=["bookings"])
def book_guide(request: GuideBookingRequest) -> Dict[str, Any]:
    booking = request.model_dump()
    booking["booking_id"] = "BOOK-{}".format(len(BOOKINGS) + 1000)
    BOOKINGS.append(booking)
    return {"booking": booking}
