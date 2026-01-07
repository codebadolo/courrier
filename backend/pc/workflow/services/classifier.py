import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def classifier_courrier(courrier):
    """
    Classification IA simplifiée du courrier
    Retourne: {'category': 'RH', 'service_impute': 'Service RH', 'confidence': 0.85}
    """
    try:
        # Texte à analyser
        texte = ""
        if courrier.contenu_texte:
            texte += courrier.contenu_texte + " "
        if courrier.objet:
            texte += courrier.objet
        
        texte_lower = texte.lower()
        
        # Dictionnaire de mots-clés par catégorie
        categories_mots_cles = {
            'RH': ['emploi', 'salaire', 'contrat', 'congé', 'recrutement', 
                  'personnel', 'formation', 'paie', 'employé', 'embauche'],
            'FINANCE': ['facture', 'paiement', 'budget', 'compte', 'financier',
                       'fiscal', 'impôt', 'trésorerie', 'comptabilité', 'dépense'],
            'JURIDIQUE': ['contrat', 'loi', 'juridique', 'avocat', 'tribunal',
                         'litige', 'droit', 'justice', 'procès', 'jurisprudence'],
            'TECHNIQUE': ['maintenance', 'réparation', 'technique', 'logiciel',
                         'informatique', 'système', 'réseau', 'développement', 'bug'],
            'COMMERCIAL': ['client', 'vente', 'contrat', 'commercial', 'marché',
                          'offre', 'devis', 'proposition', 'négociation'],
            'ADMINISTRATIF': ['administration', 'document', 'archive', 'bureau',
                             'secrétariat', 'courrier', 'réunion', 'procédure']
        }
        
        services_mapping = {
            'RH': 'Service des Ressources Humaines',
            'FINANCE': 'Service Financier',
            'JURIDIQUE': 'Service Juridique',
            'TECHNIQUE': 'Service Technique',
            'COMMERCIAL': 'Service Commercial',
            'ADMINISTRATIF': 'Secrétariat Général'
        }
        
        # Calcul des scores par catégorie
        scores = {}
        for categorie, mots_cles in categories_mots_cles.items():
            score = 0
            for mot in mots_cles:
                if mot in texte_lower:
                    score += 1
            
            if score > 0:
                scores[categorie] = {
                    'score': score,
                    'pourcentage': min(score / len(mots_cles), 1.0)
                }
        
        # Trouver la catégorie avec le score le plus élevé
        if scores:
            meilleure_categorie = max(scores.items(), key=lambda x: x[1]['score'])[0]
            confiance = scores[meilleure_categorie]['pourcentage']
        else:
            meilleure_categorie = 'ADMINISTRATIF'
            confiance = 0.3
        
        # Service correspondant
        service = services_mapping.get(meilleure_categorie, 'Secrétariat Général')
        
        logger.info(f"Classification: {meilleure_categorie} ({confiance:.2f}), Service: {service}")
        
        return {
            'category': meilleure_categorie,
            'service_impute': service,
            'confidence': float(confiance)
        }
        
    except Exception as e:
        logger.error(f"Erreur classification: {e}")
        return {
            'category': 'ADMINISTRATIF',
            'service_impute': 'Secrétariat Général',
            'confidence': 0.1
        }