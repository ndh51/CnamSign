import io
import logging
import os
import re
import time
from typing import Dict, Optional
from PIL import Image
import pytesseract
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

import config

logger = logging.getLogger(__name__)

URL_EMARGEMENT = "https://cnamsigne.lecnam.net/emargement/Emargement.aspx"

class CnamSigner:
    def __init__(self):
        self.screenshots_dir = "screenshots"
        if config.DEBUG_SCREENSHOTS and not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir, exist_ok=True)

    def _save_screenshot(self, page: Page, name: str):
        if config.DEBUG_SCREENSHOTS:
            path = os.path.join(self.screenshots_dir, f"{int(time.time())}_{name}.png")
            page.screenshot(path=path)
            logger.debug(f"Capture d'écran sauvegardée : {path}")

    def _handle_login_sso(self, page: Page):
        """Gère l'authentification SSO Shibboleth si redirigé vers idp.lecnam.net."""
        current_url = page.url
        if "idp.lecnam.net" in current_url or "login" in current_url.lower():
            logger.info("Page de connexion SSO détectée. Saisie des identifiants...")

            # Sélecteurs habituels pour le portail SSO Le Cnam / Shibboleth
            username_selectors = [
                'input[name="j_username"]',
                '#username',
                'input[type="text"]',
                'input[name="username"]',
            ]
            password_selectors = [
                'input[name="j_password"]',
                '#password',
                'input[type="password"]',
            ]
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[name="_eventId_proceed"]',
                '#submit',
            ]

            user_field = None
            for sel in username_selectors:
                if page.locator(sel).first.is_visible():
                    user_field = page.locator(sel).first
                    break

            pwd_field = None
            for sel in password_selectors:
                if page.locator(sel).first.is_visible():
                    pwd_field = page.locator(sel).first
                    break

            if not user_field or not pwd_field:
                raise RuntimeError("Champs de connexion SSO introuvables.")

            user_field.fill(config.CNAM_USER)
            pwd_field.fill(config.CNAM_PASSWORD)

            self._save_screenshot(page, "sso_filled")

            for sel in submit_selectors:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    break

            page.wait_for_load_state("networkidle")
            logger.info("Connexion SSO soumise. En attente de la redirection...")

    def _read_keypad_digit(self, img_element) -> Optional[str]:
        """Tente d'identifier le chiffre affiché sur une touche du clavier virtuel."""
        # 1. Vérifier si un attribut contient le chiffre en clair
        for attr in ("alt", "title", "data-val", "data-code", "value"):
            val = img_element.get_attribute(attr)
            if val and val.strip().isdigit():
                return val.strip()

        # 2. Vérifier l'URL du src
        src = img_element.get_attribute("src") or ""
        match = re.search(r"[?&](?:val|digit|code|key|chiffre)=(\d)", src, re.IGNORECASE)
        if match:
            return match.group(1)

        # 3. Reconnaissance visuelle par OCR (Pytesseract)
        try:
            img_bytes = img_element.screenshot()
            image = Image.open(io.BytesIO(img_bytes)).convert("L")
            # Petit seuillage pour améliorer l'OCR
            image = image.point(lambda p: 255 if p > 128 else 0)
            text = pytesseract.image_to_string(
                image,
                config="--psm 10 -c tessedit_char_whitelist=0123456789"
            ).strip()
            if text.isdigit() and len(text) == 1:
                return text
        except Exception as e:
            logger.debug(f"Échec OCR sur touche : {e}")

        return None

    def _fill_virtual_keypad(self, page: Page, keypad_container_selector: str, pin: str):
        """Remplit le clavier virtuel pour le code PIN."""
        logger.info("Détection du clavier virtuel PIN...")
        keypad = page.locator(keypad_container_selector)
        if not keypad.is_visible():
            return

        # Récupérer les 16 touches images (ibtn_0 à ibtn_15)
        buttons = keypad.locator("table img").all()
        digit_to_element = {}

        for btn in buttons:
            digit = self._read_keypad_digit(btn)
            if digit:
                digit_to_element[digit] = btn

        logger.info(f"Touches identifiées : {list(digit_to_element.keys())}")

        # Cliquer les chiffres du PIN dans l'ordre
        for digit in pin:
            if digit not in digit_to_element:
                raise RuntimeError(f"Touche pour le chiffre '{digit}' introuvable sur le clavier.")
            digit_to_element[digit].click()
            time.sleep(0.3)

        self._save_screenshot(page, "pin_entered")

        # Clic sur le bouton de validation du code PIN
        valider_btn = page.locator('input[value="Valider le code PIN"], #lkbConnexion').first
        if valider_btn.is_visible() and not valider_btn.is_disabled():
            valider_btn.click()
            logger.info("Code PIN validé.")
            time.sleep(1.5)

    def _fill_session_code(self, page: Page, session_code: str):
        """Remplit les 6 cases du code de session reçu par e-mail."""
        logger.info(f"Saisie du code de session : {session_code}")
        if len(session_code) != 6 or not session_code.isdigit():
            raise ValueError(f"Le code de session doit comporter 6 chiffres : {session_code}")

        for i, char in enumerate(session_code, start=1):
            input_sel = f"#tbCodeSession_{i}"
            field = page.locator(input_sel)
            if field.is_visible():
                field.fill(char)
                time.sleep(0.1)

        self._save_screenshot(page, "session_code_filled")

        valider_btn = page.locator("#ctl00_c_codeAcces_btnValiderCode")
        if valider_btn.is_visible():
            valider_btn.click()
            logger.info("Code de session validé.")
            time.sleep(2)

    def _select_signature(self, page: Page):
        """Sélectionne l'option 'Utiliser la signature enregistrée'."""
        logger.info("Choix du mode de signature...")
        sig_btn = page.locator("#ctl00_c_lbImageSauvegardee, text='Utiliser la signature enregistrée'").first
        if sig_btn.is_visible():
            sig_btn.click()
            logger.info("Signature enregistrée sélectionnée.")
            time.sleep(1.5)

        # Clic sur le bouton final Valider si présent
        valider_final = page.locator("#ctl00_c_btnValider").first
        if valider_final.is_visible():
            valider_final.click()
            logger.info("Validation finale effectuée.")
            time.sleep(2)

