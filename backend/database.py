"""
SQLite database setup for the Tourist Safety System.

Using raw sqlite3 instead of an ORM on purpose - the schema is small
enough that SQLAlchemy would just be extra boilerplate, and it's easier
to show exactly what's happening when someone reads this for the first time.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "tourist_safety.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tourists (
    id TEXT PRIMARY KEY,              -- UUID, also embedded in the signed JWT
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    nationality TEXT,
    itinerary TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    trip_start TEXT NOT NULL,         -- ISO datetime
    trip_end TEXT NOT NULL,           -- ISO datetime, ID is invalid after this
    created_at TEXT NOT NULL,
    onchain_tx_hash TEXT,             -- set if CHAIN_* env vars were configured at registration time, NULL otherwise
    data_hash TEXT NOT NULL           -- keccak256 of the tourist record, mirrors what's (optionally) stored on-chain
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tourist_id TEXT NOT NULL REFERENCES tourists(id),
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tourist_id TEXT NOT NULL REFERENCES tourists(id),
    alert_type TEXT NOT NULL,         -- 'geofence' | 'inactivity' | 'deviation' | 'ml_pattern' | 'sos'
    reason TEXT NOT NULL,             -- human-readable explanation, no black-box scores
    lat REAL,
    lng REAL,
    created_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_locations_tourist ON locations(tourist_id);
CREATE INDEX IF NOT EXISTS idx_alerts_tourist ON alerts(tourist_id);

CREATE TABLE IF NOT EXISTS risk_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    radius_m REAL NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',   -- 'high' | 'medium'
    sms_guidance TEXT NOT NULL,                  -- pushed to the tourist's phone on entry
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS officers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tourist_id TEXT REFERENCES tourists(id),
    reporter_name TEXT,
    reporter_phone TEXT,
    category TEXT NOT NULL,           -- 'theft' | 'harassment' | 'medical' | 'scam' | 'other'
    description TEXT NOT NULL,
    lat REAL,
    lng REAL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'   -- 'open' | 'reviewing' | 'closed'
);
"""


def _seed_default_zones(conn) -> None:
    """Migrates the zones that used to be hardcoded in zones.py into the
    DB, so there's one source of truth instead of the same three spots
    duplicated in Python and in map.html."""
    existing = conn.execute("SELECT COUNT(*) as c FROM risk_zones").fetchone()["c"]
    if existing > 0:
        return

    from datetime import datetime
    now = datetime.utcnow().isoformat()
    default_zones = [
        ("Charminar Old City", 17.3616, 78.4747, 400, "high",
         "SAFETY ALERT: You've entered a high-density restricted-monitoring zone near Charminar. "
         "Stay with your group, keep valuables out of sight, and avoid isolated lanes after dark."),
        ("Golconda Fort Outskirts", 17.3753, 78.4019, 500, "high",
         "SAFETY ALERT: You're near Golconda Fort's outer zone - uneven terrain and limited lighting "
         "past sunset. Stick to marked paths and avoid the area after 6 PM."),
        ("Hitech City Late-Night Zone", 17.4435, 78.3772, 600, "medium",
         "SAFETY NOTICE: You've entered a zone flagged for reduced foot traffic late at night. "
         "Prefer well-lit main roads and registered cabs after 10 PM."),
    ]
    conn.executemany(
        """INSERT INTO risk_zones (name, lat, lng, radius_m, risk_level, sms_guidance, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(*z, now) for z in default_zones],
    )


def _seed_default_officer(conn) -> None:
    """Demo login so the dashboard is reachable out of the box. This is
    clearly a placeholder account - swap or remove it before this goes
    anywhere beyond a local demo."""
    existing = conn.execute("SELECT COUNT(*) as c FROM officers").fetchone()["c"]
    if existing > 0:
        return

    from datetime import datetime
    from auth import hash_password

    default_password = "ChangeMe123!"
    conn.execute(
        """INSERT INTO officers (badge_id, name, password_hash, created_at)
           VALUES (?, ?, ?, ?)""",
        ("ADMIN001", "Demo Officer", hash_password(default_password), datetime.utcnow().isoformat()),
    )
    print(
        f"[seed] Created demo officer login - badge_id=ADMIN001 password={default_password} "
        f"(change this before any real deployment)"
    )


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _seed_default_zones(conn)
        _seed_default_officer(conn)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
