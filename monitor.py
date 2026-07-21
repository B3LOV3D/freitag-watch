"""
FREITAG F11 Lassie - Black Watch
Scrape la page produit freitag.ch et notifie (via ntfy.sh) dès qu'un
nouvel exemplaire BLACK apparaît en stock.

Usage:
    python monitor.py

Variables d'environnement:
    NTFY_TOPIC   -> nom du topic ntfy.sh (obligatoire, choisis un nom aléatoire
                    et secret, ex: "freitag-lassie-black-8x2kq9")
"""

import os
import re
import json
import sys
import requests

PRODUCT_URL = "https://freitag.ch/en_US/products/f11-lassie"
SEEN_FILE = "seen_refs.json"
TARGET_COLOR = "BLACK"

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Le nom de chaque variante contient le motif "F11 LASSIE MESSENGER <COLOR> <REF>"
VARIANT_PATTERN = re.compile(r"F11 LASSIE MESSENGER (\w+) (\d{6,})")


def fetch_variants() -> dict:
    """Retourne un dict {ref: couleur} de tous les exemplaires actuellement listés."""
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    variants = {}
    for color, ref in VARIANT_PATTERN.findall(resp.text):
        variants[ref] = color.upper()

    if not variants:
        # Le site a peut-être changé de structure -> à surveiller manuellement
        print("ATTENTION: aucune variante trouvée, le format de la page a peut-être changé.")

    return variants


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def notify(ref: str) -> None:
    if not NTFY_TOPIC:
        print(f"[SANS NOTIF - NTFY_TOPIC absent] Nouveau F11 Lassie noir: {ref}")
        return

    url = f"{PRODUCT_URL}?v={ref}"
    message = f"F11 Lassie NOIR disponible !\nRéf: {ref}\n{url}"

    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "FREITAG F11 Lassie - BLACK dispo",
                "Priority": "high",
                "Tags": "dark_sunglasses",
            },
            timeout=10,
        )
        print(f"Notification envoyée pour {ref}")
    except Exception as e:
        print(f"Echec de la notification pour {ref}: {e}")


def main() -> None:
    variants = fetch_variants()
    seen = load_seen()

    black_refs = {ref for ref, color in variants.items() if color == TARGET_COLOR}
    new_black = black_refs - seen

    print(f"{len(variants)} exemplaires trouvés au total, {len(black_refs)} en noir.")

    for ref in sorted(new_black):
        notify(ref)

    # On mémorise tous les noirs vus (pour ne pas re-notifier les mêmes)
    save_seen(seen | black_refs)

    if not new_black:
        print("Aucun nouveau F11 Lassie noir pour l'instant.")


if __name__ == "__main__":
    sys.exit(main() or 0)