BROWSER_PROFILE_DIR = os.path.abspath("browser_profile")

    def sign(self, session_code: str) -> bool:
        """Exécute le parcours complet d'émargement."""
        logger.info(f"Début du processus d'émargement avec le code {session_code}")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=config.HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.pages[0] if context.pages else context.new_page()

            try:
                # 1. Accès à la page d'émargement
                page.goto(URL_EMARGEMENT, wait_until="networkidle", timeout=60000)

                # 2. SSO si nécessaire
                self._handle_login_sso(page)

                # Si on est arrivé sur l'accueil, naviguer ou cliquer sur Émargement
                if "emargement" not in page.url.lower():
                    logger.info("Navigation vers la page d'émargement...")
                    page.goto(URL_EMARGEMENT, wait_until="networkidle")

                self._save_screenshot(page, "emargement_page")

                # 3. Clavier PIN initial (si affiché avant le code de session)
                if page.locator("#ctl00_c_ucKeyBoard_divKeyBoard").is_visible():
                    self._fill_virtual_keypad(page, "#ctl00_c_ucKeyBoard_divKeyBoard", config.CNAM_PIN)

                # 4. Saisie du code de session à 6 chiffres
                if page.locator("#tbCodeSession_1").is_visible():
                    self._fill_session_code(page, session_code)

                # 5. Choix de la signature
                self._select_signature(page)

                # 6. Clavier PIN contre-signature (si affiché après)
                if page.locator("#ctl00_c_ucKeyBoardContreSignature_divKeyBoard").is_visible():
                    logger.info("Clavier PIN de contre-signature détecté.")
                    self._fill_virtual_keypad(page, "#ctl00_c_ucKeyBoardContreSignature_divKeyBoard", config.CNAM_PIN)

                self._save_screenshot(page, "emargement_success")
                logger.info("Émargement terminé avec succès !")
                return True

            except Exception as e:
                logger.error(f"Erreur durant l'émargement : {e}")
                self._save_screenshot(page, "error")
                return False
            finally:
                context.close()
