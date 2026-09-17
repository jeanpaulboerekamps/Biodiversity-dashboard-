# Mijn Biodiversiteit — publieksversie v0.37

Publieksvriendelijke versie.

## Nieuw in v0.37

- De onbedoelde foto-upload en daarmee de dubbele knop **Kies gebied** zijn verwijderd.
- De overzichtskeuzes staan weer permanent uitgeklapt in beeld.
- Meerdere overzichten blijven mogelijk via afzonderlijke selectievakjes.

## Eerder toegevoegd in v0.36

- **Alle waarnemingen** is de standaardkeuze.
- Er kunnen meerdere overzichten tegelijk worden gekozen en weergegeven.
- Nummers en groepsvoorzinnen zijn uit de namen van de overzichten verwijderd.
- De blokken **Gebied bewaren of beheren** en **Over Mijn Biodiversiteit** zijn verwijderd.
- Eigen JPG-, PNG- en WebP-foto's kunnen bovenaan worden toegevoegd; deze blijven gedurende de sessie zichtbaar.
- De eerdere standaardfoto's worden niet meer op de pagina getoond.

## Eerder toegevoegd in v0.35

- Uitleg en privacy staan onderaan en verstoren de primaire werklijn niet meer.
- De gebiedskiezer toont alleen **Kies gebied**; de drag-and-drop-uitleg is verborgen.
- Een gebiedsnaam wordt bij één geopend gebied nog maar eenmaal getoond.
- De overbodige koppen **Gebied** en **Wat wil je ontdekken?** zijn verwijderd.
- De waarnemingskeuze staat compact links; gebruikersnaam, periode en kwaliteit staan rechts.
- De browser opent de eigen bestandskiezer en onthoudt doorgaans de laatst gebruikte map.

## Eerder toegevoegd in v0.34

- Eén doorlopende pagina zonder aparte stappen of tabbladen.
- Een bewaard GeoJSON-gebied kies je direct bovenaan.
- De tekenkaart wordt alleen geladen na **Nieuw gebied maken**, wat normaal gebruik lichter maakt.
- De analyse start automatisch zodra een overzicht is gekozen; de losse analyseknop is vervallen.
- Reeds berekende combinaties blijven binnen de sessie beschikbaar en API-resultaten gebruiken de cache.
- De natuurfoto's staan compact onder **Over Mijn Biodiversiteit**.

## Eerder toegevoegd in v0.33

- het hoofdmenu staat weer volledig uitgeklapt in beeld;
- alle overzichten zijn logisch gegroepeerd onder dezelfde drie publieksvragen
  als op de startpagina;
- Atlas of Life staat als laatste keuze in het menu;
- drie lokaal meegeleverde natuurfoto's geven de startpagina meer uitstraling;
- fotografen, bronpagina's en hergebruiklicenties staan zichtbaar in de app;

## Eerder toegevoegd in v0.32

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
Na installatie staat onderaan zichtbaar `Publieksversie 2.6 · Atlas-koppeling v0.37`.
