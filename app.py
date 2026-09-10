from datetime import date
import json

import folium
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point, shape
from streamlit_folium import st_folium

st.set_page_config(page_title="Mijn Biodiversiteit", page_icon="🌿", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 4rem; max-width: 1200px;}
div.stButton > button, div.stDownloadButton > button {
    min-height: 52px; font-size: 1.05rem; border-radius: 12px; width: 100%;
}
[data-testid="stMetric"] {padding: 12px; border: 1px solid rgba(128,128,128,.25); border-radius: 14px;}
h1 {font-size: clamp(1.8rem, 5vw, 2.8rem);}
@media (max-width: 768px) {
  .block-container {padding-left: .8rem; padding-right: .8rem;}
}
</style>
""", unsafe_allow_html=True)

API = "https://api.inaturalist.org/v1/observations"
TAXA_API = "https://api.inaturalist.org/v1/taxa"

if "areas" not in st.session_state:
    st.session_state.areas = {}
if "active_area" not in st.session_state:
    st.session_state.active_area = None

st.title("🌿 Mijn Biodiversiteit")
st.caption("Teken een tuin, park, natuurgebied of ander onderzoeksgebied en bekijk de iNaturalist-waarnemingen.")

tab_areas, tab_dashboard = st.tabs(["🗺️ Mijn gebieden", "📊 Dashboard"])

with tab_areas:
    st.subheader("Nieuw of bestaand gebied")

    if st.session_state.areas:
        names = list(st.session_state.areas)
        chosen = st.selectbox("Opgeslagen gebieden", ["— kies —"] + names)
        if chosen != "— kies —":
            st.session_state.active_area = chosen
            st.success(f"Actief gebied: {chosen}")

    area_name = st.text_input("Naam van het gebied", placeholder="Bijvoorbeeld: Mijn tuin")
    st.write("**Teken hieronder de grens.** Gebruik het polygoon- of rechthoek-icoon links op de kaart.")

    center = [51.93, 4.84]
    zoom = 11
    if st.session_state.active_area and st.session_state.active_area in st.session_state.areas:
        existing = shape(st.session_state.areas[st.session_state.active_area])
        c = existing.centroid
        center, zoom = [c.y, c.x], 16

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
    if st.session_state.active_area and st.session_state.active_area in st.session_state.areas:
        folium.GeoJson(
            st.session_state.areas[st.session_state.active_area],
            style_function=lambda x: {"weight": 3, "fillOpacity": 0.12},
        ).add_to(m)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False, "circle": False, "circlemarker": False, "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True},
            "rectangle": True,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    map_state = st_folium(m, height=560, use_container_width=True, key="draw_map")
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
    with c2:
        if st.button("🗑️ Actief gebied verwijderen"):
            n = st.session_state.active_area
            if n and n in st.session_state.areas:
                del st.session_state.areas[n]
                st.session_state.active_area = None
                st.rerun()

    if st.session_state.areas:
        export = json.dumps(
            {"type": "FeatureCollection",
             "features": [{"type": "Feature", "properties": {"name": n}, "geometry": g}
                          for n, g in st.session_state.areas.items()]},
            ensure_ascii=False, indent=2
        )
        st.download_button("⬇️ Gebieden bewaren als GeoJSON", export, "mijn_gebieden.geojson", "application/geo+json")

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_taxon(taxon_id):
    try:
        r = requests.get(f"{TAXA_API}/{int(taxon_id)}", params={"locale":"nl","preferred_place_id":7506}, timeout=20)
        r.raise_for_status()
        items = r.json().get("results", [])
        return items[0] if items else {}
    except Exception:
        return {}

def rank_name(taxon_record, wanted_rank):
    if taxon_record.get("rank") == wanted_rank:
        return taxon_record.get("preferred_common_name") or taxon_record.get("name")
    for anc in reversed(taxon_record.get("ancestors") or []):
        if anc.get("rank") == wanted_rank:
            return anc.get("preferred_common_name") or anc.get("name")
    return None

def pie_chart(data, names, values, title):
    fig = px.pie(data, names=names, values=values, hole=0.35, title=title)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(legend_title_text="", margin=dict(t=60,b=20,l=20,r=20))
    st.plotly_chart(fig, use_container_width=True)

with tab_dashboard:
    active = st.session_state.active_area
    if not active or active not in st.session_state.areas:
        st.info("Maak of kies eerst een gebied in ‘Mijn gebieden’.")
        st.stop()

    st.subheader(active)
    with st.expander("Filters", expanded=True):
        username = st.text_input("iNaturalist-gebruikersnaam", value="jeanpaulboerekamps")
        mode = st.segmented_control(
            "Waarnemers", ["Mijn waarnemingen", "Alle waarnemers"], default="Mijn waarnemingen"
        )
        c1, c2 = st.columns(2)
        with c1:
            start_year = st.number_input("Vanaf", 2000, date.today().year, 2020)
        with c2:
            end_year = st.number_input("Tot en met", 2000, date.today().year, date.today().year)
        quality = st.selectbox("Kwaliteit", ["Alle", "Research grade", "Needs ID", "Casual"])

    @st.cache_data(ttl=1800, show_spinner=False)
    def fetch(params_tuple):
        params = dict(params_tuple)
        rows, page, total = [], 1, None
        while True:
            params.update(page=page, per_page=200)
            r = requests.get(API, params=params, timeout=30)
            r.raise_for_status()
            payload = r.json()
            total = payload.get("total_results", 0) if total is None else total
            batch = payload.get("results", [])
            rows.extend(batch)
            if len(batch) < 200 or page * 200 >= min(total, 10000):
                return rows, total
            page += 1

    if st.button("🔎 Analyseer dit gebied", type="primary"):
        geom = st.session_state.areas[active]
        poly = shape(geom)
        minx, miny, maxx, maxy = poly.bounds
        params = {
            "swlat": miny, "swlng": minx, "nelat": maxy, "nelng": maxx,
            "d1": f"{int(start_year)}-01-01", "d2": f"{int(end_year)}-12-31",
            "order_by": "observed_on", "order": "desc",
        }
        if mode == "Mijn waarnemingen":
            params["user_id"] = username.strip()
        qp = {"Alle": None, "Research grade": "research", "Needs ID": "needs_id", "Casual": "casual"}[quality]
        if qp:
            params["quality_grade"] = qp

        with st.spinner("Waarnemingen ophalen…"):
            try:
                raw, total = fetch(tuple(sorted(params.items())))
            except Exception as e:
                st.error(f"iNaturalist kon niet worden bereikt: {e}")
                st.stop()

        taxon_ids = {(o.get("taxon") or {}).get("id") for o in raw if (o.get("taxon") or {}).get("id")}
        with st.spinner("Nederlandse namen en taxonomie aanvullen…"):
            taxon_info = {tid: fetch_taxon(tid) for tid in taxon_ids}

        out = []
        for o in raw:
            geo=o.get("geojson")
            coords=geo.get("coordinates") if geo else None
            if not coords or not poly.covers(Point(coords[0], coords[1])):
                continue
            taxon=o.get("taxon") or {}
            full=taxon_info.get(taxon.get("id"), {}) or taxon
            out.append({
                "datum": o.get("observed_on"),
                "Nederlandse naam": full.get("preferred_common_name") or taxon.get("preferred_common_name") or taxon.get("name") or "Onbekend",
                "wetenschappelijke naam": taxon.get("name"),
                "soortgroep": taxon.get("iconic_taxon_name") or "Onbekend",
                "orde": rank_name(full, "order"),
                "familie": rank_name(full, "family"),
            })
        df=pd.DataFrame(out)
        if df.empty:
            st.warning("Geen exact binnen dit gebied gelegen waarnemingen gevonden.")
            st.stop()
        df["datum"]=pd.to_datetime(df["datum"], errors="coerce")
        df=df.dropna(subset=["datum"])
        df["jaar"]=df["datum"].dt.year.astype(int)
        df["maand"]=df["datum"].dt.month.astype(int)
        df["kwartaal"]=df["datum"].dt.quarter.astype(int)

        a,b,c,d=st.columns(4)
        a.metric("Waarnemingen", len(df))
        b.metric("Taxa", df["wetenschappelijke naam"].nunique())
        c.metric("Soortgroepen", df["soortgroep"].nunique())
        d.metric("Jaren", df["jaar"].nunique())

        st.subheader("Samenstelling per soortgroep")
        gc=df["soortgroep"].fillna("Onbekend").value_counts().rename_axis("soortgroep").reset_index(name="waarnemingen")
        pie_chart(gc,"soortgroep","waarnemingen","Waarnemingen per soortgroep")

        insects=df[df["soortgroep"].eq("Insecta")].copy()
        if not insects.empty:
            st.subheader("Insecten per orde")
            oc=insects["orde"].fillna("Onbekende orde").value_counts().rename_axis("orde").reset_index(name="waarnemingen")
            pie_chart(oc,"orde","waarnemingen","Insecten uitgesplitst naar orde")
            leps=insects[insects["orde"].fillna("").str.lower().isin(["lepidoptera","vlinders","vlinders en motten"])].copy()
            if not leps.empty:
                st.subheader("Vlinders per familie")
                fc=leps["familie"].fillna("Onbekende familie").value_counts().rename_axis("familie").reset_index(name="waarnemingen")
                pie_chart(fc,"familie","waarnemingen","Vlinders uitgesplitst naar familie")

        st.subheader("Waarnemingen en taxa per jaar")
        yearly=df.groupby("jaar").agg(waarnemingen=("Nederlandse naam","size"),taxa=("wetenschappelijke naam","nunique")).reset_index()
        fy=px.bar(yearly,x="jaar",y=["waarnemingen","taxa"],barmode="group",labels={"value":"Aantal","jaar":"Jaar","variable":""})
        fy.update_layout(legend_title_text="")
        st.plotly_chart(fy,use_container_width=True)

        st.subheader("Gemiddeld per kalendermaand")
        years=list(range(int(start_year),int(end_year)+1))
        idx=pd.MultiIndex.from_product([years,range(1,13)],names=["jaar","maand"])
        obs=df.groupby(["jaar","maand"]).size().reindex(idx,fill_value=0)
        taxa=df.groupby(["jaar","maand"])["wetenschappelijke naam"].nunique().reindex(idx,fill_value=0)
        monthly=pd.DataFrame({"waarnemingen":obs.groupby("maand").mean(),"taxa":taxa.groupby("maand").mean()}).reset_index()
        names={1:"Jan",2:"Feb",3:"Mrt",4:"Apr",5:"Mei",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Okt",11:"Nov",12:"Dec"}
        monthly["kalendermaand"]=monthly["maand"].map(names)
        fm=px.bar(monthly,x="kalendermaand",y=["waarnemingen","taxa"],barmode="group",labels={"value":"Gemiddeld aantal","kalendermaand":"Maand","variable":""})
        fm.update_layout(legend_title_text="")
        st.plotly_chart(fm,use_container_width=True)

        st.subheader("Nieuwe soorten per kwartaal")
        first=df.dropna(subset=["wetenschappelijke naam"]).sort_values("datum").drop_duplicates("wetenschappelijke naam",keep="first")[["datum","wetenschappelijke naam"]]
        first["jaar"]=first["datum"].dt.year.astype(int)
        first["kwartaal"]=first["datum"].dt.quarter.astype(int)
        nq=first.groupby(["jaar","kwartaal"]).size().reset_index(name="nieuwe soorten")
        nq["periode"]=nq["jaar"].astype(str)+" Q"+nq["kwartaal"].astype(str)
        st.plotly_chart(px.bar(nq,x="periode",y="nieuwe soorten",labels={"periode":"Kwartaal","nieuwe soorten":"Aantal nieuwe soorten"}),use_container_width=True)

        st.subheader("Meest waargenomen soorten")
        top=df.groupby(["Nederlandse naam","wetenschappelijke naam"],dropna=False).size().reset_index(name="waarnemingen").sort_values("waarnemingen",ascending=False).head(30)
        st.dataframe(top,use_container_width=True,hide_index=True)

        if total > 10000:
            st.warning("De zoekopdracht bevat meer dan 10.000 resultaten. Verklein gebied of periode voor volledige dekking.")

st.caption("iPad-prototype v0.2 · Gebieden blijven tijdens de actieve sessie beschikbaar en kunnen als GeoJSON worden geëxporteerd.")
