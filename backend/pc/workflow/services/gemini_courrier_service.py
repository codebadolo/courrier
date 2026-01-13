# workflow/services/gemini_courrier_service.py
import json
import logging
import re
from django.conf import settings
from django.utils import timezone
from core.models import Category, Service
from courriers.models import ActionHistorique

logger = logging.getLogger(__name__)

def robust_json_parser(response_text):
    """
    Parseur JSON robuste qui gère plusieurs formats de réponse
    """
    try:
        # Nettoyage 1: Retirer les balises de code markdown
        cleaned = response_text.strip()
        
        # Enlever ```json et ```
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        cleaned = cleaned.strip()
        
        # Essai 1: Parser directement
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.debug(f"Premier parsing échoué: {e}")
        
        # Essai 2: Chercher le JSON avec regex
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Essai 3: Nettoyer les échappements problématiques
        cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'', cleaned)
        
        # Essai 4: Réparer les guillemets non fermés
        def fix_unclosed_quotes(text):
            count = 0
            result = []
            for char in text:
                if char == '"':
                    count += 1
                result.append(char)
            # Si nombre impair de guillemets, en ajouter un à la fin
            if count % 2 == 1:
                result.append('"')
            return ''.join(result)
        
        cleaned = fix_unclosed_quotes(cleaned)
        
        # Essai 5: Réparer les accolades/crochets non fermés
        stack = []
        for char in cleaned:
            if char == '{' or char == '[':
                stack.append(char)
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif char == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
        
        # Fermer les balises manquantes
        for char in reversed(stack):
            cleaned += '}' if char == '{' else ']'
        
        # Essai final
        return json.loads(cleaned)
        
    except Exception as e:
        logger.error(f"Échec total du parsing JSON: {e}")
        logger.debug(f"Texte d'origine: {response_text[:500]}")
        
        # Retourner une structure par défaut
        return {
            "analyse": {
                "nature": "Information",
                "sujet_principal": "Erreur d'analyse",
                "resume": "L'analyse IA a rencontré une erreur de parsing",
                "mots_cles": ["erreur", "analyse"],
                "ton": "Formel",
                "actions_requises": ["Vérification manuelle"]
            },
            "classification": {
                "categorie_suggeree": "ADMINISTRATIF",
                "service_suggere": "Secrétariat Général",
                "confiance_categorie": 0.1,
                "confiance_service": 0.1
            },
            "priorite": {
                "niveau": "NORMALE",
                "delai_recommandé_jours": 10,
                "raison": "Erreur d'analyse IA"
            },
            "extraction": {
                "dates_importantes": [],
                "montants": [],
                "references": [],
                "personnes_impliquees": []
            }
        }

class CourrierGeminiService:
    """
    Service d'analyse de courrier avec Gemini AI - Version corrigée
    """
    
    def __init__(self):
        # Vérifier que la clé API est configurée
        if not hasattr(settings, 'GEMINI_API_KEY') or not settings.GEMINI_API_KEY:
            logger.error("CLÉ API GEMINI NON CONFIGURÉE !")
            raise ValueError("La clé API Gemini n'est pas configurée dans les settings.")
        
        try:
            from .gemini_base import GeminiService
            self.gemini = GeminiService()
            self.model = "gemini-2.5-flash"
            logger.info("Service Gemini initialisé avec succès")
        except Exception as e:
            logger.error(f"Échec initialisation Gemini: {e}")
            raise
    
