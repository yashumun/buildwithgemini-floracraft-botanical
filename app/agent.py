# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore, storage
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

load_dotenv()

# IMPORTANT: Hardcoded Project ID string for Firestore & GCS clients
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-fc15cbf44ce2"
GCS_BUCKET_NAME = "floracraft-images-qwiklabs-gcp-03-fc15cbf44ce2"
MEMORY_BANK_ID = "907886542263943168"
MEMORY_LOCATION = "us-east1"


def _get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_plants(light_requirement: str = None, pet_friendly: bool = None) -> str:
    """Searches the botanical plant catalog in Firestore by light requirement or pet friendliness.

    Args:
        light_requirement: Optional light requirement string (e.g. 'low light', 'bright indirect', 'medium indirect').
        pet_friendly: Optional boolean to filter plants that are safe for pets (True or False).

    Returns:
        String listing matching plant items from the database.
    """
    db = _get_firestore_client()
    query_ref = db.collection("plants")

    docs = query_ref.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if light_requirement and light_requirement.lower() not in data.get("light_requirement", "").lower():
            continue
        if pet_friendly is not None and data.get("pet_friendly") != pet_friendly:
            continue
        results.append(data)

    if not results:
        return "No plants found matching the specified search criteria."
    return str(results)


def get_plant_details(plant_id: str) -> str:
    """Fetches full details for a specific plant from Firestore by its plant ID.

    Args:
        plant_id: The unique identifier of the plant (e.g., 'monstera-deliciosa', 'snake-plant', 'peperomia-obtusifolia', 'calathea-orbifolia', 'boston-fern').

    Returns:
        String with detailed information about the plant, or error message if not found.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()
    if not doc.exists:
        return f"Plant with ID '{plant_id}' was not found in the catalog."
    return str(doc.to_dict())


def log_plant_care(plant_name: str, care_type: str, notes: str = "") -> str:
    """Logs a plant care activity (e.g., watering, fertilizing, pruning) into Firestore.

    Args:
        plant_name: Name of the plant being cared for.
        care_type: Type of care action performed (e.g. 'watering', 'fertilizing', 'repotted').
        notes: Optional notes about the care activity.

    Returns:
        Confirmation message with logged details.
    """
    db = _get_firestore_client()
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_entry = {
        "plant_name": plant_name,
        "care_type": care_type,
        "notes": notes,
        "timestamp": now_str,
    }
    db.collection("plant_care_logs").add(log_entry)
    return f"Successfully recorded '{care_type}' care log for '{plant_name}'."


def calculate_plant_watering_schedule(
    plant_id: str, pot_diameter_inches: float = 6.0, humidity_level: str = "moderate"
) -> str:
    """Calculates customized watering volume and schedule for a plant based on pot size and room humidity.

    Args:
        plant_id: The ID of the plant (e.g., 'monstera-deliciosa', 'snake-plant', 'peperomia-obtusifolia', 'calathea-orbifolia', 'boston-fern').
        pot_diameter_inches: Diameter of the pot in inches (default 6.0).
        humidity_level: Room humidity level ('low', 'moderate', or 'high').

    Returns:
        Formatted watering schedule string with volume in mL and frequency in days.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()

    base_days = 7
    plant_name = plant_id
    if doc.exists:
        data = doc.to_dict()
        base_days = data.get("water_frequency_days", 7)
        plant_name = data.get("name", plant_id)

    humidity = humidity_level.lower()
    days_adj = 0
    if "low" in humidity:
        days_adj = -1
    elif "high" in humidity:
        days_adj = 2

    final_days = max(2, base_days + days_adj)
    water_volume_ml = round(pot_diameter_inches * 50)
    next_date = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=final_days)
    ).strftime("%Y-%m-%d")

    return (
        f"Watering Schedule for {plant_name} ({pot_diameter_inches}\" pot, {humidity_level} humidity):\n"
        f"- Recommended Water Volume: ~{water_volume_ml} mL (~{round(water_volume_ml / 29.57, 1)} fl oz)\n"
        f"- Frequency: Every {final_days} days\n"
        f"- Next Recommended Watering Date: {next_date}"
    )


