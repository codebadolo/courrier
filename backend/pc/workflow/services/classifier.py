def classify_text(text: str):
    """
    Retourne catégorie et service recommandé selon le texte.
    Remplacer par NLP avancé si nécessaire.
    """
    text_lower = text.lower()
    if "rh" in text_lower:
        return "Ressources Humaines", "Service RH"
    elif "facture" in text_lower or "finance" in text_lower:
        return "Finance", "Service Finance"
    elif "technique" in text_lower:
        return "Technique", "Service Technique"
    else:
        return "Administratif", "Service Administratif"
