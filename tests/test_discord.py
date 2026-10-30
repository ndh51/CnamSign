import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from notifier import send_discord_notification

def test_discord():
    print("--- Test des notifications Discord (Webhook) ---")
    if not config.DISCORD_WEBHOOK_URL:
        print("\n[!] DISCORD_WEBHOOK_URL n'est pas renseigné dans votre fichier .env")
        print("Pour activer les notifications, ajoutez dans votre .env :")
        print("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        sys.exit(1)

    print(f"URL Webhook : {config.DISCORD_WEBHOOK_URL[:35]}...{config.DISCORD_WEBHOOK_URL[-10:]}")
    if config.DISCORD_USER_ID:
        print(f"ID Discord  : {config.DISCORD_USER_ID} (mention activée)")
    else:
        print("ID Discord  : Non renseigné (pas de mention)")

    student = config.STUDENT_NAME or (config.EMAIL.split("@")[0].replace(".", " ").title() if config.EMAIL else "Élève")
    print(f"Nom élève   : {student}")

    # Mode de test : succès par défaut, ou échec si argument 'error'
    test_mode = "success"
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("error", "echec", "fail", "alert"):
        test_mode = "error"

    if test_mode == "error":
        print("\nEnvoi d'une simulation d'alerte d'échec...")
        ok = send_discord_notification(
            status=False,
            subject="USSI25 - Référentiels SI (Simulation échec)",
            code="999999",
            error_message="Simulation : session expirée ou code inactif."
        )
    else:
        print("\nEnvoi d'une notification de succès de test...")
        ok = send_discord_notification(
            status=True,
            subject="USSI25 - Référentiels SI (Test)",
            code="123456"
        )

    if ok:
        print("\n[SUCCÈS] Notification envoyée avec succès sur Discord !")
        print("Consultez votre salon Discord pour vérifier le rendu.")
        if test_mode != "error":
            print("Astuce : testez aussi l'alerte d'échec avec :")
            print("  python tests/test_discord.py error")
    else:
        print("\n[ÉCHEC] Impossible d'envoyer la notification. Vérifiez l'URL de votre Webhook.")
        sys.exit(1)

if __name__ == "__main__":
    test_discord()