def fetch_outdoor_plant_environment(location: str) -> str:
    """Fetches real-time outdoor climate conditions (temperature, humidity, daylight, precipitation) for a location using the Open-Meteo public API.

    Args:
        location: City or location name (e.g. 'San Francisco', 'Seattle', 'Miami', 'Tokyo').

    Returns:
        Formatted string containing real-time outdoor climate metrics for plant care.
    """
    api_key = os.getenv("OPEN_METEO_API_KEY", "")
    encoded_loc = urllib.parse.quote(location)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1"
    if api_key:
        geo_url += f"&apikey={api_key}"

    try:
        req = urllib.request.Request(geo_url, headers={"User-Agent": "FloraCraftAgent/1.0"})
        with urllib.request.urlopen(req) as resp:
            geo_data = json.loads(resp.read().decode())

        results = geo_data.get("results")
        if not results:
            return f"Could not find coordinates for location '{location}'."

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        place_name = f"{results[0].get('name')}, {results[0].get('country', '')}"

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,is_day,precipitation"
        )
        if api_key:
            weather_url += f"&apikey={api_key}"

        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "FloraCraftAgent/1.0"})
        with urllib.request.urlopen(req_w) as resp_w:
            weather_data = json.loads(resp_w.read().decode())

        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m")
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else "N/A"
        humidity = current.get("relative_humidity_2m", "N/A")
        is_day = "Daylight ☀️" if current.get("is_day") == 1 else "Nighttime 🌙"
        precip = current.get("precipitation", 0.0)

        return (
            f"Outdoor Climate Conditions for {place_name}:\n"
            f"- Temperature: {temp_c}°C ({temp_f}°F)\n"
            f"- Relative Humidity: {humidity}%\n"
            f"- Daylight Status: {is_day}\n"
            f"- Precipitation: {precip} mm"
        )
    except Exception as e:
        return f"Error fetching climate data for '{location}': {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic coordinates (latitude and longitude) using Google Maps Geocoding API.

    Args:
        address: The address or place name to geocode (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA' or 'Central Park, NY').

    Returns:
        Formatted string containing formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not set in environment."

    encoded_addr = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FloraCraftAgent/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for address '{address}': {data.get('status')}"

        result = data["results"][0]
        formatted_addr = result.get("formatted_address", address)
        location = result["geometry"]["location"]
        lat, lng = location["lat"], location["lng"]

        return (
            f"Geocoding Result for '{address}':\n"
            f"- Formatted Address: {formatted_addr}\n"
            f"- Latitude: {lat}\n"
            f"- Longitude: {lng}"
        )
    except Exception as e:
        return f"Error geocoding address '{address}': {str(e)}"


def find_nearby_places(
    latitude: float, longitude: float, place_type: str = "florist", radius_meters: float = 5000.0
) -> str:
    """Finds nearby places of a given type around a latitude/longitude using Google Maps Places API (New).

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Primary place type to search for (e.g., 'florist', 'park', 'store').
        radius_meters: Search radius in meters (default 5000.0 meters / 5km).

    Returns:
        Formatted string listing nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not set in environment."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters,
            }
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "FloraCraftAgent/1.0",
    }

    try:
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m."

        formatted_places = []
        for p in places:
            name = p.get("displayName", {}).get("text", "Unknown Place")
            addr = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat_val = loc.get("latitude", "N/A")
            lng_val = loc.get("longitude", "N/A")
            formatted_places.append(
                f"- Name: {name}\n  Address: {addr}\n  Location: Latitude {lat_val}, Longitude {lng_val}"
            )

        return f"Nearby '{place_type}' Places:\n" + "\n".join(formatted_places)
    except Exception as e:
        return f"Error searching nearby places: {str(e)}"


def generate_plant_image(plant_prompt: str, tool_context: ToolContext) -> str:
    """Generates a visual image preview for a botanical plant using gemini-3.1-flash-lite-image, saves it to Playground Artifacts, and uploads directly to GCS.

    Args:
        plant_prompt: Detailed prompt describing the plant or botanical item to visualize.
        tool_context: ADK ToolContext injected automatically.

    Returns:
        String containing the public GCS HTTPS URL of the generated image.
    """
    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=f"High quality realistic photo of {plant_prompt}",
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )

    image_bytes = None
    mime_type = "image/jpeg"

    if response.candidates:
        for candidate in response.candidates:
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/jpeg"
                        break

    if not image_bytes:
        return "Error: Failed to generate image bytes from model response."

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"plant_image_{timestamp}.jpg"

    # 1. Save artifact in ToolContext for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename, artifact_part)

    # 2. Upload image bytes directly to public GCS bucket (in-memory bytes, no local file path)
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return f"Image generated successfully! Public GCS URL: {public_url}"


def generate_plant_video(plant_prompt: str, tool_context: ToolContext) -> str:
    """Generates a short video clip for a botanical plant using gemini-omni-flash-preview in the global region, saves it to Playground Artifacts, and uploads directly to GCS.

    Args:
        plant_prompt: Detailed prompt describing the plant or botanical scene to generate in a video.
        tool_context: ADK ToolContext injected automatically.

    Returns:
        String containing the public GCS HTTPS URL of the generated video.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Short video clip of {plant_prompt}"
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(interaction, "output_video") and interaction.output_video:
            raw_data = interaction.output_video.data
            if isinstance(raw_data, str):
                video_bytes = base64.b64decode(raw_data)
            elif isinstance(raw_data, bytes):
                video_bytes = raw_data

        if not video_bytes:
            return "Error: Failed to extract video bytes from model interaction response."

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"plant_video_{timestamp}.mp4"

        # 1. Save artifact in ToolContext for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename, artifact_part)

        # 2. Upload video bytes directly to public GCS bucket (in-memory bytes, no local file path)
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Video generated successfully! Public GCS URL: {public_url}"
    except Exception as e:
        return f"Error generating plant video: {str(e)}"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after each turn to extract durable facts and store in Memory Bank."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory generation skipped: {e}")
    return None


def memory_bank_service_builder():
    """Service builder for Vertex AI Memory Bank when deployed."""
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location=MEMORY_LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FloraCraft Botanical Assistant, an expert AI assistant for indoor and outdoor plants. "
        "Help users discover plants from the botanical catalog, inspect plant care requirements, "
        "calculate customized watering schedules, fetch real outdoor climate metrics, geocode locations, "
        "find nearby botanical shops/florists, generate plant image previews, and log plant care activities using your tools."
    ),
    workflow_description="Analyze the request, call tools as needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "MEMORY & SAFETY MANDATE:\n"
        "- Actively remember and recall all user facts, preferences, and especially USER ALLERGIES & SENSITIVITIES "
        "(e.g., plant toxicity, pollen allergies, contact dermatitis, sap sensitivities like Euphorbia/Ficus, or pet allergies) "
        "across sessions using your memory tool.\n"
        "- When recommending or discussing plants, ALWAYS cross-reference the user's remembered allergies and explicitly warn or avoid "
        "any plants that pose allergy or toxicity risks to the user."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        search_plants,
        get_plant_details,
        log_plant_care,
        calculate_plant_watering_schedule,
        fetch_outdoor_plant_environment,
        geocode_address,
        find_nearby_places,
        generate_plant_image,
        generate_plant_video,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
