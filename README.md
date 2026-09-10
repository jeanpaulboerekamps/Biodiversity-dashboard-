# Mijn Biodiversiteit — iPad/web prototype

Deze versie is ingericht voor gebruik als webapp op iPad, desktop en telefoon.

## Belangrijkste verbeteringen
- touchvriendelijke grote knoppen;
- schermvullende kaart;
- eigen gebieden tekenen en een naam geven;
- meerdere gebieden tijdens een sessie;
- gebieden exporteren als GeoJSON;
- dashboard per gekozen gebied;
- eigen iNaturalist-waarnemingen of alle waarnemers;
- CSV-export.

## Lokaal starten
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Online zetten
Zet `app.py` en `requirements.txt` in een GitHub-repository en deploy die repository
via Streamlit Community Cloud. Daarna open je de toegewezen `streamlit.app`-URL in Safari
op de iPad.

## iPad
In Safari kun je de webapp via de deelknop aan het beginscherm toevoegen. De applicatie
blijft technisch een webapp; Python draait op de server.

## Nog niet permanent
De namen/geometrieën worden nu in de Streamlit-sessie bewaard. Gebruik de GeoJSON-download
om ze buiten de sessie te bewaren. Een volgende versie kan permanente opslag toevoegen.
