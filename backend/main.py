from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import tourist_id, geofence, anomaly, sos, dashboard, auth as auth_router, zones as zones_router, reports

app = FastAPI(
    title="Tourist Safety System",
    description="Digital ID issuance, geo-fencing, anomaly checks, SOS dispatch, and the police dashboard API for SIH25002.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tourist_id.router)
app.include_router(geofence.router)
app.include_router(anomaly.router)
app.include_router(sos.router)
app.include_router(dashboard.router)
app.include_router(auth_router.router)
app.include_router(zones_router.router)
app.include_router(reports.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serves the existing frontend pages directly from FastAPI so the whole
# thing runs with one command during a demo.
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
