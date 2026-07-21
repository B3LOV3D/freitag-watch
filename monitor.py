"""
FREITAG F11 Lassie - Black Watch (v2 avec photo)

Scrape la page produit freitag.ch avec un vrai navigateur (Playwright),
repere les exemplaires tagges "BLACK" par FREITAG, et envoie une
notification (via ntfy.sh) CONTENANT LA PHOTO du sac, pour verification
visuelle rapide (le tag "BLACK" de FREITAG est une categorie interne,
pas une garantie que le sac est visuellement 100% noir).

Variables d'environnement:
    NTFY_TOPIC   -> nom du topic ntfy.sh (obligatoire)
"""

import os
import re
import json
import sys
import requests
from playwright.sync_api import sync_playwright

PRODUCT_URL = "https://freitag.ch/fr_FR/products/f11-lassie"
SEEN_FILE = "seen_refs.json"
TARGET_COLOR = "BLACK"

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Motif present dans le texte alternatif de chaque vignette. Selon la
# langue du site ca peut etre "F11 LASSIE MESSENGER ..." (anglais) ou
# "F11 LASSIE SACS MESSENGER ..." (francais) - le nom de la couleur, lui,
# reste toujours en anglais (BLACK, GREEN, etc.)
VARIANT_PATTERN = re.compile(r"F11 LASSIE(?: SACS)? MESSENGER (\w+) (\d{6,})")


def fetch_variants_with_images() -> dict:
    """
    Ouvre la page avec un navigateur headless (pour que les images qui se
    chargent en JavaScript apparaissent), fait defiler la page pour
    declencher le chargement des vignettes, puis recupere pour chaque
    exemplaire: sa couleur, sa reference, et l'URL de sa photo.

    Retourne un dict {ref: {"color": ..., "image": ...}}
    """
    variants = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1280, "height": 2000})
        page.goto(PRODUCT_URL, wait_until="networkidle", timeout=45000)

        # Fait defiler progressivement la page pour declencher le
        # chargement "lazy" des vignettes (sinon certaines images restent
        # vides tant qu'on ne les a pas fait apparaitre a l'ecran).
        previous_height = 0
        for _ in range(25):
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(250)
            height = page.evaluate("document.body.scrollHeight")
            if height == previous_height:
                break
            previous_height = height

        page.wait_for_timeout(1000)

        images = page.query_selector_all("img[alt*='F11 LASSIE']")
        for img in images:
            alt = img.get_attribute("alt") or ""
            src = img.get_attribute("src") or ""
            match = VARIANT_PATTERN.search(alt)
            if not match or not src:
                continue

            color, ref = match.group(1).upper(), match.group(2)
            if src.startswith("/"):
                src = "https://freitag.ch" + src

            variants[ref] = {"color": color, "image": src}

        browser.close()

    if not variants:
        print("ATTENTION: aucune variante trouvee, le format de la page a peut-etre change.")

    return variants


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def notify(ref: str, image_url: str) -> None:
    product_url = f"{PRODUCT_URL}?v={ref}"
    message = f"Reference: {ref}\n{product_url}"

    if not NTFY_TOPIC:
        print(f"[SANS NOTIF - NTFY_TOPIC absent] Nouveau F11 Lassie noir: {ref} - photo: {image_url}")
        return

    headers = {
        "Title": "FREITAG F11 Lassie - possible BLACK",
        "Priority": "high",
        "Tags": "dark_sunglasses",
        "Click": product_url,
    }
    if image_url:
        headers["Attach"] = image_url

    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        print(f"Notification envoyee pour {ref} (photo: {'oui' if image_url else 'non'})")
    except Exception as e:
        print(f"Echec de la notification pour {ref}: {e}")


def main() -> None:
    variants = fetch_variants_with_images()
    seen = load_seen()

    black_variants = {ref: v for ref, v in variants.items() if v["color"] == TARGET_COLOR}
    new_black_refs = set(black_variants.keys()) - seen

    print(f"{len(variants)} exemplaires trouves au total, {len(black_variants)} tagges BLACK par FREITAG.")

    for ref in sorted(new_black_refs):
        notify(ref, black_variants[ref]["image"])

    save_seen(seen | set(black_variants.keys()))

    if not new_black_refs:
        print("Aucun nouveau F11 Lassie tagge BLACK pour l'instant.")


if __name__ == "__main__":
    sys.exit(main() or 0)
