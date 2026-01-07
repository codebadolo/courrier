# workflow/services/gemini_base.py
import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """
    Service de base pour appeler l'API Gemini
    """
    
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.default_model = "gemini-2.5-flash"
    
    def generate_content(self, prompt, model_name=None):
        """
        Génère du contenu avec Gemini
        """
        model = model_name or self.default_model
        
        try:
            url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.3,  # Plus déterministe pour l'analyse
                    "maxOutputTokens": 2048,
                    "topP": 0.8,
                    "topK": 40
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            logger.debug(f"Appel Gemini à {model}")
            
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extraire le texte
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Calculer l'usage de tokens
                    usage = data.get("usageMetadata", {})
                    token_usage = {
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "candidates_tokens": usage.get("candidatesTokenCount", 0),
                        "total_tokens": usage.get("totalTokenCount", 0)
                    }
                    
                    return {
                        "success": True,
                        "text": text.strip(),
                        "model_used": model,
                        "token_usage": token_usage,
                        "raw_response": data
                    }
                else:
                    return {
                        "success": False,
                        "error": "Aucune réponse dans la candidate",
                        "raw_response": data
                    }
            else:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_text = error_json.get("error", {}).get("message", error_text)
                except:
                    pass
                
                return {
                    "success": False,
                    "error": f"Erreur API ({response.status_code}): {error_text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error("Timeout Gemini")
            return {
                "success": False,
                "error": "Timeout de l'API Gemini"
            }
        except Exception as e:
            logger.error(f"Erreur Gemini: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Exception: {str(e)}"
            }