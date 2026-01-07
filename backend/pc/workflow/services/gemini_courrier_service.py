# workflow/services/gemini_courrier_service.py
import json
import logging
from django.conf import settings
from django.utils import timezone
from core.models import Category, Service
from courriers.models import ActionHistorique
from .gemini_base import GeminiService

logger = logging.getLogger(__name__)

class CourrierGeminiService:
    """
    Service d'analyse de courrier avec Gemini AI
    """
    
    def __init__(self):
        self.gemini = GeminiService()
        self.model = "gemini-2.5-flash"
        
    def analyser_courrier(self, courrier):
        """
        Analyse complète d'un courrier avec Gemini AI
        Retourne un dictionnaire avec:
        - catégorie
        - service recommandé
        - priorité
        - résumé
        - mots-clés
        - actions suggérées
        """
        try:
            # Préparer le texte à analyser
            texte_analyse = self._preparer_texte_analyse(courrier)
            
            if not texte_analyse:
                logger.warning(f"Pas de texte pour analyser le courrier {courrier.id}")
                return None
            
            # Construire le prompt pour Gemini
            prompt = self._construire_prompt_analyse(texte_analyse, courrier)
            
            # Appeler Gemini
            result = self.gemini.generate_content(prompt, self.model)
            
            if result["success"]:
                # Parser la réponse JSON
                analyse_data = self._parser_reponse_gemini(result["text"])
                
                if analyse_data:
                    # Enrichir avec des informations supplémentaires
                    analyse_data = self._enrichir_analyse(analyse_data, courrier)
                    
                    # Journaliser l'analyse
                    self._journaliser_analyse(courrier, analyse_data, result.get("token_usage", {}))
                    
                    return analyse_data
                else:
                    logger.error(f"Impossible de parser la réponse Gemini pour {courrier.id}")
            else:
                logger.error(f"Erreur Gemini pour {courrier.id}: {result.get('error')}")
                
            return None
            
        except Exception as e:
            logger.error(f"Erreur analyse courrier {courrier.id} avec Gemini: {e}", exc_info=True)
            return None
    
    def _preparer_texte_analyse(self, courrier):
        """
        Prépare le texte à analyser depuis le courrier
        """
        texte_parts = []
        
        # Ajouter l'objet
        if courrier.objet:
            texte_parts.append(f"OBJET: {courrier.objet}")
        
        # Ajouter le contenu texte (OCR)
        if courrier.contenu_texte:
            texte_parts.append(f"CONTENU:\n{courrier.contenu_texte}")
        
        # Ajouter l'expéditeur
        if courrier.expediteur_nom:
            texte_parts.append(f"EXPÉDITEUR: {courrier.expediteur_nom}")
            if courrier.expediteur_email:
                texte_parts.append(f"EMAIL: {courrier.expediteur_email}")
        
        # Ajouter des métadonnées
        if courrier.date_reception:
            texte_parts.append(f"DATE RECEPTION: {courrier.date_reception}")
        
        return "\n\n".join(texte_parts) if texte_parts else ""
    
    def _construire_prompt_analyse(self, texte_courrier, courrier):
        """
        Construit le prompt pour l'analyse du courrier
        """
        # Obtenir les catégories et services existants pour le contexte
        categories = Category.objects.values_list('name', flat=True)
        services = Service.objects.values_list('nom', flat=True)
        
        prompt = f"""
        Tu es un expert en analyse de courrier administratif pour une entreprise.
        Analyse le courrier suivant et fournis une réponse au format JSON strict.

        COURRIER À ANALYSER:
        {texte_courrier}

        TÂCHES:
        1. Identifier la nature du courrier
        2. Déterminer la catégorie appropriée
        3. Identifier le service compétent
        4. Évaluer l'urgence et la priorité
        5. Extraire les informations clés
        6. Suggérer des actions

        FORMAT DE RÉPONSE (JSON stricte):
        {{
            "analyse": {{
                "nature": "string",  // ex: "Demande", "Réclamation", "Facture", "Candidature", "Information"
                "sujet_principal": "string",
                "resume": "string",  // Résumé en 2-3 phrases
                "mots_cles": ["mot1", "mot2", ...],
                "ton": "string",  // ex: "Formel", "Urgent", "Amiable", "Réclamant"
                "actions_requises": ["action1", "action2", ...]
            }},
            "classification": {{
                "categorie_suggeree": "string",  // Doit correspondre à une catégorie existante
                "service_suggere": "string",  // Doit correspondre à un service existant
                "confiance_categorie": 0.0-1.0,
                "confiance_service": 0.0-1.0
            }},
            "priorite": {{
                "niveau": "BASSE|NORMALE|HAUTE|URGENTE",
                "delai_recommandé_jours": number,
                "raison": "string"
            }},
            "extraction": {{
                "dates_importantes": ["date1", "date2"],
                "montants": ["montant1", "montant2"],
                "references": ["ref1", "ref2"],
                "personnes_impliquees": ["personne1", "personne2"]
            }}
        }}

        CONTEXTE (catégories existantes):
        Catégories disponibles: {', '.join(categories)}
        Services disponibles: {', '.join(services)}

        RÈGLES:
        - Toujours retourner du JSON valide
        - Les catégories et services doivent correspondre exactement aux noms fournis
        - Si incertain, utiliser "ADMINISTRATIF" et "Secrétariat Général"
        - Priorité "URGENTE" seulement pour les délais < 48h ou mentions explicites
        - Ne pas inventer de catégories ou services

        Réponds uniquement avec le JSON, sans commentaires, sans ```json, rien d'autre.
        """
        
        return prompt
    
    def _parser_reponse_gemini(self, reponse_text):
        """
        Parse la réponse textuelle de Gemini en JSON
        """
        try:
            # Nettoyer la réponse
            cleaned_text = reponse_text.strip()
            
            # Retirer les marqueurs de code si présents
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            cleaned_text = cleaned_text.strip()
            
            # Parser le JSON
            data = json.loads(cleaned_text)
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON Gemini: {e}")
            logger.debug(f"Texte à parser: {reponse_text[:500]}")
            
            # Tentative de récupération avec regex
            import re
            json_match = re.search(r'\{.*\}', reponse_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            return None
    
    def _enrichir_analyse(self, analyse_data, courrier):
        """
        Enrichit les données d'analyse avec des informations du système
        """
        # Rechercher les objets Category et Service correspondants
        if "classification" in analyse_data:
            categorie_nom = analyse_data["classification"].get("categorie_suggeree")
            service_nom = analyse_data["classification"].get("service_suggere")
            
            # Chercher la catégorie
            if categorie_nom:
                try:
                    category = Category.objects.filter(name__icontains=categorie_nom).first()
                    if category:
                        analyse_data["classification"]["categorie_id"] = category.id
                        analyse_data["classification"]["categorie_nom_complet"] = category.name
                except Exception as e:
                    logger.warning(f"Erreur recherche catégorie {categorie_nom}: {e}")
            
            # Chercher le service
            if service_nom:
                try:
                    service = Service.objects.filter(nom__icontains=service_nom).first()
                    if service:
                        analyse_data["classification"]["service_id"] = service.id
                        analyse_data["classification"]["service_nom_complet"] = service.nom
                        analyse_data["classification"]["service_chef"] = service.chef.email if service.chef else None
                except Exception as e:
                    logger.warning(f"Erreur recherche service {service_nom}: {e}")
        
        # Ajouter des métadonnées
        analyse_data["metadata"] = {
            "courrier_id": courrier.id,
            "courrier_reference": courrier.reference,
            "analysed_at": timezone.now().isoformat(),
            "gemini_model": self.model
        }
        
        return analyse_data
    
    def _journaliser_analyse(self, courrier, analyse_data, token_usage):
        """
        Journalise l'analyse dans l'historique
        """
        try:
            categorie = analyse_data.get("classification", {}).get("categorie_suggeree", "Non classé")
            service = analyse_data.get("classification", {}).get("service_suggere", "Non attribué")
            priorite = analyse_data.get("priorite", {}).get("niveau", "NORMALE")
            
            message = f"Analyse IA: Catégorie '{categorie}', Service '{service}', Priorité '{priorite}'"
            
            if token_usage:
                tokens = token_usage.get("total_tokens", 0)
                message += f" (Tokens: {tokens})"
            
            ActionHistorique.objects.create(
                courrier=courrier,
                user=None,  # Analyse automatique
                action="ANALYSE_IA_GEMINI",
                commentaire=message,
                nouvelles_valeurs=json.dumps(analyse_data, ensure_ascii=False)
            )
            
            logger.info(f"Analyse Gemini journalisée pour {courrier.reference}")
            
        except Exception as e:
            logger.error(f"Erreur journalisation analyse: {e}")
    
    def suggerer_reponse(self, courrier, analyse_data=None):
        """
        Suggère une réponse automatique basée sur l'analyse
        """
        try:
            if not analyse_data:
                analyse_data = self.analyser_courrier(courrier)
            
            if not analyse_data:
                return None
            
            # Construire le prompt pour la réponse
            prompt = self._construire_prompt_reponse(courrier, analyse_data)
            
            # Appeler Gemini
            result = self.gemini.generate_content(prompt, self.model)
            
            if result["success"]:
                reponse_text = result["text"]
                
                # Journaliser
                ActionHistorique.objects.create(
                    courrier=courrier,
                    user=None,
                    action="REPONSE_SUGGEREE_IA",
                    commentaire="Réponse automatique suggérée par Gemini"
                )
                
                return {
                    "success": True,
                    "reponse": reponse_text,
                    "model_used": self.model,
                    "token_usage": result.get("token_usage", {})
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error")
                }
                
        except Exception as e:
            logger.error(f"Erreur suggestion réponse pour {courrier.id}: {e}")
            return None
    
    def _construire_prompt_reponse(self, courrier, analyse_data):
        """
        Construit le prompt pour générer une réponse
        """
        prompt = f"""
        Tu es un assistant administratif rédigeant une réponse officielle.
        
        COURRIER ORIGINAL:
        Objet: {courrier.objet}
        Expéditeur: {courrier.expediteur_nom or 'Non spécifié'}
        Date: {courrier.date_reception or 'Non spécifiée'}
        
        Contenu:
        {courrier.contenu_texte or 'Aucun contenu disponible'}
        
        ANALYSE DU COURRIER:
        {json.dumps(analyse_data, indent=2, ensure_ascii=False)}
        
        TÂCHE:
        Rédige une réponse professionnelle et appropriée. 
        
        GUIDELINES:
        - Ton formel et courtois
        - Répondre à toutes les demandes identifiées
        - Proposer des solutions ou orientations
        - Indiquer les délais de traitement si applicable
        - Signer avec "Le Service [NOM_DU_SERVICE]"
        
        FORMAT:
        - Entête avec référence
        - Formule d'appel
        - Corps du message
        - Formule de politesse
        - Signature
        
        Réponds uniquement avec le texte de la réponse, sans commentaires.
        """
        
        return prompt

# Instance globale
gemini_courrier_service = CourrierGeminiService()