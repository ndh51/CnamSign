from logging.handlers import RotatingFileHandler
import os
import sys
import time

import config
from mail_watcher import MailWatcher
from signer import CnamSigner

LOG_FILE = "logs.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"),
    ],
)
logger = logging.getLogger("cnamsign")

def main():
    logger.info("Démarrage du service d'émargement automatique CNAM...")
    try:
        config.validate_config()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    watcher = MailWatcher()
    signer = CnamSigner()
    failed_attempts = {}
    MAX_RETRIES = 3

    logger.info(f"Surveillance de la boîte {config.IMAP_USER} active (intervalle: {config.POLL_INTERVAL}s)")

    while True:
        try:
            code = watcher.check_for_code(auto_mark=False)
            if code:
                logger.info(f"==> Nouveau code trouvé ({watcher.last_detected_date}) : {code}")
                logger.info("==> Lancement du protocole de signature...")
                success = signer.sign(code)
                if success:
                    logger.info(f"==> Émargement réussi pour le code {code}")
                    watcher.mark_as_processed(code, watcher.last_detected_date)
                    failed_attempts.pop(code, None)
                else:
                    attempts = failed_attempts.get(code, 0) + 1
                    failed_attempts[code] = attempts
                    if attempts >= MAX_RETRIES:
                        logger.error(
                            f"==> Échec définitif pour le code {code} après {attempts} tentatives "
                            f"(session expirée, code inactif ou clos). Code marqué comme traité pour éviter une boucle infinie."
                        )
                        watcher.mark_as_processed(code, watcher.last_detected_date)
                        failed_attempts.pop(code, None)
                    else:
                        logger.error(
                            f"==> Échec de l'émargement pour le code {code} "
                            f"(tentative {attempts}/{MAX_RETRIES}) - nouvelle tentative au prochain cycle"
                        )
            else:
                logger.info("Pas de nouveau code.")

            time.sleep(config.POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Arrêt demandé par l'utilisateur.")
            break
        except Exception as e:
            logger.error(f"Erreur inattendue dans la boucle principale : {e}")
            time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
