import html
import os
import re
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from zoneinfo import ZoneInfo

import requests
from dateutil import parser

API_URL = os.environ.get("API_URL", "")
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")
SITE_URL = os.environ.get("SITE_URL", "https://incidenttracker.se").rstrip("/")
STOCKHOLM = ZoneInfo("Europe/Stockholm")

SVENSKA_MANADER = {
    1: "januari", 2: "februari", 3: "mars", 4: "april",
    5: "maj", 6: "juni", 7: "juli", 8: "augusti",
    9: "september", 10: "oktober", 11: "november", 12: "december"
}

# Händelsetyper från polisen.se som är värda att veta om. Matchas mot
# början av typen, så "Rån" täcker även "Rån väpnat" och "Rån försök".
RELEVANTA_TYPER = (
    "inbrott", "rån", "misshandel", "mord", "skottlossning", "detonation",
    "explosion", "våldtäkt", "stöld", "bedrägeri", "olaga hot",
    "olaga frihetsberövande", "vapenlagen", "brand", "bombhot",
    "larm överfall", "skadegörelse", "sedlighetsbrott", "våld/hot",
    "motorfordon, stöld", "rattfylleri", "farligt föremål",
)
# Typer som börjar likadant men mest är brus
IRRELEVANTA_TYPER = ("brand automatlarm", "larm inbrott")

DISTRICT_TO_KOMMUN = {
    "Stockholm": [
        "norrmalm", "vasastan", "östermalm", "kungsholmen", "gamla stan",
        "slussen", "medborgarplatsen", "skanstull", "södermalm", "djurgården",
        "hägersten", "älvsjö", "farsta", "skarpnäck", "bagarmossen",
        "hammarbyhöjden", "björkhagen", "kärrtorp", "vällingby", "hässelby",
        "bromma", "spånga", "tensta", "rinkeby", "kista", "husby", "akalla",
        "årsta", "liljeholmen", "midsommarkransen", "aspudden", "bredäng",
        "skärholmen", "fruängen", "enskede", "hökarängen", "rågsved",
    ],
    "Göteborg": [
        "hisingen", "majorna", "linné", "järntorget", "olivedal", "masthugget",
        "frölunda", "tynnered", "biskopsgården", "backa", "angered",
        "bergsjön", "kortedala", "örgryte", "lundby",
    ],
    "Malmö": [
        "husie", "kirseberg", "limhamn", "fosie", "hyllie", "oxie",
        "rosengård", "möllevången", "triangeln",
    ],
    "Uppsala": ["gottsunda", "sävja", "salabacke", "fålhagen", "gränby"],
    "Linköping": ["skäggetorp", "ryd", "berga", "lambohov", "vidingsjö"],
    "Örebro": ["vivalla", "baronbackarna", "varberga", "oxhagen", "rosta"],
    "Norrköping": ["hageby", "klockaretorpet", "navestad", "ringdansen"],
    "Helsingborg": ["drottninghög", "dalhem", "adolfsberg", "fredriksdal"],
    "Jönköping": ["öxnehaga", "råslätt", "ljungarum"],
    "Lund": ["linero", "klostergården", "norra fäladen"],
    "Umeå": ["ålidhem", "mariehem", "tomtebo", "carlshem"],
    "Gävle": ["andersberg", "sätra", "brynäs"],
    "Sundsvall": ["skönsberg", "bredsand", "nacksta"],
    "Karlstad": ["kronoparken", "våxnäs", "herrhagen"],
    "Halmstad": ["andersberg", "vallås", "oskarström"],
    "Växjö": ["araby", "dalbo"],
    "Borås": ["hässleholmen", "hulta", "norrby"],
    "Eskilstuna": ["fröslunda", "skiftinge", "råbergstorp"],
    "Södertälje": ["ronna", "hovsjö", "geneta", "fornhöjden"],
    "Borlänge": ["tjärna ängar", "jakobsgårdarna", "kvarnsveden"],
    "Västerås": ["bäckby", "skiljebo", "vallby", "hökåsen"],
}


# ---------- Urval ----------

def handelsetyp(event):
    typ = (event.get("type") or "").strip()
    if not typ:
        delar = (event.get("name") or "").split(",")
        typ = delar[1].strip() if len(delar) > 1 else ""
    return typ


