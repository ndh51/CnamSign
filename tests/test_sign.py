import os
import sys
import re
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from signer import CnamSigner
from mail_watcher import MailWatcher, PROCESSED_CODES_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_sign")

def test_sign():
    print("--- Test du processus d'émargement / signature ---")
    
    code = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit() and len(sys.argv[1]) == 6:
        code = sys.argv[1]
        print(f"[INFO] Utilisation du code passé en argument : {code}")
    else:
        # Tenter de récupérer depuis les codes récents ou depuis la boîte
        if os.path.exists(PROCESSED_CODES_FILE):
            with open(PROCESSED_CODES_FILE, "r", encoding="utf-8") as f:
                codes = []
                for line in f:
                    line = line.strip()
                    m = re.search(r"(\d{6})", line)
                    if m:
                        codes.append(m.group(1))
                if codes:
                    code = codes[-1]
                    print(f"[INFO] Dernier code détecté dans {PROCESSED_CODES_FILE} : {code}")

        if not code:
            print("[INFO] Recherche d'un code dans la boîte Outlook...")
            watcher = MailWatcher()
            code = watcher.check_for_code()

    if not code:
        print("[!] Aucun code de session disponible pour tester la signature.")
        print("Usage: python test_sign.py <CODE_6_CHIFFRES>")
        sys.exit(1)

    print(f"\n==> Démarrage du test d'émargement avec le code : {code}")
    signer = CnamSigner()
    success = signer.sign(code)

    if success:
        print(f"\n[SUCCÈS] Émargement validé avec succès pour le code {code} !")
        print("Consultez le dossier 'screenshots/' pour voir les captures d'écran.")
    else:
        print(f"\n[ÉCHEC] L'émargement a échoué. Vérifiez screenshots/error.png pour diagnostiquer.")
        sys.exit(1)

if __name__ == "__main__":
    test_sign()
