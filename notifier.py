import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

import config

logger = logging.getLogger(__name__)

def send_discord_notification(
    status: bool,
    subject: str,
    code: str,
    error_message: Optional[str] = None
) -> bool:
    """
    Envoie une notification Discord via Webhook.
    Ne lève jamais d'exception pour ne pas perturber le fonctionnement du service.
    """
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url:
        return False

    student = config.STUDENT_NAME
    if not student and config.EMAIL:
        student = config.EMAIL.split("@")[0].replace(".", " ").title()
    student = student or "Élève"

    user_id = config.DISCORD_USER_ID
    mention = f"<@{user_id}>" if user_id else ""

    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")

    if status:
        title = "✅ Émargement validé"
        color = 0x2ECC71  # Vert
        desc = "La signature a bien été validée et enregistrée pour cet événement."
    else:
        title = "⚠️ Échec de l'émargement"
        color = 0xE74C3C  # Rouge
        desc = "L'émargement automatique a échoué. Rendez-vous rapidement sur CnamSignE pour signer manuellement !"

    fields = [
        {"name": "👤 Élève", "value": student, "inline": True},
        {"name": "📚 Matière", "value": subject or "Non spécifiée", "inline": True},
        {"name": "🔑 Code", "value": code, "inline": True},
        {"name": "🕒 Heure", "value": now_str, "inline": True},
    ]

    if not status and error_message:
        fields.append({"name": "⚠️ Détail", "value": error_message, "inline": False})

    payload = {
        "username": "CnamSignSignSigner",
        "embeds": [
            {
                "title": title,
                "description": desc,
                "color": color,
                "fields": fields,
                "footer": {"text": "CnamSignSignSigner • Notification automatique"},
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        ]
    }

    if mention:
        payload["content"] = mention

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CnamSignSignSigner/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                logger.info("Notification Discord transmise avec succès.")
                return True
            else:
                logger.warning(f"Réponse inattendue de Discord : statut HTTP {resp.status}")
                return False
    except Exception as e:
        logger.error(f"Impossible d'envoyer la notification Discord : {e}")
        return False
