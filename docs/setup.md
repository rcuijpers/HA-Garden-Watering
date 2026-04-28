# Installatiegids

## Wat heb je nodig?

- **Home Assistant 2024.1** of nieuwer
- **Een waterklep** die HA kan aansturen — bijvoorbeeld een slimme kraan, solenoid of een schakelaar die een pomp bedient. In HA is dit zichtbaar als een `switch.*` of `valve.*` entiteit.
- **Een weerintegratie** in HA, bijvoorbeeld Met.no (gratis, geen API-sleutel nodig) of OpenWeatherMap. Die gebruik je al als je het weerbericht op je dashboard ziet.

---

## Installatie via HACS

1. Klik op de knop in de README, of ga handmatig naar HACS → Integraties → ⋮ → **Aangepaste repositories**
2. Voeg `https://github.com/rcuijpers/HA-Garden-Watering` toe als type **Integratie**
3. Installeer **Garden Irrigation** en herstart Home Assistant
4. Ga naar **Instellingen → Apparaten & Diensten → Integratie toevoegen** en zoek op **Garden Irrigation**

---

## De setup-wizard stap voor stap

### Stap 1 — Hoofdklep

Dit is de klep die het water aan- en uitzet voor je hele tuin. Alle andere zones gaan pas open als deze klep open is.

**Wat selecteer je?** De `switch.*` of `valve.*` entiteit die je hoofdwatertoevoer bestuurt. Als je maar één klep hebt, kies je die hier. Heb je een aparte klep per zone maar geen hoofdklep? Maak dan één van de zonesventielen je "hoofdklep" en laat de rest leeg bij de zones.

---

### Stap 2 — Bewateringszones

Een zone is een apart beregend gebied — bijvoorbeeld je moestuin, je borders of je gazon. Elke zone kan zijn eigen schema en duur hebben.

**Aantal zones**: Hoeveel aparte gebieden wil je kunnen aansturen? Je kunt er 1 tot 8 instellen. Je kunt later via de opties niets toevoegen, dus tel ze even op voorhand.

Per zone stel je in:

| Instelling | Wat het doet |
|-----------|-------------|
| **Naam** | Vrije tekst, verschijnt op het dashboard. Bijv. "Moestuin" of "Gazon achter". |
| **Type** | Kies `drip` (druppelirrigatie), `sprinkler` (sproeier) of `other`. Dit beïnvloedt hoe lang de integratie aanraadt te sproeien — sproeiers krijgen een lagere maximum-duur om oppervlakte-afvoer te voorkomen. |
| **Zone-klep** | Heb je per zone een aparte solenoid of schakelaar? Kies die hier. Optioneel — als je maar één klep hebt voor alles, laat je dit leeg. |
| **Standaard duur** | Hoeveel minuten sproeit deze zone normaal? Dit is de basiswaarde — de integratie past deze automatisch aan op basis van droogte en temperatuur. |
| **Actief** | Vink je dit uit, dan wordt de zone overgeslagen zonder dat je hem hoeft te verwijderen. Handig in de winter. |

---

### Stap 3 — Weerdata

De integratie gebruikt weerdata om te bepalen of bewateren nodig is en hoe lang. Ze kijkt naar de neerslagverwachting voor de komende 24 uur en de huidige temperatuur.

| Instelling | Wat het doet |
|-----------|-------------|
| **Weergerelateerde entiteit** | Je standaard HA-weersensor, bijv. `weather.home`. Dit is de primaire bron voor zowel regen als temperatuur. |
| **Neerslagsensor (optioneel)** | Heb je een eigen regenmeter buiten staan? Die kun je hier koppelen. De waarde hiervan heeft voorrang boven de weersensor. |
| **Temperatuursensor (optioneel)** | Heb je een eigen buitenthermometer? Die kun je hier koppelen voor nauwkeurigere metingen. |
| **Regendrempel** | Hoeveel mm verwachte neerslag is genoeg om bewatering over te slaan? Standaard 5 mm. Bij 1 mm lichte motregen wil je misschien nog steeds sproeien — zet de drempel dan hoger. |
| **Temperatuurdrempel** | Boven welke temperatuur is bewateren extra urgent? Standaard 20°C. Bij mediterraan klimaat wil je dit misschien op 25°C zetten. |

---

### Stap 4 — Flowmeter (optioneel)

Een flowmeter meet hoeveel liter er door je leidingen stroomt. **Heb je geen flowmeter? Sla deze stap gewoon over** — alles werkt ook zonder.

Met een flowmeter krijg je er wel dit bij:

- **Verbruiksmeting**: hoeveel liter je vandaag en deze week hebt gebruikt
- **Lekdetectie**: de integratie controleert regelmatig of er water stroomt terwijl er niets zou moeten stromen, en stuurt je dan een melding

| Instelling | Wat het doet |
|-----------|-------------|
| **Flowsensor** | De HA-entiteit van je flowmeter. |
| **Idle drempel** | Hoeveel L/min is "normaal stilstaand"? Leidingen lekken soms een klein beetje — zet dit net boven dat niveau. Standaard 0,5 L/min. |
| **Lekdetectie aan** | Zet dit aan als je meldingen wilt krijgen bij onverwacht waterverbruik. |
| **Check-interval** | Hoe vaak (in minuten) controleert de integratie op een lek buiten bewateringstijden? Standaard elke 5 minuten. |

---

### Stap 5 — Meldingen & planning

De integratie stuurt je elke avond een overzicht en kan 's ochtends automatisch starten. Hier stel je dat in.

| Instelling | Wat het doet |
|-----------|-------------|
| **Meldingsservice** | Via welke dienst wil je berichten ontvangen? Meestal je telefoon-app: `notify.mobile_app_[jouw_telefoon]`. |
| **Tijdstip avondadvies** | Hoe laat krijg je elke avond een bericht met het bewateringsadvies voor morgen? Standaard 20:00. |
| **Tijdstip ochtendstart** | Als automatisch starten aanstaat, hoe laat begint de bewatering dan? Standaard 06:00, voor het warmste deel van de dag. |
| **Automatisch starten** | Zet je dit aan, dan start de integratie zelf als het advies "aanbevolen" of "urgent" is. Zet het uit als je liever zelf op de knop drukt. |
| **Bevestiging vragen** | Als automatisch starten aanstaat, krijg je dan eerst nog een vraag op je telefoon voordat het water opengaat? Handig als je niet wilt dat het spontaan start als je op vakantie bent. |

---

## Na de installatie

Het dashboard verschijnt automatisch als **Tuinbewatering** in je HA-zijbalk. Zone-duren kun je daarna bijstellen via de schuifregelaars op het dashboard zonder de wizard opnieuw te doorlopen.
