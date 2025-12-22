import requests
import json
from django.conf import settings

GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

def classify_courrier_with_gemini(text: str):
    """
    Analyse le texte et retourne un JSON contenant 'categorie' et 'service'.
    """
    prompt = f"""
Tu es un assistant administratif.
Analyse le courrier suivant et retourne STRICTEMENT ce JSON :
{{
  "categorie": "...",
  "service": "..."
}}
Courrier :
{text}
"""
    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30
    )
    data = response.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)
    except Exception:
        return {"categorie": "Administratif", "service": "Service Administratif"}