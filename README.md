# 🌿 FloraCraft Botanical Assistant

An intelligent, full-stack botanical AI assistant built with Google's **Agent Development Kit (ADK)**, **Gemini 2.5/3.1 models**, and **Agent Platform**. FloraCraft helps plant enthusiasts search plant catalogs, calculate watering schedules, check local weather metrics, discover nearby plant shops, record care logs, generate plant images & videos, and remember personal preferences across sessions with full safety checks.

![FloraCraft Botanical Demo](demo.gif)

---

## ✨ Implemented Capabilities & Tools

The agent code in `app/agent.py` implements the following function tools and integrations:

### 1. 🔍 Plant Catalog & Care Logging (Firestore)
- **`search_plants(light_requirement, pet_friendly)`**: Queries Google Cloud Firestore for indoor plants filtered by light needs and toxicity to pets.
- **`get_plant_details(plant_id)`**: Fetches comprehensive plant profile data including scientific name, price, watering intervals, and toxicity details.
- **`log_plant_care(plant_id, care_type, notes)`**: Logs plant care events (watering, fertilizing, repotting, pruning) directly to Firestore.

### 2. 💧 Watering & Climate Metrics (Open-Meteo Public API)
- **`calculate_plant_watering_schedule(plant_id, pot_type, ambient_temp_c)`**: Calculates personalized watering intervals based on plant species, pot material, and temperature.
- **`fetch_outdoor_plant_environment(latitude, longitude)`**: Fetches real-time outdoor temperature, humidity, and weather conditions from Open-Meteo API.

### 3. 🗺️ Location & Shop Discovery (Google Maps & Places APIs)
- **`geocode_address(address)`**: Converts street addresses or city names into latitude/longitude coordinates via Google Geocoding API.
- **`find_nearby_places(latitude, longitude, place_type, radius_meters)`**: Finds nearby plant nurseries, florists, and botanical shops using Google Places (New) API.

### 4. 🖼️ Visual & Video Asset Generation (Gemini & GCS)
- **`generate_plant_image(plant_prompt)`**: Generates visual previews using `gemini-3.1-flash-lite-image`, saves in-memory artifacts, and uploads directly to Google Cloud Storage.
- **`generate_plant_video(plant_prompt)`**: Generates short video clips using `gemini-omni-flash-preview` via the Interactions API, saves in-memory artifacts, and uploads to Cloud Storage.

### 5. 🧠 Cross-Session Memory & Safety (Vertex AI Memory Bank)
- **`PreloadMemoryTool`**: Preloads remembered facts and preferences at session start.
- **`generate_memories_callback`**: Automatically extracts durable facts (e.g., user allergies, pet ownership) after each turn and saves them to Vertex AI Memory Bank.
- **Allergy Safety Mandate**: Cross-references user allergies (pollen, sap sensitivities, plant toxicity) before making plant recommendations.

### 6. 🎨 Generative A2UI Protocol & Chat Frontend
- **A2UI Schema Manager (v0.8 Basic Catalog)**: Emits structured A2UI cards (Cards, Columns, Rows, Text, Images) as native UI components.
- **FastAPI A2A Proxy**: A lightweight FastAPI proxy server (`frontend/main.py`) translating browser HTTP requests to Agent Engine over A2A protocol.
- **Web Chat UI**: Plain HTML/CSS chat interface (`frontend/static/index.html`) with built-in A2UI card renderer.

---

## 🛠️ Infrastructure & Google Cloud Services
- **Framework**: Google ADK (Agent Development Kit v1.1.0)
- **Database**: Google Cloud Firestore
- **Storage**: Google Cloud Storage (GCS Public Bucket)
- **Memory Service**: Vertex AI Memory Bank (`Agent Engine`)
- **APIs**: Geocoding API, Places API (New), Open-Meteo REST API
- **Deployment Targets**: Agent Runtime & Cloud Run

---

## 🚀 Local Setup & Run Instructions

### 1. Prerequisites & Environment Setup
Clone the repository and set up environment variables:
```bash
cp .env.example .env
# Edit .env and supply your GOOGLE_MAPS_API_KEY
```

### 2. Run Agent Playground Locally
Start the local ADK web playground with memory bank enabled:
```bash
uv run adk web . --port 8080 --reload_agents --memory_service_uri=agentengine://<MEMORY_BANK_ID>
```

### 3. Run Web Chat Frontend Proxy
Navigate to `frontend/` and start the FastAPI proxy:
```bash
cd frontend
uv pip install -r requirements.txt
AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/us-east1/reasoningEngines/<ENGINE_ID>" AGENT_DIRECTORY="app" uv run python main.py
```
