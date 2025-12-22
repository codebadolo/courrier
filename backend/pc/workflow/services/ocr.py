import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from PyPDF2 import PdfReader

# Chemin explicite vers tesseract (Windows)
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def process_ocr(file_path: str, courrier):
    """
    - PDF texte : extraction directe
    - PDF scanné (image) : OCR
    - Image seule : OCR
    """

    extracted_text = ""

    # -------------------------
    # CAS 1 : PDF
    # -------------------------
    if file_path.lower().endswith(".pdf"):

        # 1️⃣ Tentative PDF TEXTE
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
        except Exception:
            pass  # on bascule sur OCR image

        # 2️⃣ Si vide → OCR sur images du PDF
        if not extracted_text.strip():
            try:
                images = convert_from_path(file_path)
                for image in images:
                    extracted_text += pytesseract.image_to_string(
                        image,
                        lang="fra+eng",
                        config="--oem 3 --psm 6"
                    )
            except Exception as e:
                raise ValueError(
                    f"Impossible de traiter le PDF via OCR (Poppler ?) : {e}"
                )

    # -------------------------
    # CAS 2 : IMAGE
    # -------------------------
    else:
        try:
            image = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(
                image,
                lang="fra+eng",
                config="--oem 3 --psm 6"
            )
        except Exception as e:
            raise ValueError(f"OCR image impossible : {e}")

    # -------------------------
    # Sauvegarde (optionnelle)
    # -------------------------
    if courrier:
        courrier.contenu_texte = extracted_text
        courrier.save(update_fields=["contenu_texte"])

    return extracted_text
