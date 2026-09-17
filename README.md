# Mijn Biodiversiteit — publieksversie v0.32

Publieksvriendelijke versie.

## Nieuw in v0.32

- rustige publieksintroductie met drie duidelijke stappen;
- genummerde route van gebied kiezen naar biodiversiteit ontdekken;
- compacte, begrijpelijke Nederlandse overzichtskeuzes;
- gebruikersnaam verschijnt alleen voor persoonlijke waarnemingen;
- periodekeuze als één duidelijke schuifregelaar;
- Nederlandse kwaliteitslabels met behoud van de juiste API-filters;
- zichtbare uitleg wanneer een overzicht aanvullende soortgegevens nodig heeft;
- responsieve kaarten en introductie voor tablet, laptop en telefoon;

- Atlas v83 met iNaturalist als taxonomische ruggengraat;
- waargenomen soorten worden primair gekoppeld op de stabiele iNaturalist taxon-ID;
- alleen waarnemingen die tot een soort-ID zijn herleid tellen mee in het
  koppelresultaat;
- taxonnamen op genus-, familie-, complex- of hoger niveau worden afzonderlijk
  vermeld en niet langer onterecht als ontbrekende soortpositie geteld;
- iNaturalist-voorouders worden via de exacte multi-ID-route opgehaald, zodat
  ondersoorten, variëteiten en andere lagere rangen betrouwbaar naar hun soort
  worden herleid;
- API-antwoorden worden direct teruggebracht tot de velden die de analyse
  werkelijk gebruikt, zodat foto's en overige metadata niet in het geheugen
  en de Streamlit-cache blijven staan;
- observatiepagina's en taxonbatches worden begrensd parallel opgehaald om de
  eerste analyse aanzienlijk te versnellen;
- wetenschappelijke, Nederlandse en Engelse soortnamen gaan mee naar de Atlas;
- naamkoppeling blijft tijdelijk beschikbaar voor een gefaseerde overgang;
- maandelijkse Atlas-build publiceert taxonomie en soortcoördinaten als één snapshot;
- doorlopende blauwe soortzoekers op ieder zoomniveau;
- zoekringen volgen na koppeling het actuele soortcentrum en verdwijnen pas als de stip goed zichtbaar is;
- het eindresultaat van de coördinatenkoppeling verdwijnt na 6,5 seconden;
- grotere gekoppelde waarnemingspunten met witte zoekrand, binnen hun soortcirkel;
- zichtbare zoekringen blijven staan totdat exportcoördinaten live zijn gekoppeld;
- maximaal drie relevante soorttakken worden per stilstaande viewport gekoppeld;
- iPad-prestatiemodus met een lichter canvas en zonder zware SVG-filters;
- detaildata laadt per stilstaande viewport begrensd in plaats van als kettingreactie.

- neutrale introductie;
- drie korte startstappen;
- knop `Hoe werkt deze app?`;
- knop `Nieuw gebied`;
- geen persoonlijke gebruikersnaam als standaard;
- uitleg over persoonlijke versus algemene iNaturalist-data.

### iPad
Open de app in Safari en kies `Delen` → `Zet op beginscherm`.

### Delen
Zet de Streamlit-app op public en deel de vaste `*.streamlit.app` URL.

### GitHub
Vervang bij deze versie minimaal `app.py` (of upload de volledige projectinhoud).
Na installatie staat onderaan zichtbaar `Publieksversie 2.1 · Atlas-koppeling v0.32`.