def ar_relevant(event):
    typ = handelsetyp(event).lower()
    if typ.startswith(IRRELEVANTA_TYPER):
        return False
    return typ.startswith(RELEVANTA_TYPER)


def ord_finns(ord, text):
    # Hela ord, så att t.ex. kommunen "Ale" inte träffar "talesperson"
    return re.search(rf"(?<!\w){re.escape(ord)}(?!\w)", text) is not None


def matchar_kommun(event, kommun):
    k = kommun.lower()
    plats = (event.get("location") or {}).get("name", "").lower()
    if plats == k or plats == f"{k} kommun":
        return True
    # Rubriken slutar med platsen: "2 oktober 20.40, Inbrott, Malmö"
    rubrik_plats = (event.get("name") or "").split(",")[-1].strip().lower()
    if rubrik_plats == k:
        return True
    stadsdelar = next((v for s, v in DISTRICT_TO_KOMMUN.items() if s.lower() == k), [])
    text = f"{event.get('name', '')} {event.get('summary', '')}".lower()
    return any(ord_finns(sd, text) for sd in stadsdelar)


def hamta_handelser(nu):
    data = requests.get("https://polisen.se/api/events", timeout=30).json()
    handelser = []
    for event in data:
        if not ar_relevant(event):
            continue
        tid = parser.parse(event["datetime"])
        if tid.tzinfo is None:
            tid = tid.replace(tzinfo=timezone.utc)
        if nu - tid > timedelta(hours=24):
            continue
        event["_id"] = str(event.get("id", ""))
        event["_tid"] = tid
        handelser.append(event)
    handelser.sort(key=lambda e: e["_tid"])
    return handelser


def senaste_sammanfattningstid(user, nu):
    """Senaste tidpunkt (bakåt från nu) då användarens sammanfattning skulle gå."""
    timme, minut = map(int, user["digest_time"].split(":"))
    lokal = nu.astimezone(STOCKHOLM)
    mal = lokal.replace(hour=timme, minute=minut, second=0, microsecond=0)
    if mal > lokal:
        mal -= timedelta(days=1)
    return mal


def iso(s):
    if not s:
        return None
    t = parser.isoparse(s)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ---------- Mejl ----------

def tid_text(tid):
    lokal = tid.astimezone(STOCKHOLM)
    return f"{lokal.day} {SVENSKA_MANADER[lokal.month]}, {lokal.strftime('%H:%M')}"


def manage_url(user):
    return f"{SITE_URL}/manage.html?token={user['manage_token']}"


def html_mejl(rubrik, ingress, block_html, user):
    e = html.escape
    return f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"></head>
<body style="margin:0;padding:0;background:#eef1f6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f6;padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0b1220;">
  <tr><td style="background:#0a1020;border-radius:16px 16px 0 0;padding:22px 24px;">
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#4f8cff;box-shadow:0 0 12px #4f8cff;margin-right:8px;"></span>
    <span style="color:#ffffff;font-weight:800;letter-spacing:1.5px;font-size:13px;">INCIDENT TRACKER</span>
    <div style="color:#ffffff;font-size:22px;font-weight:800;margin-top:14px;line-height:1.25;">{e(rubrik)}</div>
    <div style="color:#9fb0cc;font-size:14px;margin-top:6px;">{e(ingress)}</div>
  </td></tr>
  <tr><td style="background:#ffffff;padding:8px 24px 8px;border-radius:0 0 16px 16px;">
    {block_html}
    <p style="font-size:12px;color:#6b7690;line-height:1.6;margin:24px 0 16px;border-top:1px solid #e6e9f0;padding-top:16px;">
      Du får det här för att du bevakar {e(user['kommun'])}.
      <a href="{e(manage_url(user))}" style="color:#2f6bff;">Ändra leveranssätt, tid eller kommun</a> ·
      <a href="{e(manage_url(user))}#avsluta" style="color:#6b7690;">Avsluta</a><br>
      Incident Tracker är inte kopplad till Polismyndigheten. Vid nödsituation, ring 112.
    </p>
  </td></tr>
