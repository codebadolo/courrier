from django.core.mail import send_mail

def send_accuse_reception_email(courrier):
    if not courrier.expediteur_email:
        return

    subject = f"Accusé de réception – {courrier.reference}"
    message = f"""
Bonjour,

Nous accusons réception de votre courrier :
Objet : {courrier.objet}
Référence : {courrier.reference}

Cordialement,
Le service courrier
"""

    send_mail(
        subject,
        message,
        "no-reply@organisation.com",
        [courrier.expediteur_email],
        fail_silently=False
    )
