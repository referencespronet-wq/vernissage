"""
Newsletter hebdomadaire automatique pour Vernissage.
Ce script :
  1. Récupère les mêmes flux RSS que le site (actualités d'art vérifiées)
  2. Choisit les 3 articles les plus récents avec une vraie image
  3. Crée et envoie un email via l'API Buttondown

Il est lancé automatiquement chaque semaine par GitHub Actions —
aucune action humaine n'est nécessaire une fois configuré.
"""
import os
import re
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

FEEDS = [
    "https://news.artnet.com/feed",
    "https://hyperallergic.com/feed/",
    "https://www.theartnewspaper.com/rss/news",
    "https://www.artforum.com/feed/news/",
    "https://artreview.com/feed/",
]

BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY")
if not BUTTONDOWN_API_KEY:
    print("Erreur : la variable BUTTONDOWN_API_KEY n'est pas définie (secret GitHub manquant).")
    sys.exit(1)


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def extract_image(item_xml):
    enclosure = item_xml.find("enclosure")
    if enclosure is not None and "url" in enclosure.attrib:
        return enclosure.attrib["url"]
    ns = {"media": "http://search.yahoo.com/mrss/"}
    media = item_xml.find("media:content", ns)
    if media is not None and "url" in media.attrib:
        return media.attrib["url"]
    desc = item_xml.findtext("description") or ""
    match = re.search(r'<img[^>]+src="([^">]+)"', desc)
    return match.group(1) if match else None


def fetch_feed_items(url):
    items = []
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item")[:6]:
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = strip_html(item.findtext("description") or "")[:200]
            pub_date = item.findtext("pubDate") or ""
            img = extract_image(item)
            if img:
                items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "desc": desc,
                    "img": img,
                    "pub_date": pub_date,
                })
    except Exception as e:
        print(f"Flux ignoré ({url}) : {e}")
    return items


def pick_top_three(all_items):
    def parse_date(item):
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                return datetime.strptime(item["pub_date"], fmt)
            except Exception:
                continue
        return datetime.min
    all_items.sort(key=parse_date, reverse=True)
    return all_items[:3]


def build_email_html(articles):
    blocks = []
    for art in articles:
        blocks.append(f"""
<table style="margin-bottom:32px;">
  <tr><td>
    <img src="{art['img']}" width="560" style="max-width:100%; border-radius:4px;" alt="">
  </td></tr>
  <tr><td style="padding-top:14px;">
    <h2 style="font-size:20px; margin:0 0 8px;">
      <a href="{art['link']}" style="color:#1c1812; text-decoration:none;">{art['title']}</a>
    </h2>
    <p style="color:#5a5448; font-size:15px; line-height:1.6; margin:0;">{art['desc']}…</p>
    <p style="margin-top:10px;"><a href="{art['link']}" style="color:#a8731f; font-size:13px;">Lire l'article complet →</a></p>
  </td></tr>
</table>""")
    return f"""
<div style="font-family:Georgia, serif; max-width:600px; margin:0 auto;">
  <h1 style="font-size:26px; border-bottom:2px solid #d6a23c; padding-bottom:12px;">Vernissage — Le récap de la semaine</h1>
  <p style="color:#5a5448; font-size:14px;">Les 3 actualités d'art qui ont compté cette semaine.</p>
  {''.join(blocks)}
  <p style="font-size:12px; color:#999; margin-top:40px;">Vous recevez cet email car vous êtes inscrit à la newsletter Vernissage.</p>
</div>"""


def send_email(subject, html_body):
    url = "https://api.buttondown.com/v1/emails"
    headers = {"Authorization": f"Token {BUTTONDOWN_API_KEY}"}
    data = {"subject": subject, "body": html_body, "status": "about_to_send"}
    resp = requests.post(url, headers=headers, json=data, timeout=20)
    print("Statut Buttondown :", resp.status_code)
    print(resp.text)
    resp.raise_for_status()


def main():
    all_items = []
    for feed_url in FEEDS:
        all_items.extend(fetch_feed_items(feed_url))

    if len(all_items) < 3:
        print("Pas assez d'articles récupérés, envoi annulé.")
        sys.exit(1)

    top3 = pick_top_three(all_items)
    subject = f"Vernissage — Le récap de la semaine ({datetime.now().strftime('%d/%m/%Y')})"
    html_body = build_email_html(top3)
    send_email(subject, html_body)
    print("Newsletter envoyée avec succès.")


if __name__ == "__main__":
    main()
