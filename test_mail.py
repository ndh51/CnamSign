import sys
import config
from mail_watcher import MailWatcher

def test_mail():
    print("--- Test de récupération de mail via Outlook Web (Dossier 'Emargements') ---")
    if not config.EMAIL or not config.PASSWORD:
        print("[!] EMAIL ou PASSWORD manquant dans le fichier .env")
        sys.exit(1)

    print(f"Connexion au compte {config.EMAIL}...")
    watcher = MailWatcher()
    code = watcher.check_for_code()

    if code:
        print(f"\n[SUCCÈS] Code d'émargement récupéré avec succès : {code}")
    else:
        print("\n[INFO] La boîte et le dossier 'Emargements' ont été vérifiés.")
        print("Aucun nouveau code non traité n'a été détecté (ou la boîte est vide).")

if __name__ == "__main__":
    test_mail()
