# Tourist Safety System — SIH25002

Prototype for Smart India Hackathon problem statement **SIH25002**: Smart Tourist Safety
Monitoring & Incident Response System (AI, Geo-Fencing, Blockchain-based Digital ID).

Team: Neural Nexus.

The first version of this (the actual SIH submission) was a static frontend with every
feature — blockchain ID, AI detection, IoT — faked with `localStorage` and no server behind
it. This is the rebuild: a real FastAPI backend, mapped against the five pain points the
problem statement actually asks for.

## The five pain points, and what's here for each

**1. Tamper-proof verification (blockchain ID)**
Every tourist gets a JWT signed server-side — tamper-evident, expires on its own once the
trip ends. On top of that, if `CHAIN_RPC_URL` / `CHAIN_PRIVATE_KEY` / `CHAIN_CONTRACT_ADDRESS`
are set, registration also mints the identity on `backend/blockchain/contracts/TouristID.sol`,
a deployed Solidity contract. The point of the chain layer isn't the JWT can't do the job
alone — it's cross-border verification: a checkpoint in a different state can call
`isValid()` directly against the same contract and get the same answer, without needing an
API key or a live connection back to whichever state originally issued the ID. Only a hash
of the tourist's record goes on-chain, never the record itself.
Deploy it with `python3 blockchain/deploy.py` (needs `pip install py-solc-x` and a funded
testnet wallet — see the script's docstring). Without it configured, registration still
works fine on the JWT alone.

**2. Proactive danger prevention (geo-fencing)**
Every location ping is checked server-side against a table of risk zones (haversine
distance, not decoration). Entering one logs an alert *and* sends a real SMS via Twilio to
the tourist's own phone with zone-specific safety guidance — SMS specifically because it
still gets through on plain cellular coverage with no data connection, which a push
notification can't promise in the terrain this is meant for. Zones live in the DB now
(`risk_zones` table) instead of being duplicated in Python and JS — `GET /api/zones` is how
the map and anything else reads the current list, and officers can add/remove zones through
the dashboard's API.

**3. AI anomaly detection**
Two layers. Three explainable rules (prolonged inactivity, implausible speed, repeated
zone entries) give a plain-English reason for anything they flag. Alongside that,
`backend/ml/` trains an IsolationForest on the shape of a tourist's recent movement
(average/max speed, time since last ping, how tightly they're clustered around one area,
recent zone entries) and flags patterns that don't fit — catching combinations the fixed
thresholds would each pass individually. It's trained on synthetic data, not real tourist
GPS logs, because none exist yet for a hackathon prototype — see `ml/train_model.py`'s
docstring for what to swap in once real data exists.

**4. Real-time incident command dashboard**
Police login (`/api/auth/login`, badge ID + password) gates the dashboard. Once in, the
map, live locations, and alert feed update over a WebSocket the backend pushes to every
few seconds, with an automatic fallback to HTTP polling if the socket can't connect. A
heatmap layer plots both live positions and alert locations. Digital ID lookups happen via
`GET /api/verify/{token}`, which checks the JWT and, if blockchain is configured, cross-
checks the chain too.

**5. Offline support & SOS**
Pressing SOS always writes a real alert to the database first, so the dashboard side works
even if SMS dispatch fails. If Twilio is configured, it also texts the configured dispatch
number. The "IoT band" panic button on `iot.html` isn't backed by real hardware (there's no
device to build for a software-track hackathon submission), but it now calls the same real
`/api/sos` endpoint the in-app button does, instead of pretending to log an alert nowhere
reads.

## Stack

- Backend: FastAPI, raw sqlite3 (no ORM), scikit-learn (IsolationForest), web3.py (optional
  on-chain layer), python-jose (JWT), Twilio (optional SMS)
- Frontend: plain HTML/CSS/JS, Bootstrap 5, Leaflet + Leaflet.heat
- Smart contract: Solidity 0.8.20

