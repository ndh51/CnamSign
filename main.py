import logging
import sys
import time

import config
from mail_watcher import MailWatcher
from signer import CnamSigner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
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

    logger.info(f"Surveillance de la boîte {config.IMAP_USER} active (intervalle: {config.POLL_INTERVAL}s)")

    while True:
        try:
            code = watcher.check_for_code()
            if code:
                logger.info(f"==> Nouveau code reçu : {code}")
                success = signer.sign(code)
                if success:
                    logger.info(f"==> Émargement réussi pour le code {code}")
                else:
                    logger.error(f"==> Échec de l'émargement pour le code {code}")

            time.sleep(config.POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Arrêt demandé par l'utilisateur.")
            break
        except Exception as e:
            logger.error(f"Erreur inattendue dans la boucle principale : {e}")
            time.sleep(config.POLL_INTERVAL)

if __name__ == "__main__":
    main()
