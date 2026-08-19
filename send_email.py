import smtplib
import requests
import json
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dateutil import parser
from zoneinfo import ZoneInfo

API_URL = os.environ["API_URL"]  # t.ex. https://din-app.onrender.com

SVENSKA_MANADER = {
    1: "januari", 2: "februari", 3: "mars", 4: "april",
    5: "maj", 6: "juni", 7: "juli", 8: "augusti",
    9: "september", 10: "oktober", 11: "november", 12: "december"
}

# Kända stadsdelar mappade till sin kommun. Polisen skriver ofta bara
# stadsdelen i location.name, inte kommunnamnet — utan denna mappning
# missas sådana händelser helt vid kommun-matchning.
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


def hitta_kommun_for_handelse(full_text, valda_kommuner):
    """Matcha en händelse mot en användares kommun, antingen via
    kommunnamn direkt i texten eller via känd stadsdel."""
    for kommun in valda_kommuner:
        if kommun.lower() in full_text:
            return kommun
        for stad, stadsdelar in DISTRICT_TO_KOMMUN.items():
            if kommun.lower() == stad.lower() and any(sd in full_text for sd in stadsdelar):
                return kommun
    return None


SKICKADE_FIL = "skickade.json"

if os.path.exists(SKICKADE_FIL):
    with open(SKICKADE_FIL, "r") as f:
        skickade = set(json.load(f))
else:
    skickade = set()

nu = datetime.now(timezone.utc)

polisapi = requests.get("https://polisen.se/api/events")
polisdata = polisapi.json()

# Filtrera relevanta händelser (samma logik som innan, men matcha på kommun
# istället för län/mikroort — se separat kommun-lookup)
relevanta_events = []

for event in polisdata:
    namn = event.get("name", "")
    summary = event.get("summary", "")
    plats = event["location"]["name"]
    full_text = f"{namn} {summary} {plats}".lower()

    brott = any(x in full_text for x in [
        "misshandel", "rån", "stöld", "inbrott", "bedrägeri",
        "narkotika", "våld", "skottlossning", "skjutning", "mord",
        "rånförsök", "vapen", "rånare", "personrån", "våldtäkt",
        "mordbrand", "explosion", "sprängning", "kniv", "beväpnad",
        "rånförberedelse", "rattfylleri"
    ])
    if not brott:
        continue

    irrelevant = any(x in full_text for x in [
        "övning", "övar", "träning", "information",
        "samverkan", "presstalesperson", "kontroll"
    ])
    if irrelevant:
        continue

    event_tid = parser.parse(event["datetime"])
    if event_tid.tzinfo is None:
        event_tid = event_tid.replace(tzinfo=timezone.utc)

    alder_timmar = (nu - event_tid).total_seconds() / 3600
    if alder_timmar > 24:
        continue

    event_id = str(event.get("id", ""))
    if event_id in skickade:
        continue

    event["_full_text"] = full_text
    event["_tid"] = event_tid
    relevanta_events.append(event)

# HÄMTA ANVÄNDARE FRÅN EGEN API (Flask + SQLite)
import time
requests.get(f"{API_URL}/")  # Väck servern
time.sleep(15)               # Vänta tills den är vaken
resp = requests.get(f"{API_URL}/api/users")
resp.raise_for_status()
anvandare = resp.json()

email_sender = os.environ["EMAIL_SENDER"]
email_password = os.environ["EMAIL_PASSWORD"]

nya_skickade = set()

for user in anvandare:
    mottagare_email = user.get("email", "")
    kommun = user.get("kommun", "")

    if not mottagare_email or not kommun:
        continue

    events_for_kommun = [
        e for e in relevanta_events
        if hitta_kommun_for_handelse(e["_full_text"], [kommun]) == kommun
    ]
    if not events_for_kommun:
        continue

    email_text = ""
    for event in events_for_kommun:
        namn = event.get("name", "")
        # Brottstyp står som andra delen i namn-fältet, ex:
        # "3 juli 02:28, Rattfylleri, Botkyrka" -> "Rattfylleri"
        delar = namn.split(",")
        brottstyp = delar[1].strip().capitalize() if len(delar) > 1 else ""
        summary = event.get("summary", "")

        # Enda källan till tid — Polisens datetime-fält, konverterat till
        # svensk lokal tid och formaterat på svenska. Ingen egen parsning
        # av namn-strängen (det var källan till dubbla/felaktiga tider).
        lokal_tid = event["_tid"].astimezone(ZoneInfo("Europe/Stockholm"))
        manad = SVENSKA_MANADER[lokal_tid.month]
        tid_str = f"{lokal_tid.day} {manad}, {lokal_tid.strftime('%H:%M')}"

        email_text += f"{tid_str}\n"
        email_text += f"{brottstyp}, {kommun.capitalize()}\n"
        email_text += f"{summary}\n\n"

        nya_skickade.add(str(event.get("id", "")))

    email_text += "Incident Tracker — Real-time alerts"

    try:
        message = MIMEMultipart()
        message["From"] = email_sender
        message["To"] = mottagare_email
        message["Subject"] = f"{len(events_for_kommun)} nya incidenter i {kommun.capitalize()}"
        message.attach(MIMEText(email_text, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email_sender, email_password)
        server.sendmail(email_sender, mottagare_email, message.as_string())
        server.quit()

        print(f"Mail skickat till {mottagare_email} ({kommun})")
    except Exception as e:
        print(f"Kunde inte skicka till {mottagare_email}: {e}")

skickade.update(nya_skickade)

with open(SKICKADE_FIL, "w") as f:
    json.dump(list(skickade), f)

print("Klart!")