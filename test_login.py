import os
import sys
from playwright.sync_api import sync_playwright

import config
from signer import CnamSigner, URL_EMARGEMENT

def test_login():
    print("--- Test de connexion SSO CnamSignE ---")
    if not config.CNAM_USER or not config.CNAM_PASSWORD:
        print("[!] CNAM_USER ou CNAM_PASSWORD manquant dans .env")
        sys.exit(1)

    os.makedirs("screenshots", exist_ok=True)
    screenshot_path = os.path.join("screenshots", "test_login_result.png")

    signer = CnamSigner()

    with sync_playwright() as p:
        print("Lancement du navigateur avec profil persistant...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=os.path.abspath("browser_profile"),
            headless=config.HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            print(f"Navigation vers {URL_EMARGEMENT}...")
            page.goto(URL_EMARGEMENT, wait_until="networkidle", timeout=60000)

            # Connexion SSO
            signer._handle_login_sso(page)

            print(f"URL finale après connexion : {page.url}")
            page.screenshot(path=screenshot_path)
            print(f"[OK] Capture de la page enregistrée dans : {screenshot_path}")

            if "cnamsigne.lecnam.net" in page.url:
                print("\n[SUCCÈS] Connexion réussie et session active sur CnamSignE !")
                # Vérifier si la page contient le nom de l'utilisateur ou le menu
                page_content = page.content()
                if "ctl00_liMenuDeconnexion" in page_content or "Emargement" in page_content:
                    print("[INFO] La page d'émargement est correctement chargée.")
            else:
                print("\n[ATTENTION] La redirection finale n'a pas abouti sur cnamsigne.lecnam.net.")

        except Exception as e:
            print(f"\n[ERREUR] Une erreur est survenue pendant le test : {e}")
            page.screenshot(path=os.path.join("screenshots", "test_login_error.png"))
        finally:
            context.close()

if __name__ == "__main__":
    test_login()
