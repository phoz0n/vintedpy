from typing import Any, Dict, List
from dataset import Database
import hikari
from lightbulb import BotApp
from datetime import datetime
from langdetect import detect


from api import search
from loguru import logger as log

language_flags = {
    "fr": "🇫🇷",
    "it": "🇮🇹",
    "nl": "🇳🇱",
    "en": "🇬🇧",
    "ja": "🇯🇵"
}


def scrape(db: Database, params: Dict[str, str]) -> List:
    """
    Scrape items and filter by new results

    Args:
        params (Dict[str, str]): Row of database

    Returns:
        List: list of new items
    """
    response = search(params["url"], {"per_page": 20})

    # Remove promoted items
    try:
        items = [item for item in response["items"] if item["promoted"] == False]
    except KeyError:
        return []

    # Skip null
    if not len(items):
        return []

    # Ignore items for first sync
    if params["last_sync"] == -1:
        return [items[0]]

    table = db["items"]

    # Filter date and by existing
    results = []
    for item in items:
        try:
            timestamp = item["photo"]["high_resolution"]["timestamp"]
        except:
            log.warning("Empty timestamp found")
            print(item)
            continue

        if timestamp > params["last_sync"] and "id" in item:
            results.append(item)

    for item in results:
        saved = table.find_one(id=item["id"])
        log.debug(saved)

        if saved:
            # Already known
            log.debug("Removing result {id}, already known", id=item["id"])
            results.remove(item)
        else:
            log.debug("Inserting item #{id}", id=item["id"])
            table.insert({"id": item["id"]})

    return results


def generate_embed(item: Any, sub_id: int) -> hikari.Embed:
    embed = hikari.Embed()
    embed.title = item["title"] or "Unknown"
    embed.url = item["url"] or "Unknown"
    embed.set_image(item["photo"]["url"] or "Unknown")
    embed.color = hikari.Color(0x09B1BA)

    # Utiliser le champ "title" pour la détection de la langue
    detected_language = "unknown"

    try:
        detected_language = detect(item["title"])
    except:
        pass

    # Ajouter le drapeau correspondant à la langue détectée
    if detected_language in language_flags:
        flag_emoji = language_flags[detected_language]
        detected_language_text = f"{flag_emoji} ({detected_language})"
    else:
        detected_language_text = "Unknown"

    embed.add_field("Language", detected_language_text, inline=True)

    embed.add_field("Price", str(item["price"]) or "-1" + " €", inline=True)

    embed.set_footer(f'Published on {datetime.now().strftime("%d/%m/%Y, %H:%M:%S") or "unknown"} • Subscription #{str(sub_id)}')

    embed.set_author(
        name="Posted by " + item["user"]["login"] or "unknown",
        url=item["user"]["profile_url"] or "unknown",
    )

    return embed