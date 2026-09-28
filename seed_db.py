"""Seed script for FloraCraft Botanical Assistant Firestore database."""
import sys
from google.cloud import firestore

# IMPORTANT: Hardcoded Project ID string to ensure compatibility with Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-fc15cbf44ce2"

PLANTS_DATA = [
    {
        "id": "monstera-deliciosa",
        "name": "Monstera Deliciosa",
        "light_requirement": "bright indirect",
        "water_frequency_days": 7,
        "pet_friendly": False,
        "price": 35.0,
        "description": "Popular tropical plant with dramatic split/fenestrated leaves. Thrives in warm, humid spaces.",
        "category": "indoor"
    },
    {
        "id": "snake-plant",
        "name": "Snake Plant (Sansevieria)",
        "light_requirement": "low light",
        "water_frequency_days": 14,
        "pet_friendly": False,
        "price": 24.0,
        "description": "Hardy air-purifying plant tolerant of low light and infrequent watering. Great for beginners.",
        "category": "indoor"
    },
    {
        "id": "peperomia-obtusifolia",
        "name": "Peperomia Obtusifolia (Baby Rubber Plant)",
        "light_requirement": "medium indirect",
        "water_frequency_days": 10,
        "pet_friendly": True,
        "price": 18.0,
        "description": "Compact plant with glossy succulent-like leaves. Completely non-toxic and safe for cats & dogs.",
        "category": "indoor"
    },
    {
        "id": "calathea-orbifolia",
        "name": "Calathea Orbifolia",
        "light_requirement": "medium indirect",
        "water_frequency_days": 5,
        "pet_friendly": True,
        "price": 30.0,
        "description": "Stunning tropical plant with large striped silver-green leaves. Safe for pets.",
        "category": "indoor"
    },
    {
        "id": "boston-fern",
        "name": "Boston Fern",
        "light_requirement": "medium indirect",
        "water_frequency_days": 4,
        "pet_friendly": True,
        "price": 22.0,
        "description": "Lush feathery fronds that love moisture and indirect sunlight. Pet-friendly.",
        "category": "indoor"
    }
]


def seed_firestore():
    print(f"Connecting to Firestore using project ID: '{FIRESTORE_PROJECT_ID}'...")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    
    collection_ref = db.collection("plants")
    print("Seeding 'plants' collection...")
    
    for item in PLANTS_DATA:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded plant: {item['name']} (ID: {doc_id})")
        
    print("\n✅ Firestore seeding completed successfully!")


if __name__ == "__main__":
    seed_firestore()
