from datetime import date
import json
import html
import logging
import sys
import time

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from folium.plugins import Draw, HeatMap
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

# -----------------------------
# Logging / diagnostics
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("biodiversity-dashboard")

def checkpoint(message):
    log.info(message)

checkpoint("APP_START")

st.set_page_config(
    page_title="Mijn Biodiversiteit",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 4rem; max-width: 1200px;}
div.stButton > button, div.stDownloadButton > button {
    min-height: 52px; font-size: 1.05rem; border-radius: 12px; width: 100%;
}
[data-testid="stMetric"] {
    padding: 12px; border: 1px solid rgba(128,128,128,.25); border-radius: 14px;
}
h1 {font-size: clamp(1.8rem, 5vw, 2.8rem);}
@media (max-width: 768px) {
  .block-container {padding-left: .8rem; padding-right: .8rem;}
}
</style>
""", unsafe_allow_html=True)

OBS_API = "https://api.inaturalist.org/v1/observations"
SPECIES_COUNTS_API = "https://api.inaturalist.org/v1/observations/species_counts"
TAXA_API = "https://api.inaturalist.org/v1/taxa"

if "areas" not in st.session_state:
    st.session_state.areas = {}
if "active_area" not in st.session_state:
    st.session_state.active_area = None
if "analysis_df" not in st.session_state:
    st.session_state.analysis_df = None
if "analysis_meta" not in st.session_state:
    st.session_state.analysis_meta = {}
if "timeline_firsts" not in st.session_state:
    st.session_state.timeline_firsts = {}
if "timeline_key" not in st.session_state:
    st.session_state.timeline_key = None
if "show_help" not in st.session_state:
    st.session_state.show_help = False

st.title("🌿 Mijn Biodiversiteit")
st.caption(
    "Ontdek de biodiversiteit van je tuin, park of natuurgebied met openbare "
    "iNaturalist-waarnemingen."
)

intro1, intro2, intro3 = st.columns(3)
intro1.markdown("**1 · Kies je gebied**  \nTeken een nieuw gebied of open een opgeslagen GeoJSON.")
intro2.markdown("**2 · Stel je analyse in**  \nKies periode, kwaliteit en het gewenste overzicht.")
intro3.markdown("**3 · Ontdek**  \nBekijk soortenrijkdom, trends, tijdlijn, heatmap en targetsoorten.")

if st.button("ℹ️ Hoe werkt deze app?", key="toggle_help"):
    st.session_state.show_help = not st.session_state.show_help

if st.session_state.show_help:
    st.info(
        "Begin bij ‘Gebied’: teken de grens van je tuin of onderzoeksgebied en geef die een naam. "
        "Je kunt gebieden als GeoJSON bewaren en later weer openen. Ga daarna naar ‘Dashboard’, "
        "kies een overzicht en start de analyse. Voor persoonlijke functies kun je je openbare "
        "iNaturalist-gebruikersnaam invullen; je wachtwoord is niet nodig. "
        "‘Target soorten’ gebruikt algemene openbare waarnemingen van alle waarnemers."
    )

checkpoint("UI_HEADER_READY")

tab_areas, tab_dashboard = st.tabs(["🗺️ Mijn gebieden", "📊 Dashboard"])

with tab_areas:

    if st.button("➕ Nieuw gebied", key="new_area"):
        st.session_state.active_area = None
        st.session_state.analysis_df = None
        st.session_state.analysis_meta = {}
        st.session_state.timeline_firsts = {}
        st.session_state.timeline_key = None
        st.success("Klaar voor een nieuw gebied. Teken het gebied op de kaart en geef het een naam.")

    st.subheader("Nieuw of bestaand gebied")

    if st.session_state.areas:
        names = list(st.session_state.areas)
        current = st.session_state.active_area if st.session_state.active_area in names else None
        default_index = names.index(current) + 1 if current else 0

        chosen = st.selectbox(
            "Opgeslagen gebieden",
            ["— kies —"] + names,
            index=default_index,
            key="saved_area_selector",
        )

        if chosen != "— kies —":
            c_open, c_status = st.columns([1, 2])
            with c_open:
                if st.button("📂 Gebied openen", type="primary", key="open_saved_area"):
                    st.session_state.active_area = chosen
                    st.session_state.analysis_df = None
                    st.session_state.analysis_meta = {}
                    st.rerun()
            with c_status:
                if st.session_state.active_area == chosen:
                    st.success(f"Actief gebied: {chosen}")

    st.markdown("### Gebieden openen of bewaren")
    st.info(
        "Een webapp mag uit veiligheidsoverwegingen niet zelfstandig naar een willekeurige map "
        "op je iPad, OneDrive of iCloud schrijven. De app maakt daarom een GeoJSON-bestand; "
        "via Safari/Bestanden kies je daarna zelf de doelmap."
    )
    uploaded_areas = st.file_uploader(
        "Open een eerder bewaard GeoJSON-bestand",
        type=["geojson", "json"],
        accept_multiple_files=False,
        help="Kies een bestand uit de opslaglocaties die op je apparaat beschikbaar zijn.",
    )

    if uploaded_areas is not None:
        upload_key = (uploaded_areas.name, uploaded_areas.size)
        if st.session_state.get("last_area_upload") != upload_key:
            try:
                imported = json.loads(uploaded_areas.getvalue().decode("utf-8"))
                features = (
                    imported.get("features") or []
                    if imported.get("type") == "FeatureCollection"
                    else [imported] if imported.get("type") == "Feature"
                    else []
                )
                count = 0
                first_name = None
                for i, feature in enumerate(features, 1):
                    geom = feature.get("geometry")
                    if not geom:
                        continue
                    name = str((feature.get("properties") or {}).get("name") or f"Geïmporteerd gebied {i}").strip()
                    st.session_state.areas[name] = geom
                    first_name = first_name or name
                    count += 1
                if count:
                    st.session_state.active_area = first_name
                    st.session_state.last_area_upload = upload_key
                    st.session_state.analysis_df = None
                    st.session_state.analysis_meta = {}
                    st.success(f"{count} gebied(en) ingelezen. '{first_name}' is actief gemaakt.")
                    st.rerun()
                else:
                    st.warning("In dit bestand zijn geen bruikbare gebieden gevonden.")
            except Exception as e:
                st.error(f"Dit bestand kon niet als GeoJSON worden geopend: {e}")

    area_name = st.text_input("Naam van het gebied", placeholder="Bijvoorbeeld: Mijn tuin")
    st.write("**Teken hieronder de grens.** Gebruik het polygoon- of rechthoek-icoon links op de kaart.")

    center = [51.93, 4.84]
    zoom = 11
    if st.session_state.active_area and st.session_state.active_area in st.session_state.areas:
        existing = shape(st.session_state.areas[st.session_state.active_area])
        c = existing.centroid
        center, zoom = [c.y, c.x], 16

    checkpoint("MAP_BUILD_START")
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)

    if st.session_state.active_area and st.session_state.active_area in st.session_state.areas:
        folium.GeoJson(
            st.session_state.areas[st.session_state.active_area],
            style_function=lambda _: {"weight": 3, "fillOpacity": 0.12},
        ).add_to(m)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True},
            "rectangle": True,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    map_state = st_folium(
        m,
        height=560,
        use_container_width=True,
        key="draw_map",
        returned_objects=["all_drawings"],
    )
    checkpoint("MAP_RENDERED")

    drawings = map_state.get("all_drawings") or []
    newest_geom = drawings[-1].get("geometry") if drawings else None

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Gebied bewaren", type="primary"):
            if not area_name.strip():
                st.error("Geef het gebied eerst een naam.")
            elif not newest_geom:
                st.error("Teken eerst een gebied op de kaart.")
            else:
                st.session_state.areas[area_name.strip()] = newest_geom
                st.session_state.active_area = area_name.strip()
                st.success(f"'{area_name.strip()}' is voor deze sessie opgeslagen.")
                checkpoint(f"AREA_SAVED name={area_name.strip()}")

    with c2:
        if st.button("🗑️ Actief gebied verwijderen"):
            n = st.session_state.active_area
            if n and n in st.session_state.areas:
                del st.session_state.areas[n]
                st.session_state.active_area = None
                st.session_state.analysis_df = None
                checkpoint(f"AREA_DELETED name={n}")
                st.rerun()

    if st.session_state.areas:
        st.markdown("### Gebieden beheren")

        active_for_manage = st.session_state.active_area
        if active_for_manage and active_for_manage in st.session_state.areas:
            new_name = st.text_input("Actief gebied hernoemen", value=active_for_manage, key="rename_area_name")
            if st.button("✏️ Hernoemen"):
                clean = new_name.strip()
                if not clean:
                    st.error("De naam mag niet leeg zijn.")
                elif clean != active_for_manage and clean in st.session_state.areas:
                    st.error("Er bestaat al een gebied met deze naam.")
                elif clean != active_for_manage:
                    geom = st.session_state.areas.pop(active_for_manage)
                    st.session_state.areas[clean] = geom
                    st.session_state.active_area = clean
                    st.rerun()

        export = json.dumps({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"name": n}, "geometry": g}
                for n, g in st.session_state.areas.items()
            ],
        }, ensure_ascii=False, indent=2)

        st.download_button(
            "💾 Alle gebieden opslaan als bestand",
            export,
            "mijn_biodiversiteitsgebieden.geojson",
            "application/geo+json",
            help="Bewaar het bestand via je browser op de locatie van je keuze.",
        )

        if active_for_manage and active_for_manage in st.session_state.areas:
            single = json.dumps({
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {"name": active_for_manage},
                    "geometry": st.session_state.areas[active_for_manage],
                }],
            }, ensure_ascii=False, indent=2)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in active_for_manage).strip("_") or "gebied"
            st.download_button(
                "💾 Actief gebied opslaan als bestand",
                single,
                f"{safe}.geojson",
                "application/geo+json",
            )

        st.caption(
            "Het GeoJSON-bestand is je permanente kopie. Bewaar het waar je wilt en open het later "
            "weer met de bestandskiezer hierboven."
        )


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_observations(params_tuple):
    checkpoint("OBS_FETCH_START")
    params = dict(params_tuple)
    rows = []
    page = 1
    total = None

    while True:
        call_params = dict(params)
        call_params.update(page=page, per_page=200)
        checkpoint(f"OBS_FETCH_PAGE page={page}")

        r = requests.get(OBS_API, params=call_params, timeout=(10, 30))
        r.raise_for_status()
        payload = r.json()

        if total is None:
            total = payload.get("total_results", 0)
            checkpoint(f"OBS_FETCH_TOTAL total={total}")

        batch = payload.get("results", [])
        rows.extend(batch)

        if len(batch) < 200 or page * 200 >= min(total, 10000):
            break

        page += 1
        time.sleep(0.1)

    checkpoint(f"OBS_FETCH_DONE fetched={len(rows)}")
    return rows, total or 0




@st.cache_data(ttl=3600, show_spinner=False)
def fetch_species_counts_around(lat, lng, radius_km, start_year, end_year, quality_grade):
    """
    Algemene iNaturalist-soortenlijst rondom een middelpunt, gesorteerd op aantal
    waarnemingen. Gebruikt de geaggregeerde species_counts endpoint.
    """
    rows = []
    page = 1

    while True:
        params = {
            "lat": float(lat),
            "lng": float(lng),
            "radius": float(radius_km),
            "d1": f"{int(start_year)}-01-01",
            "d2": f"{int(end_year)}-12-31",
            "per_page": 500,
            "page": page,
            "locale": "nl",
            "preferred_place_id": 7506,
        }
        if quality_grade:
            params["quality_grade"] = quality_grade

        checkpoint(f"TARGET_COUNTS_PAGE page={page}")
        r = requests.get(SPECIES_COUNTS_API, params=params, timeout=(10, 45))
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("results", [])
        rows.extend(batch)

        total = payload.get("total_results", 0)
        if not batch or len(batch) < 500 or page * 500 >= total:
            break

        page += 1
        time.sleep(1.0)

    checkpoint(f"TARGET_COUNTS_DONE species={len(rows)}")
    return rows


def build_target_species_table(df, area_geom, start_year, end_year, quality_grade):
    """
    Vergelijk alle soorten die in het exacte onderzoeksgebied zijn aangetroffen
    met alle soorten binnen 25 km van het middelpunt.
    """
    poly = shape(area_geom)
    center = poly.centroid

    counts = fetch_species_counts_around(
        center.y,
        center.x,
        25,
        start_year,
        end_year,
        quality_grade,
    )

    # Alleen soorten (geen genus/familie). Gebruik soort-ID's waar mogelijk.
    seen_species_ids = set(
        int(x)
        for x in df["species_id"].dropna().tolist()
        if x is not None
    )

    out = []
    for item in counts:
        taxon = item.get("taxon") or {}
        if taxon.get("rank") != "species":
            continue

        tid = taxon.get("id")
        if not tid or int(tid) in seen_species_ids:
            continue

        nl = taxon.get("preferred_common_name") or taxon.get("name") or "Onbekend"
        sci = taxon.get("name") or ""
        count = int(item.get("count") or 0)

        out.append({
            "Nederlandse naam": nl,
            "Wetenschappelijke naam": sci,
            "Waarnemingen binnen 25 km": count,
            "iNaturalist": f"https://www.inaturalist.org/taxa/{tid}",
        })

    if not out:
        return pd.DataFrame(
            columns=[
                "Nederlandse naam",
                "Wetenschappelijke naam",
                "Waarnemingen binnen 25 km",
                "iNaturalist",
            ]
        )

    target_df = pd.DataFrame(out)
    target_df = target_df.sort_values(
        ["Waarnemingen binnen 25 km", "Nederlandse naam"],
        ascending=[False, True],
    ).reset_index(drop=True)
    target_df.index = target_df.index + 1
    target_df.index.name = "Rang"
    return target_df


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_taxa_by_ids(ids_tuple):
    """
    Haal veel taxonrecords efficiënt op via /v1/taxa met taxon_id als queryparameter.
    Dit vermijdt honderden /v1/taxa/{id1,id2,...}-requests.
    """
    ids = sorted({int(x) for x in ids_tuple if x})
    result = {}

    # iNaturalist /v1/taxa kan veel taxa per pagina teruggeven.
    # We houden de chunks ruim onder 500 om URLs/parameters beheersbaar te houden.
    chunk_size = 350

    for start in range(0, len(ids), chunk_size):
        batch = ids[start:start + chunk_size]
        checkpoint(f"TAXON_QUERY_BATCH start={start} size={len(batch)}")

        try:
            params = {
                "taxon_id": ",".join(str(x) for x in batch),
                "per_page": 500,
                "page": 1,
                "locale": "nl",
                "preferred_place_id": 7506,
            }
            r = requests.get(TAXA_API, params=params, timeout=(10, 45))
            r.raise_for_status()
            payload = r.json()

            for tx in payload.get("results", []):
                tid = tx.get("id")
                if tid:
                    result[int(tid)] = tx

        except Exception as e:
            log.exception("TAXON_QUERY_BATCH_ERROR %s", e)

    checkpoint(f"TAXON_QUERY_DONE requested={len(ids)} returned={len(result)}")
    return result


def extract_ancestor_ids(taxon):
    """
    Verzamel ancestor IDs uit de vormen die in de observation-response kunnen voorkomen.
    """
    ids = []

    for item in taxon.get("ancestor_ids") or []:
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, str) and item.isdigit():
            ids.append(int(item))

    for item in taxon.get("ancestors") or []:
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, str) and item.isdigit():
            ids.append(int(item))
        elif isinstance(item, dict) and item.get("id"):
            ids.append(int(item["id"]))

    if taxon.get("id"):
        ids.append(int(taxon["id"]))

    return list(dict.fromkeys(ids))


def rank_from_ancestors(taxon, lookup, wanted_rank, scientific=False):
    """
    Zoek orde/familie in de opgehaalde ancestorrecords.
    """
    for tid in reversed(extract_ancestor_ids(taxon)):
        tx = lookup.get(int(tid))
        if tx and tx.get("rank") == wanted_rank:
            if scientific:
                return tx.get("name")
            return tx.get("preferred_common_name") or tx.get("name")
    return None


def rank_id_from_ancestors(taxon, lookup, wanted_rank):
    for tid in reversed(extract_ancestor_ids(taxon)):
        tx = lookup.get(int(tid))
        if tx and tx.get("rank") == wanted_rank:
            return int(tid)
    if taxon.get("rank") == wanted_rank and taxon.get("id"):
        return int(taxon["id"])
    return None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_personal_first_observations(username, species_ids_tuple):
    if not (username or "").strip():
        return {}

    species_ids = sorted({int(x) for x in species_ids_tuple if x})
    firsts = {}
    chunk_size = 100

    for start in range(0, len(species_ids), chunk_size):
        target = set(species_ids[start:start + chunk_size])
        unresolved = set(target)
        page = 1

        while unresolved:
            params = {
                "user_id": username,
                "taxon_ids": ",".join(str(x) for x in sorted(target)),
                "order_by": "observed_on",
                "order": "asc",
                "per_page": 200,
                "page": page,
                "locale": "nl",
            }

            checkpoint(
                f"LIFELIST_FETCH chunk={start//chunk_size + 1} "
                f"page={page} unresolved={len(unresolved)}"
            )

            r = requests.get(OBS_API, params=params, timeout=(10, 45))
            r.raise_for_status()
            payload = r.json()
            results = payload.get("results", [])

            for obs in results:
                tx = obs.get("taxon") or {}
                lineage = set(extract_ancestor_ids(tx))
                matches = unresolved.intersection(lineage)
                for sid in list(matches):
                    firsts[sid] = {
                        "date": obs.get("observed_on"),
                        "observation_id": obs.get("id"),
                    }
                    unresolved.discard(sid)

            total = payload.get("total_results", 0)
            if not results or len(results) < 200 or page * 200 >= min(total, 10000):
                break

            page += 1
            time.sleep(1.0)

        time.sleep(1.0)

    checkpoint(f"LIFELIST_DONE species={len(species_ids)} firsts={len(firsts)}")
    return firsts


def timeline_html(timeline_df, personal_firsts):
    cards = []

    for _, row in timeline_df.iterrows():
        sid = int(row["species_id"]) if pd.notna(row["species_id"]) else None
        first_info = personal_firsts.get(sid, {}) if sid else {}

        is_personal_first = bool(
            first_info
            and first_info.get("observation_id")
            and int(first_info["observation_id"]) == int(row["observation_id"])
        )

        border = "#d62728" if is_personal_first else "#2b6cb0"
        label = "Eerste iNaturalist-waarneming" if is_personal_first else "Nieuw voor dit gebied"

        nl = html.escape(str(row.get("species_nl") or row.get("Nederlandse naam") or "Onbekend"))
        sci = html.escape(str(row.get("species_scientific") or row.get("wetenschappelijke naam") or ""))
        date_text = pd.to_datetime(row["datum"]).strftime("%d-%m-%Y")
        url = html.escape(str(row.get("inat_url") or "#"))

        photo = row.get("photo_url")
        if isinstance(photo, str) and photo:
            photo_html = (
                '<img loading="lazy" src="' + html.escape(photo) + '" '
                'style="width:156px;height:118px;object-fit:cover;'
                'border-radius:10px 10px 0 0;display:block;">'
            )
        else:
            photo_html = (
                '<div style="width:156px;height:118px;border-radius:10px 10px 0 0;'
                'display:flex;align-items:center;justify-content:center;background:#f1f3f5;'
                'font-size:13px;color:#666;">Geen foto</div>'
            )

        card = (
            '<a href="' + url + '" target="_blank" style="text-decoration:none;color:inherit;">'
            '<div style="width:156px;min-width:156px;border:4px solid ' + border + ';'
            'border-radius:14px;background:white;overflow:hidden;'
            'box-shadow:0 2px 8px rgba(0,0,0,.12);">'
            + photo_html +
            '<div style="padding:8px 9px 10px 9px;white-space:normal;">'
            '<div style="font-weight:700;font-size:13px;line-height:1.2;">' + nl + '</div>'
            '<div style="font-style:italic;font-size:11px;color:#555;line-height:1.2;margin-top:2px;">' + sci + '</div>'
            '<div style="font-size:12px;margin-top:7px;font-weight:600;">' + date_text + '</div>'
            '<div style="font-size:10px;color:' + border + ';margin-top:4px;font-weight:700;">' + label + '</div>'
            '</div></div></a>'
        )
        cards.append(card)

    return (
        '<div style="overflow-x:auto;overflow-y:hidden;display:flex;gap:14px;'
        'padding:10px 4px 18px 4px;scroll-snap-type:x proximity;'
        '-webkit-overflow-scrolling:touch;">'
        + ''.join(cards) +
        '</div>'
    )


def rank_name(taxon_record, wanted_rank, scientific=False):
    if taxon_record.get("rank") == wanted_rank:
        if scientific:
            return taxon_record.get("name")
        return taxon_record.get("preferred_common_name") or taxon_record.get("name")

    for anc in reversed(taxon_record.get("ancestors") or []):
        if anc.get("rank") == wanted_rank:
            if scientific:
                return anc.get("name")
            return anc.get("preferred_common_name") or anc.get("name")
    return None


def pie_chart(data, names, values, title):
    fig = px.pie(data, names=names, values=values, hole=0.35, title=title)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(legend_title_text="", margin=dict(t=60, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)


with tab_dashboard:
    active = st.session_state.active_area

    if not active or active not in st.session_state.areas:
        st.info("Maak of kies eerst een gebied in ‘Mijn gebieden’.")
    else:
        st.subheader(active)

        with st.expander("Filters", expanded=True):
            username = st.text_input("iNaturalist-gebruikersnaam", value="")
            mode = st.segmented_control(
                "Waarnemers",
                ["Mijn waarnemingen", "Alle waarnemers"],
                default="Mijn waarnemingen",
            )

            c1, c2 = st.columns(2)
            with c1:
                start_year = st.number_input("Vanaf", 2000, date.today().year, 2020)
            with c2:
                end_year = st.number_input("Tot en met", 2000, date.today().year, date.today().year)

            quality = st.selectbox("Kwaliteit", ["Alle", "Research grade", "Needs ID", "Casual"])

        overview_choice = st.selectbox(
            "Kies overzicht",
            [
                "Taxonomische samenstelling",
                "Heatmap",
                "Per jaar",
                "Gemiddeld per kalendermaand",
                "Cumulatief aantal soorten per kwartaal",
                "Tijdlijn nieuwe soorten",
                "Meest waargenomen soorten",
                "Target soorten",
            ],
            help="Alleen het gekozen overzicht wordt berekend en weergegeven.",
        )

        if st.button("🔎 Analyseer dit gebied", type="primary"):
            # Persoonlijke overzichten hebben een iNaturalist-gebruikersnaam nodig.
            # Target soorten gebruikt algemene openbare waarnemingen en vormt daarop een uitzondering.
            if (
                mode == "Mijn waarnemingen"
                and overview_choice != "Target soorten"
                and not username.strip()
            ):
                st.error(
                    "Vul eerst je iNaturalist-gebruikersnaam in, of kies "
                    "‘Alle waarnemers’."
                )
                st.stop()

            try:
                checkpoint("ANALYSIS_START")

                geom = st.session_state.areas[active]
                poly = shape(geom)
                minx, miny, maxx, maxy = poly.bounds

                params = {
                    "swlat": miny,
                    "swlng": minx,
                    "nelat": maxy,
                    "nelng": maxx,
                    "d1": f"{int(start_year)}-01-01",
                    "d2": f"{int(end_year)}-12-31",
                    "order_by": "observed_on",
                    "order": "desc",
                    "locale": "nl",
                    "preferred_place_id": 7506,
                }

                if mode == "Mijn waarnemingen" and overview_choice != "Target soorten":
                    params["user_id"] = username.strip()

                qp = {
                    "Alle": None,
                    "Research grade": "research",
                    "Needs ID": "needs_id",
                    "Casual": "casual",
                }[quality]
                if qp:
                    params["quality_grade"] = qp

                with st.status("Analyse uitvoeren…", expanded=True) as status:
                    st.write("Waarnemingen ophalen…")
                    raw, total = fetch_observations(tuple(sorted(params.items())))

                    st.write("Exact binnen het getekende gebied filteren…")
                    inside = []

                    for o in raw:
                        geo = o.get("geojson")
                        coords = geo.get("coordinates") if geo else None
                        if coords and poly.covers(Point(coords[0], coords[1])):
                            inside.append(o)

                    checkpoint(f"POLYGON_FILTER_DONE inside={len(inside)} raw={len(raw)}")

                    if not inside:
                        status.update(label="Geen waarnemingen gevonden", state="complete")
                        st.warning("Geen exact binnen dit gebied gelegen waarnemingen gevonden.")
                        st.stop()

                    need_taxonomy = overview_choice in {
                        "Taxonomische samenstelling",
                        "Tijdlijn nieuwe soorten",
                        "Target soorten",
                    }

                    taxon_lookup = {}
                    if need_taxonomy:
                        st.write("Taxonomische indeling bepalen…")
                        checkpoint("FAST_TAXONOMY_START")

                        all_ancestor_ids = set()
                        for o in inside:
                            tx = o.get("taxon") or {}
                            all_ancestor_ids.update(extract_ancestor_ids(tx))

                        checkpoint(
                            f"ANCESTOR_IDS_NEEDED observations={len(inside)} "
                            f"unique_taxa={len(all_ancestor_ids)}"
                        )
                        taxon_lookup = fetch_taxa_by_ids(tuple(sorted(all_ancestor_ids)))

                    out = []
                    for o in inside:
                        taxon = o.get("taxon") or {}
                        tid = taxon.get("id")
                        focal = taxon_lookup.get(int(tid), {}) if tid else {}

                        nl_name = (
                            focal.get("preferred_common_name")
                            or taxon.get("preferred_common_name")
                            or taxon.get("name")
                            or "Onbekend"
                        )

                        geo = o.get("geojson") or {}
                        coords = geo.get("coordinates") or [None, None]
                        lon = coords[0] if len(coords) > 0 else None
                        lat = coords[1] if len(coords) > 1 else None

                        species_id = None
                        if taxon.get("rank") == "species" and taxon.get("id"):
                            species_id = int(taxon["id"])
                        elif need_taxonomy:
                            species_id = rank_id_from_ancestors(taxon, taxon_lookup, "species")

                        species_rec = taxon_lookup.get(species_id, {}) if species_id else {}
                        species_nl = species_rec.get("preferred_common_name") or nl_name
                        species_scientific = species_rec.get("name") or taxon.get("name")

                        photos = o.get("photos") or []
                        photo_url = None
                        if photos:
                            photo_url = photos[0].get("url")
                            if photo_url:
                                photo_url = photo_url.replace("square", "medium")

                        out.append({
                            "datum": o.get("observed_on"),
                            "Nederlandse naam": nl_name,
                            "wetenschappelijke naam": taxon.get("name"),
                            "species_id": species_id,
                            "species_nl": species_nl,
                            "species_scientific": species_scientific,
                            "observation_id": o.get("id"),
                            "photo_url": photo_url,
                            "inat_url": (
                                f"https://www.inaturalist.org/observations/{o.get('id')}"
                                if o.get("id") else None
                            ),
                            "soortgroep": taxon.get("iconic_taxon_name") or "Onbekend",
                            "orde": (
                                rank_from_ancestors(taxon, taxon_lookup, "order")
                                if need_taxonomy else None
                            ),
                            "orde_wetenschappelijk": (
                                rank_from_ancestors(taxon, taxon_lookup, "order", scientific=True)
                                if need_taxonomy else None
                            ),
                            "familie": (
                                rank_from_ancestors(taxon, taxon_lookup, "family")
                                if need_taxonomy else None
                            ),
                            "lat": lat,
                            "lon": lon,
                        })

                    checkpoint("FAST_TAXONOMY_DONE")

                    df = pd.DataFrame(out)
                    df["datum"] = pd.to_datetime(df["datum"], errors="coerce")
                    df = df.dropna(subset=["datum"])
                    df["jaar"] = df["datum"].dt.year.astype(int)
                    df["maand"] = df["datum"].dt.month.astype(int)
                    df["kwartaal"] = df["datum"].dt.quarter.astype(int)

                    st.session_state.analysis_df = df
                    st.session_state.analysis_meta = {
                        "total": total,
                        "start_year": int(start_year),
                        "end_year": int(end_year),
                        "username": username.strip(),
                        "mode": mode,
                    }
                    st.session_state.timeline_firsts = {}
                    st.session_state.timeline_key = None

                    checkpoint(f"DATAFRAME_READY rows={len(df)}")
                    status.update(label="Analyse gereed", state="complete")

            except Exception as e:
                log.exception("ANALYSIS_FATAL")
                st.error(f"Analyse kon niet worden voltooid: {e}")

        df = st.session_state.analysis_df
        meta = st.session_state.analysis_meta

        if df is not None and not df.empty:
            checkpoint("DASHBOARD_RENDER_START")

            a, b, c, d = st.columns(4)
            a.metric("Waarnemingen", len(df))
            b.metric("Taxa", df["wetenschappelijke naam"].nunique())
            c.metric("Soortgroepen", df["soortgroep"].nunique())
            d.metric("Jaren", df["jaar"].nunique())

            selected_overview = overview_choice

            taxonomy_needed_now = selected_overview in {
                "Taxonomische samenstelling",
                "Tijdlijn nieuwe soorten",
                "Target soorten",
            }
            taxonomy_available = (
                "orde" in df.columns
                and df["orde"].notna().any()
            ) or (
                "species_id" in df.columns
                and df["species_id"].notna().any()
            )

            if taxonomy_needed_now and not taxonomy_available:
                st.info(
                    "Dit overzicht heeft aanvullende soortgegevens nodig. "
                    "Klik één keer opnieuw op ‘Analyseer dit gebied’ met deze keuze actief. "
                    "Daarna kun je het overzicht gebruiken."
                )

            if selected_overview == "Taxonomische samenstelling" and taxonomy_available:
                st.subheader("Samenstelling per soortgroep")
                group_counts = (
                    df["soortgroep"].fillna("Onbekend")
                    .value_counts()
                    .rename_axis("soortgroep")
                    .reset_index(name="waarnemingen")
                )
                pie_chart(group_counts, "soortgroep", "waarnemingen", "Waarnemingen per soortgroep")

                insects = df[df["soortgroep"].eq("Insecta")].copy()

                if not insects.empty:
                    unknown_order_pct = insects["orde"].isna().mean() * 100
                    unknown_family_pct = insects["familie"].isna().mean() * 100
                    checkpoint(
                        f"TAXONOMY_QUALITY insects={len(insects)} "
                        f"unknown_order_pct={unknown_order_pct:.1f} "
                        f"unknown_family_pct={unknown_family_pct:.1f}"
                    )
                    if unknown_order_pct > 20:
                        st.warning(
                            f"Taxonomische controle: {unknown_order_pct:.1f}% van de insectwaarnemingen "
                            "heeft nog geen herkende orde. Dit wordt ook in de Streamlit-log geregistreerd."
                        )
                    st.subheader("Insecten per orde")
                    order_counts = (
                        insects["orde"].fillna("Onbekende orde")
                        .value_counts()
                        .rename_axis("orde")
                        .reset_index(name="waarnemingen")
                    )
                    pie_chart(order_counts, "orde", "waarnemingen", "Insecten uitgesplitst naar orde")

                    leps = insects[insects["orde_wetenschappelijk"].eq("Lepidoptera")].copy()

                    if not leps.empty:
                        st.subheader("Vlinders per familie")
                        fam_counts = (
                            leps["familie"].fillna("Onbekende familie")
                            .value_counts()
                            .rename_axis("familie")
                            .reset_index(name="waarnemingen")
                        )
                        pie_chart(fam_counts, "familie", "waarnemingen", "Vlinders uitgesplitst naar familie")


            if selected_overview == "Heatmap":
                st.subheader("Heatmap van waarnemingen")
                st.caption(
                    "Donkerdere/intenser gekleurde zones bevatten meer waarnemingen. "
                    "De heatmap gebruikt alleen de locaties binnen het gekozen gebied."
                )

                heat_df = df.dropna(subset=["lat", "lon"]).copy()
                if not heat_df.empty:
                    # Centreer de kaart op het onderzoeksgebied.
                    geom = st.session_state.areas[active]
                    poly = shape(geom)
                    c = poly.centroid

                    heat_map = folium.Map(
                        location=[c.y, c.x],
                        zoom_start=16,
                        tiles="OpenStreetMap",
                        control_scale=True,
                    )

                    # Toon de grens van het gekozen gebied.
                    folium.GeoJson(
                        geom,
                        name="Onderzoeksgebied",
                        style_function=lambda _: {
                            "weight": 3,
                            "fillOpacity": 0.04,
                        },
                    ).add_to(heat_map)

                    heat_points = heat_df[["lat", "lon"]].astype(float).values.tolist()
                    HeatMap(
                        heat_points,
                        radius=18,
                        blur=14,
                        min_opacity=0.25,
                        max_zoom=18,
                    ).add_to(heat_map)

                    st_folium(
                        heat_map,
                        height=520,
                        use_container_width=True,
                        key="heatmap_map",
                        returned_objects=[],
                    )
                else:
                    st.info("Voor deze selectie zijn geen bruikbare coördinaten beschikbaar.")

            if selected_overview == "Per jaar":
                st.subheader("Waarnemingen en taxa per jaar")
                yearly = (
                    df.groupby("jaar")
                    .agg(
                        waarnemingen=("Nederlandse naam", "size"),
                        taxa=("wetenschappelijke naam", "nunique"),
                    )
                    .reset_index()
                )
                fig_year = px.bar(
                    yearly,
                    x="jaar",
                    y=["waarnemingen", "taxa"],
                    barmode="group",
                    labels={"value": "Aantal", "jaar": "Jaar", "variable": ""},
                )
                fig_year.update_layout(legend_title_text="")
                st.plotly_chart(fig_year, use_container_width=True)

            if selected_overview == "Gemiddeld per kalendermaand":
                st.subheader("Gemiddeld per kalendermaand")
                years = list(range(meta["start_year"], meta["end_year"] + 1))
                idx = pd.MultiIndex.from_product([years, range(1, 13)], names=["jaar", "maand"])

                obs_month = df.groupby(["jaar", "maand"]).size().reindex(idx, fill_value=0)
                taxa_month = (
                    df.groupby(["jaar", "maand"])["wetenschappelijke naam"]
                    .nunique()
                    .reindex(idx, fill_value=0)
                )

                monthly = pd.DataFrame({
                    "waarnemingen": obs_month.groupby("maand").mean(),
                    "taxa": taxa_month.groupby("maand").mean(),
                }).reset_index()

                maandnamen = {
                    1: "Jan", 2: "Feb", 3: "Mrt", 4: "Apr", 5: "Mei", 6: "Jun",
                    7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec"
                }
                monthly["kalendermaand"] = monthly["maand"].map(maandnamen)

                fig_month = px.bar(
                    monthly,
                    x="kalendermaand",
                    y=["waarnemingen", "taxa"],
                    barmode="group",
                    labels={"value": "Gemiddeld aantal", "kalendermaand": "Maand", "variable": ""},
                )
                fig_month.update_layout(legend_title_text="")
                st.plotly_chart(fig_month, use_container_width=True)

            if selected_overview == "Cumulatief aantal soorten per kwartaal":
                st.subheader("Cumulatief aantal soorten per kwartaal")
                st.caption(
                    "Elke staaf toont hoeveel verschillende soorten er tot en met dat kwartaal "
                    "in totaal zijn waargenomen. Het bovenste deel zijn de soorten die in dat "
                    "kwartaal voor het eerst zijn waargenomen."
                )

                species_df = (
                    df.dropna(subset=["wetenschappelijke naam"])
                    .sort_values("datum")
                    .copy()
                )

                # Eerste waarneming van elke soort binnen de geselecteerde periode.
                first_seen = (
                    species_df
                    .drop_duplicates("wetenschappelijke naam", keep="first")
                    [["datum", "wetenschappelijke naam"]]
                )
                first_seen["jaar"] = first_seen["datum"].dt.year.astype(int)
                first_seen["kwartaal"] = first_seen["datum"].dt.quarter.astype(int)

                # Alle kwartalen in de geselecteerde periode, ook kwartalen zonder nieuwe soorten.
                quarter_rows = []
                for yr in range(meta["start_year"], meta["end_year"] + 1):
                    for q in range(1, 5):
                        quarter_rows.append({"jaar": yr, "kwartaal": q})
                quarterly = pd.DataFrame(quarter_rows)

                new_counts = (
                    first_seen.groupby(["jaar", "kwartaal"])
                    .size()
                    .reset_index(name="nieuwe soorten")
                )

                quarterly = quarterly.merge(
                    new_counts,
                    on=["jaar", "kwartaal"],
                    how="left",
                )
                quarterly["nieuwe soorten"] = quarterly["nieuwe soorten"].fillna(0).astype(int)

                # Cumulatief aantal soorten tot en met ieder kwartaal.
                quarterly["totaal soorten"] = quarterly["nieuwe soorten"].cumsum()

                # Onderste segment: soorten die al vóór dit kwartaal bekend waren.
                quarterly["eerder bekende soorten"] = (
                    quarterly["totaal soorten"] - quarterly["nieuwe soorten"]
                )

                quarterly["periode"] = (
                    quarterly["jaar"].astype(str)
                    + " Q"
                    + quarterly["kwartaal"].astype(str)
                )

                q_long = quarterly.melt(
                    id_vars=["periode", "totaal soorten"],
                    value_vars=["eerder bekende soorten", "nieuwe soorten"],
                    var_name="categorie",
                    value_name="aantal",
                )

                q_long["categorie"] = pd.Categorical(
                    q_long["categorie"],
                    categories=["eerder bekende soorten", "nieuwe soorten"],
                    ordered=True,
                )
                q_long = q_long.sort_values(["periode", "categorie"])

                # Bouw de gestapelde staaf expliciet op, zodat het rode segment
                # gegarandeerd boven op het donkerblauwe segment staat.
                fig_quarter = go.Figure()

                fig_quarter.add_bar(
                    x=quarterly["periode"],
                    y=quarterly["eerder bekende soorten"],
                    name="Eerder bekende soorten",
                    marker_color="#1f4e79",
                    text=quarterly["eerder bekende soorten"].astype(str),
                    textposition="inside",
                )

                fig_quarter.add_bar(
                    x=quarterly["periode"],
                    y=quarterly["nieuwe soorten"],
                    name="Nieuwe soorten",
                    marker_color="#d62728",
                    text=quarterly["nieuwe soorten"].astype(str),
                    textposition="inside",
                )

                # Cumulatief totaal boven iedere gestapelde staaf.
                fig_quarter.add_scatter(
                    x=quarterly["periode"],
                    y=quarterly["totaal soorten"],
                    mode="text",
                    text=quarterly["totaal soorten"].astype(str),
                    textposition="top center",
                    name="Totaal",
                    showlegend=False,
                    hoverinfo="skip",
                )

                fig_quarter.update_layout(
                    barmode="stack",
                    legend_title_text="",
                    xaxis_title="Kwartaal",
                    yaxis_title="Cumulatief aantal soorten",
                )

                st.plotly_chart(fig_quarter, use_container_width=True)

            if selected_overview == "Tijdlijn nieuwe soorten" and taxonomy_available:
                st.subheader("Chronologische tijdlijn van nieuwe soorten")
                st.caption(
                    "De kaarten staan op datum van de eerste waarneming van die soort in het gekozen "
                    "gebied binnen de geselecteerde periode. Blauw = nieuw voor het gebied. "
                    "Rood = deze waarneming is óók je vroegste iNaturalist-waarneming van die soort. "
                    "Tik op een kaart om de oorspronkelijke iNaturalist-waarneming te openen."
                )

                timeline = (
                    df.dropna(subset=["species_id", "observation_id"])
                    .sort_values(["datum", "observation_id"])
                    .drop_duplicates("species_id", keep="first")
                    .copy()
                )
                timeline["species_id"] = timeline["species_id"].astype(int)
                # Meest recente nieuwe soort eerst; daarna terug in de tijd scrollen.
                timeline = timeline.sort_values(
                    ["datum", "species_nl"],
                    ascending=[False, True],
                )

                timeline_key = (
                    meta.get("username"),
                    tuple(timeline["species_id"].tolist()),
                )

                if meta.get("mode") == "Mijn waarnemingen":
                    if st.session_state.timeline_key != timeline_key:
                        st.info(
                            "Voor de rode omlijning moet de app éénmalig je vroegste iNaturalist-"
                            "waarneming voor deze soorten bepalen. Dit resultaat wordt daarna gecachet."
                        )
                        if st.button(
                            "🔎 Bepaal mijn eerste iNaturalist-waarnemingen",
                            key="build_lifelist_timeline",
                        ):
                            with st.spinner("Persoonlijke eerste waarnemingen bepalen…"):
                                st.session_state.timeline_firsts = fetch_personal_first_observations(
                                    meta.get("username") or "",
                                    tuple(timeline["species_id"].tolist()),
                                )
                                st.session_state.timeline_key = timeline_key
                            st.rerun()

                    personal_firsts = (
                        st.session_state.timeline_firsts
                        if st.session_state.timeline_key == timeline_key
                        else {}
                    )
                else:
                    personal_firsts = {}
                    st.info(
                        "De rode omlijning is alleen beschikbaar wanneer je analyseert met "
                        "‘Mijn waarnemingen’. In ‘Alle waarnemers’ wordt de tijdlijn blauw weergegeven."
                    )

                st.markdown(
                    '<div style="font-size:12px;margin-bottom:4px;">'
                    '<span style="display:inline-block;width:12px;height:12px;border:3px solid #2b6cb0;'
                    'border-radius:3px;vertical-align:-2px;margin-right:5px;"></span>Nieuw voor gebied&nbsp;&nbsp;&nbsp;'
                    '<span style="display:inline-block;width:12px;height:12px;border:3px solid #d62728;'
                    'border-radius:3px;vertical-align:-2px;margin-right:5px;"></span>Eerste persoonlijke iNaturalist-waarneming'
                    '</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(timeline_html(timeline, personal_firsts), unsafe_allow_html=True)

            if selected_overview == "Target soorten" and taxonomy_available:
                st.subheader("Target soorten binnen 25 km")
                st.caption(
                    "Dit overzicht gebruikt alle openbare iNaturalist-waarnemingen, niet alleen "
                    "jouw eigen waarnemingen. Een targetsoort is binnen de geselecteerde periode "
                    "wel binnen 25 km van het middelpunt van het gebied waargenomen, maar niet "
                    "binnen het getekende gebied zelf. De meest waargenomen soorten staan bovenaan."
                )

                qp_target = {
                    "Alle": None,
                    "Research grade": "research",
                    "Needs ID": "needs_id",
                    "Casual": "casual",
                }.get(quality)

                with st.spinner("Targetsoorten binnen 25 km bepalen…"):
                    target_df = build_target_species_table(
                        df,
                        st.session_state.areas[active],
                        meta["start_year"],
                        meta["end_year"],
                        qp_target,
                    )

                if target_df.empty:
                    st.success(
                        "Binnen deze periode zijn geen soorten gevonden die wel binnen 25 km "
                        "maar nog niet in het gekozen gebied zijn waargenomen."
                    )
                else:
                    c1, c2 = st.columns(2)
                    c1.metric("Target soorten", len(target_df))
                    c2.metric(
                        "Meeste waarnemingen",
                        int(target_df["Waarnemingen binnen 25 km"].max()),
                    )

                    st.dataframe(
                        target_df,
                        use_container_width=True,
                        column_config={
                            "iNaturalist": st.column_config.LinkColumn("iNaturalist"),
                            "Waarnemingen binnen 25 km": st.column_config.NumberColumn(
                                "Waarnemingen binnen 25 km",
                                format="%d",
                            ),
                        },
                    )

            if selected_overview == "Meest waargenomen soorten":
                st.subheader("Meest waargenomen soorten")
                top = (
                    df.groupby(
                        ["Nederlandse naam", "wetenschappelijke naam"],
                        dropna=False,
                    )
                    .size()
                    .reset_index(name="waarnemingen")
                    .sort_values("waarnemingen", ascending=False)
                    .head(30)
                )
                st.dataframe(top, use_container_width=True, hide_index=True)

            if meta.get("total", 0) > 10000:
                st.warning(
                    "De zoekopdracht bevat meer dan 10.000 resultaten. "
                    "Verklein gebied of periode voor volledige dekking."
                )

            checkpoint("DASHBOARD_RENDER_DONE")

st.caption(
    "publieke webapp v0.23 · snelle taxonomie + interactieve heatmap · "
    "geen iNaturalist-analyse vóór je op ‘Analyseer dit gebied’ drukt."
)

checkpoint("APP_END")