</table></td></tr></table></body></html>"""


def handelse_block(event):
    e = html.escape
    url = event.get("url") or ""
    if url.startswith("/"):
        url = "https://polisen.se" + url
    plats = (event.get("location") or {}).get("name", "")
    lank = f'<a href="{e(url)}" style="color:#2f6bff;font-size:13px;text-decoration:none;">Läs på polisen.se →</a>' if url else ""
    return f"""
    <div style="padding:18px 0;border-bottom:1px solid #eef0f5;">
      <div style="font-size:12px;color:#6b7690;letter-spacing:.3px;">{e(tid_text(event['_tid']))} · {e(plats)}</div>
      <div style="font-size:17px;font-weight:700;margin:4px 0 6px;">{e(handelsetyp(event))}</div>
      <div style="font-size:15px;line-height:1.55;color:#2a3347;">{e(event.get('summary', ''))}</div>
      <div style="margin-top:8px;">{lank}</div>
    </div>"""


def text_version(rubrik, handelser, user):
    rader = [rubrik, ""]
    for ev in handelser:
        rader += [tid_text(ev["_tid"]), f"{handelsetyp(ev)}, {user['kommun']}", ev.get("summary", ""), ""]
    rader += ["—", f"Ändra eller avsluta: {manage_url(user)}"]
    return "\n".join(rader)


class Mejlare:
    """Återanvänder en SMTP-anslutning för hela körningen."""

    def __init__(self):
        self.sender = os.environ["EMAIL_SENDER"]
        self.password = os.environ["EMAIL_PASSWORD"]
        self.server = None

    def skicka(self, till, amne, text, html_body, user=None):
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("Incident Tracker", self.sender))
        msg["To"] = till
        msg["Subject"] = amne
        if user:
            msg["List-Unsubscribe"] = f"<{manage_url(user)}#avsluta>"
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        if self.server is None:
            self.server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            self.server.starttls()
            self.server.login(self.sender, self.password)
        self.server.sendmail(self.sender, till, msg.as_string())

    def stang(self):
        if self.server:
            try:
                self.server.quit()
            except smtplib.SMTPException:
                pass


def mejl_handelser(user, handelser, sammanfattning):
    kommun = user["kommun"]
    n = len(handelser)
    if sammanfattning:
        dag = datetime.now(STOCKHOLM)
        rubrik = f"Dagens sammanfattning för {kommun}"
        if n:
            ingress = f"{n} {'händelse' if n == 1 else 'händelser'} sedan förra sammanfattningen."
            amne = f"{kommun}: {n} {'händelse' if n == 1 else 'händelser'} · {dag.day} {SVENSKA_MANADER[dag.month]}"
            block = "".join(handelse_block(e) for e in handelser)
        else:
            ingress = "Inga nya händelser rapporterade sedan förra sammanfattningen."
            amne = f"{kommun}: lugnt idag · {dag.day} {SVENSKA_MANADER[dag.month]}"
            block = '<p style="font-size:15px;line-height:1.6;color:#2a3347;padding:18px 0;">Polisen har inte rapporterat något i din kommun som når upp till vår nivå. Det är goda nyheter.</p>'
    else:
        if n == 1:
            rubrik = f"{handelsetyp(handelser[0])} i {kommun}"
            amne = rubrik
        else:
            rubrik = f"{n} nya händelser i {kommun}"
            amne = rubrik
        ingress = "Nyss publicerat av Polisen."
        block = "".join(handelse_block(e) for e in handelser)
    return amne, text_version(rubrik, handelser, user), html_mejl(rubrik, ingress, block, user)


def mejl_valkommen(user):
    if user["delivery_mode"] == "digest":
        hur = f"Du får en sammanfattning varje dag kl. {user['digest_time']}."
    else:
        hur = "Du får ett mejl så fort Polisen publicerar något relevant i din kommun."
    block = f"""<p style="font-size:15px;line-height:1.6;color:#2a3347;padding-top:18px;">Hej {html.escape(user['name'])}!</p>
    <p style="font-size:15px;line-height:1.6;color:#2a3347;">Din bevakning av <b>{html.escape(user['kommun'])}</b> är igång. {hur}</p>
    <p style="padding:6px 0 4px;"><a href="{html.escape(manage_url(user))}" style="display:inline-block;background:#2f6bff;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Hantera bevakning</a></p>"""
    text = f"Hej {user['name']}!\n\nDin bevakning av {user['kommun']} är igång. {hur}\n\nHantera: {manage_url(user)}"
    return "Din bevakning är igång", text, html_mejl("Välkommen", f"Bevakning av {user['kommun']}", block, user)


