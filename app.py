from datetime import date
import json
import logging
import sys
import time

import folium
import pandas as pd
import plotly.express as px
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
TAXA_API = "https://api.inaturalist.org/v1/taxa"

if "areas" not in st.session_state:
    st.session_state.areas = {}
if "active_area" not in st.session_state:
    st.session_state.active_area = None
if "analysis_df" not in st.session_state:
    st.session_state.analysis_df = None
if "analysis_meta" not in st.session_state:
    st.session_state.analysis_meta = {}

st.title("🌿 Mijn Biodiversiteit")
st.caption("Teken een tuin, park, natuurgebied of ander onderzoeksgebied en analyseer iNaturalist-waarnemingen.")

checkpoint("UI_HEADER_READY")

tab_areas, tab_dashboard = st.tabs(["🗺️ Mijn gebieden", "📊 Dashboard"])

with tab_areas:
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
            username = st.text_input("iNaturalist-gebruikersnaam", value="jeanpaulboerekamps")
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

        if st.button("🔎 Analyseer dit gebied", type="primary"):
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

                if mode == "Mijn waarnemingen":
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

                    st.write("Taxonomische indeling bepalen…")
                    checkpoint("FAST_TAXONOMY_START")

                    # Alleen de vooroudertaxa verzamelen die daadwerkelijk nodig zijn
                    # voor de waarnemingen binnen het getekende gebied.
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

                        out.append({
                            "datum": o.get("observed_on"),
                            "Nederlandse naam": nl_name,
                            "wetenschappelijke naam": taxon.get("name"),
                            "soortgroep": taxon.get("iconic_taxon_name") or "Onbekend",
                            "orde": rank_from_ancestors(taxon, taxon_lookup, "order"),
                            "orde_wetenschappelijk": rank_from_ancestors(
                                taxon, taxon_lookup, "order", scientific=True
                            ),
                            "familie": rank_from_ancestors(taxon, taxon_lookup, "family"),
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
                    }

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

            st.subheader("Nieuwe soorten per kwartaal")
            first_seen = (
                df.dropna(subset=["wetenschappelijke naam"])
                .sort_values("datum")
                .drop_duplicates("wetenschappelijke naam", keep="first")
                [["datum", "wetenschappelijke naam"]]
            )
            first_seen["jaar"] = first_seen["datum"].dt.year.astype(int)
            first_seen["kwartaal"] = first_seen["datum"].dt.quarter.astype(int)

            new_q = (
                first_seen.groupby(["jaar", "kwartaal"])
                .size()
                .reset_index(name="nieuwe soorten")
            )
            new_q["periode"] = new_q["jaar"].astype(str) + " Q" + new_q["kwartaal"].astype(str)

            st.plotly_chart(
                px.bar(
                    new_q,
                    x="periode",
                    y="nieuwe soorten",
                    labels={
                        "periode": "Kwartaal",
                        "nieuwe soorten": "Aantal nieuwe soorten",
                    },
                ),
                use_container_width=True,
            )

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
    "iPad/web prototype v0.13 · snelle taxonomie + interactieve heatmap · "
    "geen iNaturalist-analyse vóór je op ‘Analyseer dit gebied’ drukt."
)

checkpoint("APP_END")