# Dans gemini_courrier_service.py
    def analyser_courrier(self, courrier):
        """
        Analyse complète d'un courrier avec extraction de toutes les informations
        """
        try:
            # Préparer le texte pour l'analyse
            texte_complet = f"""
            OBJET: {courrier.objet or ''}
            EXPÉDITEUR: {courrier.expediteur_nom or ''}
            EMAIL: {courrier.expediteur_email or ''}
            TÉLÉPHONE: {courrier.expediteur_telephone or ''}
            ADRESSE: {courrier.expediteur_adresse or ''}
            DATE: {courrier.date_reception or ''}
            CONTENU:
            {courrier.contenu_texte or ''}
            """
            
            # Prompt amélioré pour l'IA
            prompt = f"""
            Analyse ce document et extrait toutes les informations suivantes:
            
            1. CATÉGORIE: Quelle est la catégorie administrative (ex: RH, Finances, Technique, Juridique, etc.)
            2. SERVICE: À quel service doit-il être imputé (ex: Secrétariat Général, RH, Finances, etc.)
            3. PRIORITÉ: Quelle est la priorité (URGENTE, HAUTE, NORMALE, BASSE) et pourquoi
            4. CONFIDENTIALITÉ: Quelle est le niveau de confidentialité (CONFIDENTIELLE, RESTREINTE, NORMALE)
            5. RÉSUMÉ: Fais un résumé de 3-4 lignes
            6. MOTS-CLÉS: Liste 5-10 mots-clés importants
            7. DATE: Identifie la date du document si présente
            8. EXPÉDITEUR: Identifie le nom complet de l'expéditeur
            
            Document à analyser:
            {texte_complet}
            
            Retourne la réponse au format JSON avec cette structure:
            {{
                "classification": {{
                    "categorie_suggeree": "nom de la catégorie",
                    "service_suggere": "nom du service",
                    "confiance_categorie": 0.0 à 1.0,
                    "confiance_service": 0.0 à 1.0
                }},
                "priorite": {{
                    "niveau": "URGENTE/HAUTE/NORMALE/BASSE",
                    "raison": "explication",
                    "confiance": 0.0 à 1.0
                }},
                "confidentialite_suggestion": "CONFIDENTIELLE/RESTREINTE/NORMALE",
                "analyse": {{
                    "resume": "résumé du document",
                    "mots_cles": ["mot1", "mot2", ...]
                }}
            }}
            """
            
            # Appeler l'API Gemini
            response = self.model.generate_content(prompt)
            
            # Parser la réponse JSON
            import json
            import re
            
            # Extraire le JSON de la réponse
            response_text = response.text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                
                # Enrichir avec l'extraction d'expéditeur si disponible
                if not courrier.expediteur_nom and 'expediteur' in response_text:
                    # Tenter d'extraire l'expéditeur du texte
                    expediteur_match = re.search(r'EXPÉDITEUR[:\s]+([^\n]+)', response_text, re.IGNORECASE)
                    if expediteur_match:
                        result['expediteur'] = {"nom": expediteur_match.group(1).strip()}
                
                return result
            else:
                # Retourner un résultat par défaut
                return {
                    "classification": {
                        "categorie_suggeree": "ADMINISTRATIF",
                        "service_suggere": "Secrétariat Général",
                        "confiance_categorie": 0.3,
                        "confiance_service": 0.3
                    },
                    "priorite": {
                        "niveau": "NORMALE",
                        "raison": "Document administratif standard",
                        "confiance": 0.5
                    },
                    "confidentialite_suggestion": "NORMALE",
                    "analyse": {
                        "resume": texte_complet[:200],
                        "mots_cles": ["document", "administratif"]
                    }
                }
                
        except Exception as e:
            logger.error(f"Erreur analyse Gemini: {e}")
            raise e   
    def _construire_prompt_simplifie(self, texte_courrier, courrier):
        """
        Construit un prompt SIMPLE et ROBUSTE pour Gemini
        """
        # Obtenir les catégories et services
        categories = list(Category.objects.values_list('name', flat=True)[:20])  # Limiter pour éviter trop long
        services = list(Service.objects.values_list('nom', flat=True)[:20])
        
        prompt = f"""Tu es un assistant IA qui analyse des courriers administratifs.

COURRIER À ANALYSER:
{texte_courrier}

INSTRUCTIONS:
1. Analyse ce courrier
2. Réponds UNIQUEMENT en format JSON valide
3. Suis EXACTEMENT ce format:

{{
  "categorie_suggeree": "Choisis parmi: {', '.join(categories)}",
  "service_suggere": "Choisis parmi: {', '.join(services)}",
  "confiance_categorie": 0.95,
  "confiance_service": 0.95,
  "priorite_niveau": "BASSE ou NORMALE ou HAUTE ou URGENTE",
  "priorite_raison": "Explique brièvement",
  "resume": "Résume en 2 phrases"
}}

RÈGLES IMPORTANTES:
- Les catégories et services DOIVENT être exactement dans les listes ci-dessus
- Si incertain, utilise "ADMINISTRATIF" et "Secrétariat Général"
- Réponds UNIQUEMENT avec le JSON, rien d'autre avant ou après"""
        
        return prompt
    
    def _valider_structure_analyse(self, data):
        """Valide la structure minimale de l'analyse"""
        required_keys = ['categorie_suggeree', 'service_suggere']
        return all(key in data for key in required_keys)
    
    def _corriger_structure_analyse(self, data):
        """Corrige la structure de l'analyse"""
        default = self._get_analyse_par_defaut()
        
        if not isinstance(data, dict):
            return default
        
        # Fusionner avec les valeurs par défaut
        corrected = default.copy()
        corrected.update(data)
        
        return corrected
    
    def _preparer_texte_analyse(self, courrier):
        """Prépare le texte à analyser"""
        texte_parts = []
        
        if courrier.objet:
            texte_parts.append(f"OBJET: {courrier.objet}")
        if courrier.contenu_texte:
            texte_parts.append(f"CONTENU: {courrier.contenu_texte[:2000]}")  # Limiter la taille
        if courrier.expediteur_nom:
            texte_parts.append(f"EXPÉDITEUR: {courrier.expediteur_nom}")
        
        return "\n\n".join(texte_parts) if texte_parts else ""
    
    def _enrichir_analyse(self, analyse_data, courrier):
        """Enrichit l'analyse avec les objets réels"""
        try:
            # Chercher la catégorie
            categorie_nom = analyse_data.get('categorie_suggeree')
            if categorie_nom:
                category = Category.objects.filter(name__icontains=categorie_nom).first()
                if category:
                    analyse_data['categorie_id'] = category.id
            
            # Chercher le service
            service_nom = analyse_data.get('service_suggere')
            if service_nom:
                service = Service.objects.filter(nom__icontains(service_nom)).first()
                if service:
                    analyse_data['service_id'] = service.id
            
            # Standardiser le format de réponse
            formatted_data = {
                "classification": {
                    "categorie_suggeree": analyse_data.get('categorie_suggeree', 'ADMINISTRATIF'),
                    "service_suggere": analyse_data.get('service_suggere', 'Secrétariat Général'),
                    "confiance_categorie": min(float(analyse_data.get('confiance_categorie', 0.5)), 0.95),
                    "confiance_service": min(float(analyse_data.get('confiance_service', 0.5)), 0.95)
                },
                "priorite": {
                    "niveau": analyse_data.get('priorite_niveau', 'NORMALE').upper(),
                    "raison": analyse_data.get('priorite_raison', 'Priorité standard')
                }
            }
            
            return formatted_data
            
        except Exception as e:
            logger.error(f"Erreur enrichissement: {e}")
            return self._get_analyse_par_defaut()
    
    def _get_analyse_par_defaut(self):
        """Retourne une analyse par défaut"""
        return {
            "classification": {
                "categorie_suggeree": "ADMINISTRATIF",
                "service_suggere": "Secrétariat Général",
                "confiance_categorie": 0.3,
                "confiance_service": 0.3
            },
            "priorite": {
                "niveau": "NORMALE",
                "raison": "Analyse par défaut"
            }
        }
    
    def _journaliser_analyse(self, courrier, analyse_data, token_usage):
        """Journalise l'analyse"""
        try:
            ActionHistorique.objects.create(
                courrier=courrier,
                user=None,
                action="ANALYSE_IA_GEMINI",
                commentaire=f"Analyse IA: {analyse_data['classification']['categorie_suggeree']} -> {analyse_data['classification']['service_suggere']}"
            )
        except Exception as e:
            logger.error(f"Erreur journalisation: {e}")

# Instance globale
gemini_courrier_service = CourrierGeminiService()