def mejl_hantera(user):
    block = f"""<p style="font-size:15px;line-height:1.6;color:#2a3347;padding-top:18px;">Här är din personliga länk för att ändra eller avsluta bevakningen. Dela den inte med någon.</p>
    <p style="padding:6px 0 4px;"><a href="{html.escape(manage_url(user))}" style="display:inline-block;background:#2f6bff;color:#fff;text-decoration:none;font-weight:700;padding:12px 18px;border-radius:10px;">Hantera bevakning</a></p>"""
    text = f"Din länk för att hantera bevakningen:\n{manage_url(user)}"
    return "Din länk för att hantera bevakningen", text, html_mejl("Hantera din bevakning", user["kommun"], block, user)


# ---------- Körning ----------

def planera(users, legacy_sent, handelser, nu):
    """Bestämmer vad som ska skickas. Ren funktion, så att den går att testa.
    Returnerar en lista med (user, typ, händelser) där typ är
    'welcome', 'manage', 'live' eller 'digest'."""
    plan = []
    for user in users:
        if not user.get("email") or not user.get("kommun"):
            continue
        if not user.get("welcome_sent"):
            plan.append((user, "welcome", []))
        manage_sent = iso(user.get("manage_sent_at"))
        if user.get("manage_requested") and (not manage_sent or nu - manage_sent > timedelta(minutes=10)):
            plan.append((user, "manage", []))

        skickade = set(user.get("sent_ids") or [])
        egna = [e for e in handelser if e["_id"] not in skickade and matchar_kommun(e, user["kommun"])]
        skapad = iso(user.get("created_at")) or nu

        if user.get("delivery_mode") == "digest":
            mal = senaste_sammanfattningstid(user, nu)
            senast = iso(user.get("last_digest_at"))
            if senast and senast >= mal:
                continue
            fran = max(x for x in (senast, skapad, nu - timedelta(hours=24)) if x)
            plan.append((user, "digest", [e for e in egna if e["_tid"] > fran]))
        else:
            # Nya användare får inte en hög med gamla händelser direkt
            fran = max(skapad - timedelta(hours=1), nu - timedelta(hours=24))
            nya = [e for e in egna if e["_id"] not in legacy_sent and e["_tid"] >= fran]
            if nya:
                plan.append((user, "live", nya))
    return plan


def main():
    if not API_URL or not WORKER_TOKEN:
        raise SystemExit("API_URL och WORKER_TOKEN måste vara satta.")
    headers = {"Authorization": f"Bearer {WORKER_TOKEN}"}

    # Väck servern (Render sover på gratisnivån)
    for _ in range(6):
        try:
            if requests.get(f"{API_URL}/", timeout=30).ok:
                break
        except requests.RequestException:
            pass
        time.sleep(10)

    resp = requests.get(f"{API_URL}/api/worker/users", headers=headers, timeout=60)
    resp.raise_for_status()
    state = resp.json()

    nu = datetime.now(timezone.utc)
    handelser = hamta_handelser(nu)
    plan = planera(state["users"], set(state["legacy_sent"]), handelser, nu)

    rapport = {"sent": [], "digested": [], "welcomed": [], "manage_sent": []}
    mejlare = Mejlare()
    try:
        for user, typ, evs in plan:
            if typ == "welcome":
                innehall = mejl_valkommen(user)
            elif typ == "manage":
                innehall = mejl_hantera(user)
            else:
                innehall = mejl_handelser(user, evs, sammanfattning=(typ == "digest"))
            try:
                mejlare.skicka(user["email"], *innehall, user=user)
            except Exception as exc:
                print(f"Kunde inte skicka {typ} till användare {user['id']}: {exc}")
                mejlare.server = None
                continue
            print(f"{typ} skickat till användare {user['id']} ({user['kommun']}, {len(evs)} händelser)")
            if evs:
                rapport["sent"].append({"user_id": user["id"], "event_ids": [e["_id"] for e in evs]})
            key = {"digest": "digested", "welcome": "welcomed", "manage": "manage_sent"}.get(typ)
            if key:
                rapport[key].append(user["id"])
    finally:
        mejlare.stang()
        requests.post(f"{API_URL}/api/worker/report", json=rapport, headers=headers, timeout=60).raise_for_status()

    print("Klart!")


if __name__ == "__main__":
    main()
