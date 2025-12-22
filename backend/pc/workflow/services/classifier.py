# 
def classifier_courrier(text):
    text = text.lower()

    if "stage" in text:
        return {
            "category": "RH",
            "service": "Ressources Humaines",
            "priorite": "normale"
        }

    if "facture" in text or "paiement" in text:
        return {
            "category": "Financier",
            "service": "Comptabilité",
            "priorite": "haute"
        }

    return {
        "category": "Autre",
        "service": None,
        "priorite": "normale"
    }
