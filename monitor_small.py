"""FREITAG F40 Jamie + F41 Hawaii Five-0 - Black Watch"""

import os
import re
import json
import sys
import requests
from playwright.sync_api import sync_playwright

SEEN_FILE = "seen_refs_small.json"
TARGET_COLOR = "BLACK"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_SMALL")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MODELS = [
    {
        "key": "f40",
        "label": "F40 Jamie",
        "url": "https://freitag.ch/fr_FR/products/f40-jamie",
        "alt_keyword": "F40 JAMIE",
        "pattern": re.compile(r"F40 JAMIE\b.*?([A-Za-z]+)\s+(\d{6,})"),
    },
    {
        "key": "f41",
        "label": "F41 Hawaii Five-0",
        "url": "https://freitag.ch/fr_FR/products/f41-hawaii-five-0",
        "alt_keyword": "F41 HAWAII",
        "pattern": re.compile(r"F41 HAWAII FIVE[\s\-]?[0O]\b.*?([A-Za-z]+)\s+(\d{6,})"),
    },
]

FALLBACK_PATTERN = re.compile(r"([A-Za-z]+)\s+(\d{6,})\s*$")


def fetch_variants(page, model) -> dict:
    """Ouvre la page produit et recupere couleur + reference + photo."""
    variants = {}
    debug_alts = []

    page.goto(model["url"], wait_until="networkidle", timeout=45000)

    previous_height = 0
    for _ in range(25):
        page.mouse.wheel(0, 2200)
        page.wait_for_timeout(250)
        height = page.evaluate("document.body.scrollHeight")
        if height == previous_height:
            break
        previous_height = height

    page.wait_for_timeout(1000)

    for img in page.query_selector_all(f"img[alt*='{model['alt_keyword']}']"):
        alt = img.get_attribute("alt") or ""
        src = img.get_attribute("src") or ""
        if len(debug_alts) < 5 and alt:
            debug_alts.append(alt)

        match = model["pattern"].search(alt) or FALLBACK_PATTERN.search(alt)
        if not match or not src:
            continue

        color, ref = match.group(1).upper(), match.group(2)
        if src.startswith("/"):
            src = "https://freitag.ch" + src

        variants[ref] = {"color": color, "image": src}

    if not variants:
        print(f"ATTENTION [{model['label']}]: aucune variante trouvee.")
        print("Exemples de textes alternatifs vus:", debug_alts)

    return variants


def load_seen() -> dict:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen(seen: dict) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2, sort_keys=True)


def notify(model, ref: str, image_url: str) -> None:
    product_url = f"{model['url']}?v={ref}"
    message = f"{model['label']}\nReference: {ref}\n{product_url}"

    if not NTFY_TOPIC:
        print(f"[SANS NOTIF - NTFY_TOPIC_SMALL absent] {model['label']} noir: {ref}")
        return

    headers = {
        "Title": f"FREITAG {model['label']} - possible BLACK",
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
        print(f"Notification envoyee: {model['label']} {ref}")
    except Exception as e:
        print(f"Echec de la notification pour {ref}: {e}")


def main() -> None:
    seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1280, "height": 2000})

        for model in MODELS:
            variants = fetch_variants(page, model)
            black = {r: v for r, v in variants.items() if v["color"] == TARGET_COLOR}

            already = set(seen.get(model["key"], []))
            new_refs = set(black.keys()) - already

            print(f"[{model['label']}] {len(variants)} exemplaires, {len(black)} tagges BLACK, {len(new_refs)} nouveaux.")

            for ref in sorted(new_refs):
                notify(model, ref, black[ref]["image"])

            seen[model["key"]] = sorted(already | set(black.keys()))

        browser.close()

    save_seen(seen)


if __name__ == "__main__":
    sys.exit(main() or 0)