## Running it

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 ml/train_model.py       # trains and saves the anomaly model - do this once before first run
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` — FastAPI serves the frontend directly, so it's one command.
The dashboard is at `dbpolice.html`; a demo officer login is created automatically on first
run (badge `ADMIN001`) with the password printed to the console — change it before this
goes anywhere beyond a local demo.

Optional env vars:

```bash
export JWT_SECRET_KEY=something_long_and_random   # change before any real deployment

# SMS (SOS dispatch + zone-entry safety guidance) - without these, SMS is logged as "simulated"
export TWILIO_SID=your_sid
export TWILIO_TOKEN=your_token
export TWILIO_FROM=your_twilio_number
export DISPATCH_TO_NUMBER=number_to_receive_sos_alerts

# On-chain digital ID - without these, registration works on JWT alone
export CHAIN_RPC_URL=your_testnet_rpc_url
export CHAIN_PRIVATE_KEY=your_wallet_private_key   # needs testnet funds, never a real wallet
export CHAIN_CONTRACT_ADDRESS=deployed_TouristID_address
```

## Project structure

```
backend/
├── main.py                  # FastAPI app, mounts the frontend as static files
├── database.py               # sqlite schema + seed data (demo officer, default zones)
├── models.py                 # Pydantic request/response schemas
├── auth.py                   # JWT signing (tourist + officer tokens), password hashing
├── deps.py                   # FastAPI dependency: require a valid officer session
├── zones.py                  # DB-backed risk zone lookups + haversine geofence math
├── sms.py                    # shared Twilio wrapper
├── ml/
│   ├── features.py           # location history -> feature vector
│   ├── train_model.py        # trains the IsolationForest on synthetic data
│   ├── anomaly_model.py       # loads the trained model, scores at request time
│   └── model.joblib           # trained model (committed so the repo runs out of the box)
├── blockchain/
│   ├── contracts/TouristID.sol
│   ├── abi.json                # hand-written ABI matching the contract
│   ├── web3_client.py          # optional on-chain issue/verify/revoke
│   └── deploy.py                # compiles + deploys TouristID.sol to a testnet
├── routers/
│   ├── tourist_id.py          # POST /api/register, GET /api/verify/{token}
│   ├── geofence.py             # POST /api/location/ping
│   ├── anomaly.py               # POST /api/anomaly/check/{tourist_id}
│   ├── sos.py                    # POST /api/sos
│   ├── auth.py                    # POST /api/auth/login (officer)
│   ├── zones.py                    # GET/POST/DELETE /api/zones
│   ├── reports.py                   # POST/GET /api/reports
│   └── dashboard.py                  # alerts, live-locations, WebSocket push
└── requirements.txt
frontend/
├── index.html, form.html, map.html, sos.html, dbpolice.html, iot.html, report.html, ...
└── js/app.js, css/style.css
```

## Known gaps

Still worth being upfront about:

- **Blockchain layer is written but not deployed anywhere by default.** The contract and
  web3.py integration are real code, but they were built without network access to a
  compiler or a live testnet, so they haven't been runtime-tested end-to-end the way the ML
  model has. Deploy it yourself and smoke-test `issue_onchain`/`is_valid_onchain` before
  relying on it in a demo.
- **ML model is trained on synthetic data**, not real tourist movement logs, because none
  exist yet. It's a real model doing real inference, just not trained on real-world data.
- **WebSocket push is per-connection polling on the server side**, not a fully event-driven
  broadcast. Fine for a single-process demo; would want a message queue (Redis or similar)
  behind it to scale to many concurrent officer sessions across multiple server processes.
- **SMS needs your own Twilio account** — not connected to any real emergency dispatch
  infrastructure, which would need an actual partnership with police/helpline systems.
- **CORS is wide open** (`allow_origins=["*"]`) since the frontend and backend are served
  same-origin in this setup — tighten this if the frontend ever gets deployed separately.
