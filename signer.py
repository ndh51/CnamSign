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
BROWSER_PROFILE_DIR = os.path.abspath("browser_profile")

class CnamSigner:
    def __init__(self):
        self.screenshots_dir = "screenshots"
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir, exist_ok=True)

    def _save_screenshot(self, page: Page, name: str):
        path = os.path.join(self.screenshots_dir, f"{int(time.time())}_{name}.png")
        page.screenshot(path=path)
        logger.debug(f"Capture d'écran sauvegardée : {path}")

    def _handle_login_sso(self, page: Page):
        """Gère l'authentification SSO Shibboleth si redirigé vers idp.lecnam.net."""
        current_url = page.url
        if "idp.lecnam.net" in current_url or "login" in current_url.lower():
            logger.info("Page de connexion SSO détectée. Saisie des identifiants...")

            username_selectors = [
                'input[name="j_username"]',
                '#identifiant',
                '#username',
                'input[type="text"]',
                'input[name="username"]',
            ]
            password_selectors = [
                'input[name="j_password"]',
                '#mdp',
                '#password',
                'input[type="password"]',
            ]
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[name="_eventId_proceed"]',
                '#submit',
                'button:has-text("Se connecter")',
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
            try:
                page.wait_for_url(lambda u: "idp.lecnam.net" not in u, timeout=15000)
            except Exception:
                pass
            logger.info("Connexion SSO soumise. Redirection vers : " + page.url)

    def _read_keypad_digit(self, img_element) -> Optional[str]:
        """Tente d'identifier le chiffre affiché sur une touche du clavier virtuel."""
        # 1. Vérifier le nom du fichier image src (ex: numpad_5.png)
        src = img_element.get_attribute("src") or ""
        match = re.search(r"numpad_(\d)\.png", src, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"[?&](?:val|digit|code|key|chiffre)=(\d)", src, re.IGNORECASE) or re.search(r"_(\d)\.png", src, re.IGNORECASE)
        if match:
            return match.group(1)

        # 2. Vérifier si un attribut contient le chiffre en clair
        for attr in ("alt", "title", "data-val", "data-code", "value"):
            val = img_element.get_attribute(attr)
            if val and val.strip().isdigit():
                return val.strip()

        # 3. Reconnaissance visuelle par OCR (Pytesseract) si disponible
        try:
            img_bytes = img_element.screenshot()
            image = Image.open(io.BytesIO(img_bytes)).convert("L")
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

    def _handle_pin_if_present(self, page: Page, pin: str, timeout_ms: int = 4000) -> bool:
        """Détecte et remplit un clavier virtuel PIN s'il est visible à l'écran."""
        try:
            keypad_key = page.locator("img[src*='numpad_']:visible").first
            keypad_key.wait_for(state="visible", timeout=timeout_ms)
        except Exception:
            # Aucun clavier virtuel affiché à cette étape
            return False

        logger.info("Clavier virtuel PIN détecté. Saisie du code PIN...")

        # Réinitialisation du champ PIN si le bouton croix est visible (champ déjà partiellement rempli)
        reset_btn = page.locator(".btnDelete:visible, img[id*='btnDelete']:visible, img[src*='croix']:visible").first
        if reset_btn.is_visible():
            reset_btn.click()
            time.sleep(0.3)

        # Récupérer les touches de chiffres visibles
        visible_imgs = [img for img in page.locator("img[src*='numpad_']").all() if img.is_visible()]
        digit_to_element = {}
        for btn in visible_imgs:
            digit = self._read_keypad_digit(btn)
            if digit:
                digit_to_element[digit] = btn

        logger.info(f"Touches PIN identifiées ({len(digit_to_element)}) : {sorted(digit_to_element.keys())}")

        # Cliquer les chiffres du PIN dans l'ordre
        for digit in pin:
            if digit not in digit_to_element:
                raise RuntimeError(f"Touche pour le chiffre '{digit}' introuvable sur le clavier.")
            digit_to_element[digit].click()
            time.sleep(0.2)

        self._save_screenshot(page, "pin_entered")

        # Clic sur le bouton de validation du code PIN qui est visible et actif
        time.sleep(0.5)
        valider_candidates = page.locator("#lkbConnexion, input[value*='Valider le code PIN'], input[value*='Valider'], button:has-text('Valider')").all()
        for btn in valider_candidates:
            if btn.is_visible() and not btn.is_disabled():
                btn.click()
                logger.info("Bouton de validation du code PIN cliqué.")
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                return True

        logger.warning("Clavier PIN rempli mais aucun bouton de validation actif trouvé.")
        return False

    def _fill_session_code(self, page: Page, session_code: str) -> bool:
        """Remplit les 6 cases du code de session reçu par e-mail et valide."""
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
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            return True
        return False

    def _confirm_presence_and_sign(self, page: Page, pin: str):
        """Gère la confirmation de présence, les éventuels PIN et le choix de la signature."""
        logger.info("Confirmation de présence et signature...")

        # 1. Cocher la case 'Je confirme ma présence'
        cb = page.locator("#cbConfirmer, input[id*='cbConfirmer']").first
        if cb.is_visible():
            cb.check()
            logger.info("Case 'Je confirme ma présence' cochée.")
            time.sleep(1)

        # 2. Cliquer sur le bouton Signer (icône stylo)
        btn_signer = page.locator("#btnSignerAuditeur, [id*='btnSignerAuditeur']").first
        if btn_signer.is_visible():
            btn_signer.click()
            logger.info("Bouton de signature cliqué.")
            time.sleep(1.5)

        # 3. Éventuel code PIN dans la modale (PIN #2)
        self._handle_pin_if_present(page, pin, timeout_ms=8000)

        # 4. Choix de la signature dans la modale
        logger.info("Vérification de la modale de choix de signature...")
        sig_btn = page.locator("#ctl00_c_lbImageSauvegardee, a:has-text('signature enregistrée')").first
        try:
            sig_btn.wait_for(state="visible", timeout=12000)
            if sig_btn.is_visible():
                sig_btn.click()
                logger.info("Option 'Utiliser la signature enregistrée' sélectionnée.")
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                return
        except Exception:
            pass

        # Alternative: pad de signature si aucune signature sauvegardée
        pad_btn = page.locator("#ctl00_c_btnSignaturePad, input[value*='pad']").first
        if pad_btn.is_visible():
            pad_btn.click()
            logger.info("Option 'Signer avec le pad' sélectionnée.")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            try:
                canvas = page.locator("canvas, #signature-pad canvas").first
                if canvas.is_visible():
                    box = canvas.bounding_box()
                    if box:
                        page.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.5)
                        page.mouse.down()
                        page.mouse.move(box["x"] + box["width"] * 0.8, box["y"] + box["height"] * 0.5, steps=5)
                        page.mouse.up()
                        time.sleep(1)
            except Exception:
                pass

        # 5. Éventuelle contre-signature par code PIN (PIN #3)
        self._handle_pin_if_present(page, pin, timeout_ms=3000)

        # 6. Bouton final Valider si présent
        valider_final = page.locator("#ctl00_c_btnValider, a:has-text('Valider'), input[value='Valider']").all()
        for v in valider_final:
            if v.is_visible() and not v.is_disabled():
                v.click()
                logger.info("Validation finale effectuée.")
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                break

    def sign(self, session_code: str) -> bool:
        """Exécute le parcours complet d'émargement."""
        logger.info(f"Début du processus d'émargement avec le code {session_code}")
        from mail_watcher import clean_browser_locks
        clean_browser_locks()
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

                # 2. SSO Shibboleth si nécessaire
                self._handle_login_sso(page)
                time.sleep(2)

                # 3. Clavier PIN initial (PIN #1 si sur CodePIN.aspx ou affiché en plein écran)
                self._handle_pin_if_present(page, config.CNAM_PIN, timeout_ms=4000)

                # 4. Navigation vers la page d'émargement si nécessaire
                if "emargement" not in page.url.lower():
                    logger.info("Navigation vers la page d'émargement...")
                    page.goto(URL_EMARGEMENT, wait_until="networkidle")
                    time.sleep(2)

                self._save_screenshot(page, "emargement_page")

                # 5. Saisie du code de session à 6 chiffres
                if page.locator("#tbCodeSession_1").is_visible():
                    self._fill_session_code(page, session_code)
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)

                # Vérifier si CnamSignE signale une erreur (ex: code erroné, session inexistante ou expirée)
                page_text = page.locator("body").inner_text()
                if "Aucune session" in page_text or "code saisi est erroné" in page_text:
                    logger.error(f"Erreur CnamSignE pour le code {session_code} : Aucune session d'émargement active trouvée.")
                    self._save_screenshot(page, "code_session_error")
                    return False

                error_el = page.locator(".alert-danger:visible, [id*='lblErreur']:visible, [id*='MessageErreur']:visible, .toast:visible, [role='alert']:visible").first
                if error_el.is_visible():
                    err_msg = error_el.inner_text().strip()
                    if err_msg:
                        logger.error(f"Erreur signalée par CnamSignE pour le code {session_code} : {err_msg}")
                        self._save_screenshot(page, "code_session_error")
                        return False

                # 6. Confirmation de présence et signature
                cb = page.locator("#cbConfirmer, input[id*='cbConfirmer']").first
                if cb.is_visible():
                    self._confirm_presence_and_sign(page, config.CNAM_PIN)
                else:
                    # Si ni case de présence ni message de succès, la session n'est pas ouverte
                    page_text = page.locator("body").inner_text()
                    if "Émargement saisi" not in page_text and "Émargement signé" not in page_text and "déjà émargé" not in page_text.lower():
                        logger.error("Session non accessible ou code inactif.")
                        self._save_screenshot(page, "session_inaccessible")
                        return False

                self._save_screenshot(page, "emargement_final")

                # 7. Vérification stricte du succès
                page_text = page.locator("body").inner_text()
                if "Aucune signature" in page_text or "veuillez dessiner" in page_text:
                    logger.error("Échec de l'émargement : CnamSignE signale qu'aucune signature n'a été détectée.")
                    self._save_screenshot(page, "signature_non_detectee")
                    return False

                if "Émargement saisi" in page_text or "Émargement signé" in page_text or "enregistrée pour cet évènement" in page_text or "déjà émargé" in page_text.lower():
                    logger.info("Émargement terminé avec succès !")
                    return True
                else:
                    logger.error("Échec de l'émargement : aucune confirmation textuelle de signature reçue.")
                    self._save_screenshot(page, "emargement_echec")
                    return False

            except Exception as e:
                logger.error(f"Erreur durant l'émargement : {e}")
                self._save_screenshot(page, "error")
                return False
            finally:
                context.close()
