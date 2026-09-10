from datetime import date
import json

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Mijn Biodiversiteit",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1rem; padding-bottom: 4rem; max-width: 1200px;}
div.stButton > button, div.stDownloadButton > button {
    min-height: 52px; font-size: 1.05rem; border-radius: 12px; width: 100%;
}
[data-testid="stMetric"] {
    padding: 12px;
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
}
h1 {font-size: clamp(1.8rem, 5vw, 2.8rem);}
@media (max-width: 768px) {
  .block-container {padding-left: .8rem; padding-right: .8rem;}
}
</style>
""",
    unsafe_allow_html=True,
)

API = "https://api.inaturalist.org/v1/observations"
PER_PAGE = 200
MAX_RESULTS = 10_000

if "areas" not in st.session_state:
    st.session_state.areas = {}

if "active_area" not in st.session_state:
    st.session_state.active_area = None

st.title("🌿 Mijn Biodiversiteit")
st.caption(
    "Teken een tuin, park, natuurgebied of ander onderzoeksgebied "
    "en bekijk de iNaturalist-waarnemingen."
)

tab_areas, tab_dashboard = st.tabs(["🗺️ Mijn gebieden", "📊 Dashboard"])


with tab_areas:
    st.subheader("Nieuw of bestaand gebied")

    if st.session_state.areas:
        names = list(st.session_state.areas)
        chosen = st.selectbox("Opgeslagen gebieden", ["— kies —"] + names)
        if chosen != "— kies —":
            st.session_state.active_area = chosen
            st.success(f"Actief gebied: {chosen}")

    area_name = st.text_input(
        "Naam van het gebied",
        placeholder="Bijvoorbeeld: Mijn tuin",
    )

    st.write(
        "**Teken hieronder de grens.** Gebruik het polygoon- "
        "of rechthoek-icoon links op de kaart."
    )

    center = [51.93, 4.84]
    zoom = 11

    if (
        st.session_state.active_area
        and st.session_state.active_area in st.session_state.areas
    ):
        existing = shape(
            st.session_state.areas[st.session_state.active_area]
        )
        c = existing.centroid
        center, zoom = [c.y, c.x], 16

    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    if (
        st.session_state.active_area
        and st.session_state.active_area in st.session_state.areas
    ):
        folium.GeoJson(
            st.session_state.areas[st.session_state.active_area],
            style_function=lambda x: {
                "weight": 3,
                "fillOpacity": 0.12,
            },
        ).add_to(m)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polygon": {
                "allowIntersection": False,
                "showArea": True,
            },
            "rectangle": True,
        },
        edit_options={
            "edit": True,
            "remove": True,
        },
    ).add_to(m)

    map_state = st_folium(
        m,
        height=560,
        use_container_width=True,
        key="draw_map",
    )

    drawings = map_state.get("all_drawings") or []
    newest_geom = (
        drawings[-1].get("geometry") if drawings else None
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button("💾 Gebied bewaren", type="primary"):
            if not area_name.strip():
                st.error("Geef het gebied eerst een naam.")
            elif not newest_geom:
                st.error("Teken eerst een gebied op de kaart.")
            else:
                try:
                    test_geom = shape(newest_geom)
                except Exception as e:
                    st.error(f"Het getekende gebied is ongeldig: {e}")
                else:
                    if test_geom.is_empty or not test_geom.is_valid:
                        st.error(
                            "Het getekende gebied is leeg of geometrisch ongeldig. "
                            "Teken het gebied opnieuw."
                        )
                    else:
                        st.session_state.areas[
                            area_name.strip()
                        ] = newest_geom
                        st.session_state.active_area = (
                            area_name.strip()
                        )
                        st.success(
                            f"'{area_name.strip()}' is voor deze sessie opgeslagen."
                        )

    with c2:
        if st.button("🗑️ Actief gebied verwijderen"):
            n = st.session_state.active_area
            if n and n in st.session_state.areas:
                del st.session_state.areas[n]
                st.session_state.active_area = None
                st.rerun()

    if st.session_state.areas:
        export = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": n},
                        "geometry": g,
                    }
                    for n, g in st.session_state.areas.items()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

        st.download_button(
            "⬇️ Gebieden bewaren als GeoJSON",
            export,
            "mijn_gebieden.geojson",
            "application/geo+json",
        )


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_observations(params_tuple, geometry_json):
    """
    Haal iNaturalist-resultaten per pagina op en verwerk iedere pagina direct.

    Belangrijk: volledige API-resultaten worden niet meer allemaal in het
    geheugen bewaard. Alleen de compacte rijen die exact binnen het getekende
    gebied liggen worden opgeslagen.
    """
    params = dict(params_tuple)
    poly = shape(json.loads(geometry_json))

    if poly.is_empty or not poly.is_valid:
        raise ValueError("Het onderzoeksgebied is geometrisch ongeldig.")

    rows = []
    page = 1
    total = None
    examined = 0

    with requests.Session() as session:
        while examined < MAX_RESULTS:
            request_params = {
                **params,
                "page": page,
                "per_page": PER_PAGE,
            }

            response = session.get(
                API,
                params=request_params,
                timeout=(10, 45),
            )
            response.raise_for_status()
            payload = response.json()

            if total is None:
                total = int(payload.get("total_results") or 0)

            batch = payload.get("results") or []
            if not batch:
                break

            for o in batch:
                examined += 1

                geo = o.get("geojson") or {}
                coords = geo.get("coordinates")

                if (
                    not isinstance(coords, (list, tuple))
                    or len(coords) < 2
                ):
                    continue

                try:
                    point = Point(float(coords[0]), float(coords[1]))
                except (TypeError, ValueError):
                    continue

                if not poly.covers(point):
                    continue

                taxon = o.get("taxon") or {}
                user = o.get("user") or {}
                observation_id = o.get("id")

                rows.append(
                    {
                        "datum": o.get("observed_on"),
                        "soort": (
                            taxon.get("preferred_common_name")
                            or taxon.get("name")
                            or "Onbekend"
                        ),
                        "wetenschappelijke naam": taxon.get("name"),
                        "soortgroep": (
                            taxon.get("iconic_taxon_name")
                            or "Onbekend"
                        ),
                        "kwaliteit": o.get("quality_grade"),
                        "waarnemer": user.get("login"),
                        "url": (
                            f"https://www.inaturalist.org/observations/"
                            f"{observation_id}"
                            if observation_id
                            else None
                        ),
                    }
                )

                if examined >= MAX_RESULTS:
                    break

            if len(batch) < PER_PAGE:
                break

            if total is not None and page * PER_PAGE >= total:
                break

            page += 1

    return rows, (total or 0), examined


with tab_dashboard:
    active = st.session_state.active_area

    if not active or active not in st.session_state.areas:
        st.info("Maak of kies eerst een gebied in ‘Mijn gebieden’.")
    else:
        st.subheader(active)

        with st.expander("Filters", expanded=True):
            username = st.text_input(
                "iNaturalist-gebruikersnaam",
                value="jeanpaulboerekamps",
            )

            mode = st.segmented_control(
                "Waarnemers",
                ["Mijn waarnemingen", "Alle waarnemers"],
                default="Mijn waarnemingen",
            )

            c1, c2 = st.columns(2)

            with c1:
                start_year = st.number_input(
                    "Vanaf",
                    2000,
                    date.today().year,
                    2020,
                )

            with c2:
                end_year = st.number_input(
                    "Tot en met",
                    2000,
                    date.today().year,
                    date.today().year,
                )

            quality = st.selectbox(
                "Kwaliteit",
                [
                    "Alle",
                    "Research grade",
                    "Needs ID",
                    "Casual",
                ],
            )

        if st.button("🔎 Analyseer dit gebied", type="primary"):
            if int(start_year) > int(end_year):
                st.error("'Vanaf' kan niet later zijn dan 'Tot en met'.")
                st.stop()

            if mode == "Mijn waarnemingen" and not username.strip():
                st.error(
                    "Vul een iNaturalist-gebruikersnaam in."
                )
                st.stop()

            geom = st.session_state.areas[active]

            try:
                poly = shape(geom)
            except Exception as e:
                st.error(
                    f"Het opgeslagen gebied kon niet worden gelezen: {e}"
                )
                st.stop()

            if poly.is_empty or not poly.is_valid:
                st.error(
                    "Het opgeslagen gebied is ongeldig. "
                    "Verwijder het en teken het opnieuw."
                )
                st.stop()

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

            geometry_json = json.dumps(
                geom,
                sort_keys=True,
                separators=(",", ":"),
            )

            with st.spinner(
                "Waarnemingen ophalen en binnen het gebied filteren…"
            ):
                try:
                    rows, total, examined = fetch_observations(
                        tuple(sorted(params.items())),
                        geometry_json,
                    )
                except requests.Timeout:
                    st.error(
                        "iNaturalist reageerde niet op tijd. "
                        "Probeer het opnieuw of verklein periode/gebied."
                    )
                    st.stop()
                except requests.HTTPError as e:
                    status = (
                        e.response.status_code
                        if e.response is not None
                        else "onbekend"
                    )
                    st.error(
                        f"iNaturalist gaf een HTTP-fout ({status}). "
                        "Probeer het later opnieuw."
                    )
                    st.stop()
                except requests.RequestException as e:
                    st.error(
                        f"Netwerkfout bij iNaturalist: {e}"
                    )
                    st.stop()
                except Exception as e:
                    st.exception(e)
                    st.stop()

            df = pd.DataFrame(rows)

            if df.empty:
                st.warning(
                    "Geen exact binnen dit gebied gelegen "
                    "waarnemingen gevonden."
                )
                if total:
                    st.caption(
                        f"iNaturalist vond {total:,} resultaten in de "
                        "omliggende rechthoek; geen daarvan viel exact "
                        "binnen het getekende gebied."
                    )
                st.stop()

            df["datum"] = pd.to_datetime(
                df["datum"],
                errors="coerce",
            )
            df["jaar"] = df["datum"].dt.year

            a, b, c, d = st.columns(4)
            a.metric("Waarnemingen", len(df))
            b.metric(
                "Taxa",
                df["wetenschappelijke naam"].nunique(),
            )
            c.metric(
                "Soortgroepen",
                df["soortgroep"].nunique(),
            )
            d.metric(
                "Jaren",
                df["jaar"].nunique(),
            )

            if total > MAX_RESULTS:
                st.warning(
                    f"iNaturalist vond {total:,} resultaten in de "
                    f"omliggende rechthoek. Om de app stabiel te houden "
                    f"zijn maximaal {MAX_RESULTS:,} resultaten onderzocht. "
                    "Verklein het gebied of de periode voor volledige dekking."
                )
            elif examined < total:
                st.caption(
                    f"{examined:,} van {total:,} resultaten onderzocht."
                )

            st.subheader("Soortgroepen")
            st.bar_chart(
                df["soortgroep"].value_counts()
            )

            st.subheader("Ontwikkeling")
            yearly = (
                df.dropna(subset=["jaar"])
                .groupby("jaar")
                .agg(
                    waarnemingen=("soort", "size"),
                    taxa=(
                        "wetenschappelijke naam",
                        "nunique",
                    ),
                )
            )
            if yearly.empty:
                st.info(
                    "Er zijn geen bruikbare datums voor de tijdreeks."
                )
            else:
                st.line_chart(yearly)

            st.subheader("Meest waargenomen")
            top = (
                df.groupby(
                    ["soort", "wetenschappelijke naam"],
                    dropna=False,
                )
                .size()
                .reset_index(name="waarnemingen")
            )
            st.dataframe(
                top.sort_values(
                    "waarnemingen",
                    ascending=False,
                ).head(30),
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Alle waarnemingen")
            st.dataframe(
                df.sort_values(
                    "datum",
                    ascending=False,
                    na_position="last",
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "url": st.column_config.LinkColumn(
                        "iNaturalist"
                    )
                },
            )

            safe_name = active.replace(" ", "_")
            st.download_button(
                "⬇️ Download als CSV",
                df.to_csv(index=False).encode("utf-8"),
                f"{safe_name}_waarnemingen.csv",
                "text/csv",
            )

st.caption(
    "iPad-prototype · Gebieden blijven tijdens de actieve sessie "
    "beschikbaar en kunnen als GeoJSON worden geëxporteerd."
)
