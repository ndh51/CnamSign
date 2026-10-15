import logging
import os
import re
import time
from datetime import datetime
from typing import Optional, Set
from playwright.sync_api import sync_playwright, Page

import config

logger = logging.getLogger(__name__)

CODE_PATTERNS = [
    re.compile(r"code\s+de\s+session\s*(?:à\s+indiquer\s+)?(?:pour\s+émarger[^\d:]*)?:\s*(\d{6})", re.IGNORECASE),
    re.compile(r"code\s+de\s+session[^\d:]*:\s*(\d{6})", re.IGNORECASE),
    re.compile(r"émarger[^\d:]*:\s*(\d{6})", re.IGNORECASE),
    re.compile(r"(\d{6})"),
]

BROWSER_PROFILE_DIR = os.path.abspath("browser_profile")
PROCESSED_CODES_FILE = "processed_codes.txt"

class MailWatcher:
    def __init__(self):
        self.processed_codes: Set[str] = self._load_processed_codes()
        self.last_detected_date: Optional[str] = None

    def _load_processed_codes(self) -> Set[str]:
        if os.path.exists(PROCESSED_CODES_FILE):
            try:
                with open(PROCESSED_CODES_FILE, "r", encoding="utf-8") as f:
                    return set(line.strip() for line in f if line.strip())
            except Exception:
                pass
        return set()

    @staticmethod
    def extract_date(text: str) -> str:
        """Extrait la date du texte si présente (ex: 15/10/2026), sinon retourne la date du jour (YYYY-MM-DD)."""
        m = re.search(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b", text)
        if m:
            day, month, year = m.groups()
            return f"{year}-{month}-{day}"
        return datetime.now().strftime("%Y-%m-%d")

    def is_processed(self, code: str, date_str: str) -> bool:
        """Vérifie si la combinaison date+code (ou le code seul) a déjà été traitée."""
        entry = f"{date_str}:{code}"
        return entry in self.processed_codes or code in self.processed_codes

    def mark_as_processed(self, code: str, date_str: Optional[str] = None):
        """Enregistre le couple date+code dans l'historique."""
        d = date_str or datetime.now().strftime("%Y-%m-%d")
        entry = f"{d}:{code}"
        self.processed_codes.add(entry)
        try:
            with open(PROCESSED_CODES_FILE, "a", encoding="utf-8") as f:
                f.write(f"{entry}\n")
        except Exception:
            pass

    def _login_outlook(self, page: Page):
        """Authentifie la session sur Outlook Web via Microsoft et Le Cnam SSO."""
        logger.info("Session expirée ou absente : authentification Microsoft / Le Cnam en cours...")
        email_field = page.wait_for_selector('input[type="email"], input[name="loginfmt"]', timeout=30000)
        email_field.fill(config.EMAIL)
        page.locator('input[type="submit"], #idSIButton9').first.click()

        logger.info("Attente de la redirection vers Le Cnam SSO...")
        page.wait_for_url(lambda u: "idp.lecnam.net" in u, timeout=30000)

        logger.info("Saisie des identifiants SSO Le Cnam...")
        username_selectors = ['input[name="j_username"]', '#username', 'input[type="text"]']
        password_selectors = ['input[name="j_password"]', '#password', 'input[type="password"]']
        submit_selectors = ['button[type="submit"]', 'input[type="submit"]', 'button[name="_eventId_proceed"]']

        for sel in username_selectors:
            if page.locator(sel).first.is_visible():
                page.locator(sel).first.fill(config.EMAIL)
                break

        for sel in password_selectors:
            if page.locator(sel).first.is_visible():
                page.locator(sel).first.fill(config.PASSWORD)
                break

        for sel in submit_selectors:
            if page.locator(sel).first.is_visible():
                page.locator(sel).first.click()
                break

        logger.info("Connexion SSO envoyée. Attente de la validation Microsoft...")
        try:
            stay_signed_btn = page.wait_for_selector('input[value="Oui"], #idSIButton9, button:has-text("Oui")', timeout=20000)
            if stay_signed_btn:
                stay_signed_btn.click()
        except Exception:
            pass

        logger.info("Attente du chargement d'Outlook Web...")
        page.wait_for_url(lambda u: "outlook.office.com/mail" in u or "outlook.office365.com/mail" in u, timeout=60000)
        time.sleep(4)
        logger.info("Session Outlook active et enregistrée dans le profil persistant !")

    def check_for_code(self, auto_mark: bool = False, max_mails_to_check: int = 5) -> Optional[str]:
        """Vérifie les derniers messages du dossier Emargements et extrait le dernier code reçu."""
        with sync_playwright() as p:
            # Utilisation d'un profil navigateur persistant pour conserver cache, cookies et tokens
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=config.HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.pages[0] if context.pages else context.new_page()

            try:
                page.goto("https://outlook.office.com/mail/", timeout=60000)

                # Si le cache a expiré ou première visite, on s'authentifie
                needs_login = False
                try:
                    login_field = page.wait_for_selector('input[type="email"], input[name="loginfmt"]', timeout=5000)
                    if login_field:
                        needs_login = True
                except Exception:
                    pass

                if needs_login:
                    self._login_outlook(page)

                # Accès direct au dossier d'émargement
                folder_name = config.OUTLOOK_FOLDER
                folder_sel = f'span[title="{folder_name}"], div[title="{folder_name}"], span:text-is("{folder_name}"), [aria-label*="{folder_name}"]'
                folder = page.locator(folder_sel).first
                if folder.is_visible():
                    folder.click()
                    time.sleep(2)

                # Vérifier les derniers mails de la liste
                mails = page.locator('div[role="listbox"] div[role="option"]').all()[:max_mails_to_check]
                if not mails:
                    logger.debug("Aucun mail dans le dossier Emargements.")
                    return None

                for idx, mail_item in enumerate(mails):
                    try:
                        if not mail_item.is_visible():
                            continue
                        mail_item.click()
                        time.sleep(1)

                        # Extraire le corps du message
                        body_el = page.locator('div[aria-label="Corps du message"], div[role="document"], .ReadingPaneContainer').first
                        if not body_el.is_visible():
                            continue

                        body_text = body_el.inner_text()
                        email_date = self.extract_date(body_text)

                        for pattern in CODE_PATTERNS:
                            match = pattern.search(body_text)
                            if match:
                                code = match.group(1)
                                if not self.is_processed(code, email_date):
                                    logger.info(f"Nouveau code d'émargement détecté pour le {email_date} : {code} (mail #{idx+1})")
                                    self.last_detected_date = email_date
                                    if auto_mark:
                                        self.mark_as_processed(code, email_date)
                                    return code
                    except Exception as err:
                        logger.debug(f"Erreur lors de la lecture du mail #{idx+1} : {err}")
                        continue

                return None

            except Exception as e:
                logger.error(f"Erreur lors de la vérification des mails Outlook Web : {e}")
                return None
            finally:
                context.close()
