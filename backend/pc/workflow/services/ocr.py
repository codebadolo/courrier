# workflow/services/ocr.py
import pytesseract
from courriers.models import Courrier
from pdf2image import convert_from_path
import os

def process_ocr(courrier: Courrier, file_path: str):
    """
    Extrait le texte d'une pièce jointe (PDF ou image) et met à jour le courrier.
    """
    texte_complet = ""

    # Vérifier l'extension
    ext = os.path.splitext(file_path)[1].lower()

    if ext in [".pdf"]:
        # Conversion PDF -> images
        try:
            # Si vous êtes sous Windows, indiquez le chemin vers Poppler si nécessaire
            # images = convert_from_path(file_path, poppler_path=r"C:\chemin\vers\poppler\bin")
            images = convert_from_path(file_path)
        except Exception as e:
            raise ValueError(f"Impossible de convertir le PDF en image : {e}")

        for image in images:
            texte_complet += pytesseract.image_to_string(image) + "\n"

    else:
        # Si c'est une image directement
        texte_complet = pytesseract.image_to_string(file_path)

    # Mettre à jour le champ contenu_texte
    if courrier.contenu_texte:
        courrier.contenu_texte += "\n" + texte_complet
    else:
        courrier.contenu_texte = texte_complet

    courrier.save()
