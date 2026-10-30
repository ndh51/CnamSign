import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from notifier import send_discord_notification

def test_discord():
    print("--- Test d'envoi de notification Discord Webhook ---")
    if not config.DISCORD_WEBHOOK_URL:
        print("[!] DISCORD_WEBHOOK_URL n'est pas configuré dans votre fichier .env")
        print("Ajoutez DISCORD_WEBHOOK_URL=<votre_url> dans votre .env pour tester.")
        sys.exit(1)

    print("Envoi d'une notification de test (Succès)...")
    res = send_discord_notification(
        status=True,
        subject="USSI25 - Référentiels SI (Test)",
        code="123456"
    )

    if res:
        print("[SUCCÈS] Notification envoyée avec succès sur Discord !")
    else:
        print("[ÉCHEC] L'envoi a échoué. Vérifiez l'URL de votre Webhook.")

if __name__ == "__main__":
    test_discord()
