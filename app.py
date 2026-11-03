"""
Observatorio de Analítica Económica y Social por Departamentos en Colombia
==========================================================================
Datos REALES desde el Portal de Datos Abiertos de Colombia (datos.gov.co):
  - PIB departamental (agregado de actividades, precios corrientes)
  - Homicidios (conteo anual por departamento, MinDefensa)
  - Cobertura neta educación media (MEN, entidades territoriales certificadas departamentales)

Indicadores sin serie abierta estable vía API (IPM, desempleo, inversión DNP agregada):
  se muestran como no disponibles hasta cargar anexos oficiales (sin inventar cifras).
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import unicodedata
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Observatorio Económico-Social | Colombia (datos reales)",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0F172A !important; }
    [data-testid="stSidebar"] > div:first-child { background-color: #0F172A !important; }
    [data-testid="stSidebar"] label { color: #94A3B8 !important; font-weight: 600 !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stMarkdown { color: #E2E8F0 !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #1E293B !important; border: 1px solid #475569 !important;
        border-radius: 8px !important; color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div { color: #F8FAFC !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #F8FAFC !important; }
    div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li {
        background-color: #1E293B !important; color: #F8FAFC !important;
    }
    div[data-baseweb="popover"] li span { color: #F8FAFC !important; }
    div[data-baseweb="popover"] li:hover { background-color: #334155 !important; }
    [data-testid="stSidebar"] .stCaption { color: #94A3B8 !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #1E293B !important; border: 1px solid #334155 !important; border-radius: 8px;
    }
    .hero-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 55%, #1E3A5F 100%);
        border-radius: 16px; padding: 28px 32px; margin-bottom: 20px; color: #F8FAFC;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.35);
    }
    .hero-title { font-size: 1.7rem; font-weight: 800; margin: 0 0 6px 0; color: #FFFFFF !important; }
    .hero-subtitle { font-size: 1.02rem; color: #94A3B8; margin: 0 0 16px 0; line-height: 1.45; }
    .hero-meta { display: flex; flex-wrap: wrap; gap: 10px; }
    .hero-chip {
        background: rgba(37, 99, 235, 0.28); border: 1px solid rgba(37, 99, 235, 0.5);
        color: #93C5FD; font-size: 0.8rem; font-weight: 600; padding: 6px 14px; border-radius: 9999px;
    }
    .hero-chip-teal {
        background: rgba(13, 148, 136, 0.28); border: 1px solid rgba(13, 148, 136, 0.5); color: #5EEAD4;
    }
    .kpi-card {
        background: #FFF; border-left: 5px solid #2563EB; padding: 18px 22px; border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07); margin-bottom: 14px;
    }
    .kpi-title { font-size: 0.78rem; color: #64748B; font-weight: 600; text-transform: uppercase; margin: 0; }
    .kpi-value { font-size: 1.55rem; color: #0F172A; font-weight: 700; margin: 6px 0 2px 0; }
    .kpi-subtitle { font-size: 0.78rem; font-weight: 500; margin: 0; }
    .kpi-positive { color: #059669; }
    .kpi-negative { color: #DC2626; }
    .kpi-neutral { color: #64748B; }
    .kpi-na { color: #94A3B8; }
    h1, h2, h3 { color: #0F172A !important; font-weight: 700 !important; }
    .stTabs [data-baseweb="tab"] { background: #E2E8F0; border-radius: 8px 8px 0 0; padding: 10px 18px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #2563EB !important; color: white !important; }
    .source-badge {
        display: inline-block; background: #E0F2FE; color: #0369A1; font-size: 0.7rem;
        padding: 2px 8px; border-radius: 9999px; font-weight: 600;
    }
    .info-box {
        background: #FFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 16px 18px; margin-bottom: 10px;
    }
    .footer {
        text-align: center; color: #64748B; font-size: 0.8rem; padding: 24px 0 8px 0;
        border-top: 1px solid #E2E8F0; margin-top: 36px;
    }
    .warn-box {
        background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 12px 16px; border-radius: 8px; margin: 12px 0;
        color: #92400E; font-size: 0.9rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# METADATOS (solo variables con fuente real o explícitamente no disponibles)
# =============================================================================
METADATA_VARIABLES: Dict[str, Dict] = {
    "pib_mil_millones": {
        "nombre": "PIB Departamental (Miles de Millones COP)",
        "significado": "Suma del valor agregado por actividades económicas + impuestos a precios corrientes, por departamento.",
        "impacto": "Tamaño de la economía regional y base productiva/tributaria.",
        "fuente": "datos.gov.co dataset kgyi-qc7j (PIB Departamental con proyección; agregado de actividades)",
        "unidad": "Miles de millones de pesos corrientes",
        "mejor_cuando": "alto",
        "formato": "{:,.1f}",
        "disponible": True,
    },
    "homicidios_cantidad": {
        "nombre": "Homicidios (número de víctimas)",
        "significado": "Conteo anual de víctimas de homicidio intencional registradas por departamento.",
        "impacto": "Indicador de seguridad ciudadana. Nota: la tasa por 100.000 hab. requiere proyecciones de población DANE no expuestas en esta API.",
        "fuente": "MinDefensa / datos.gov.co resource m8fd-ahd9 (HOMICIDIO)",
        "unidad": "Número de víctimas",
        "mejor_cuando": "bajo",
        "formato": "{:,.0f}",
        "disponible": True,
    },
    "cobertura_educacion_media": {
        "nombre": "Cobertura Neta Educación Media (%)",
        "significado": "Relación entre estudiantes de media en edad teórica (15–16) y la población de esa edad. Solo ETC departamentales.",
        "impacto": "Formación de capital humano y acceso a educación superior.",
        "fuente": "MEN / datos.gov.co resource sras-4t5p (estadísticas preescolar, básica y media por ETC)",
        "unidad": "%",
        "mejor_cuando": "alto",
        "formato": "{:.1f}%",
        "disponible": True,
    },
    "ipm_porcentaje": {
        "nombre": "Índice de Pobreza Multidimensional (%)",
        "significado": "Incidencia de pobreza multidimensional (metodología Alkire-Foster / DANE-ECV).",
        "impacto": "Privaciones simultáneas en salud, educación, trabajo y vivienda.",
        "fuente": "DANE – anexos departamentales IPM (no hay serie histórica completa vía API pública estable)",
        "unidad": "%",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
        "disponible": False,
    },
    "tasa_desempleo": {
        "nombre": "Tasa de Desempleo (%)",
        "significado": "Porcentaje de la fuerza de trabajo en búsqueda activa sin empleo (GEIH).",
        "impacto": "Salud del mercado laboral regional.",
        "fuente": "DANE – GEIH / boletines departamentales (anexos XLS; sin API abierta completa para 33 entidades)",
        "unidad": "%",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
        "disponible": False,
    },
    "inversion_dnp": {
        "nombre": "Inversión Pública Ejecutada (Millones COP)",
        "significado": "Recursos públicos ejecutados en proyectos de inversión territorial.",
        "impacto": "Palanca de política fiscal e infraestructura regional.",
        "fuente": "DNP TerriData / Mapa Inversiones (proyectos a nivel BPIN; agregación anual departamental no estandarizada en API abierta)",
        "unidad": "Millones de pesos",
        "mejor_cuando": "alto",
        "formato": "{:,.0f}",
        "disponible": False,
    },
}

VARIABLES_DISPONIBLES = [k for k, v in METADATA_VARIABLES.items() if v["disponible"]]
VARIABLES_ORDEN = list(METADATA_VARIABLES.keys())

DEPARTAMENTOS_CANONICOS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.",
    "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare",
    "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca",
    "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena",
    "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío",
    "Risaralda", "San Andrés y Providencia", "Santander", "Sucre",
    "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
]


def quitar_acentos(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_nombre(nombre: str) -> str:
    n = quitar_acentos(str(nombre)).upper().strip()
    for ch in [".", ",", "(", ")", "-"]:
        n = n.replace(ch, " ")
    while "  " in n:
        n = n.replace("  ", " ")
    n = n.strip()
    # quitar sufijo ETC
    if n.endswith(" ETC"):
        n = n[:-4].strip()
    aliases = {
        "BOGOTA DC": "BOGOTA D C",
        "BOGOTA D C": "BOGOTA D C",
        "BOGOTA": "BOGOTA D C",
        "DISTRITO CAPITAL": "BOGOTA D C",
        "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES Y PROVIDENCIA": "SAN ANDRES Y PROVIDENCIA",
        "NORTE SANTANDER": "NORTE DE SANTANDER",
        "VALLE": "VALLE DEL CAUCA",
        "ATLANTICO": "ATLANTICO",
        "BOLIVAR": "BOLIVAR",
        "BOYACA": "BOYACA",
        "CAQUETA": "CAQUETA",
        "CORDOBA": "CORDOBA",
        "CHOCO": "CHOCO",
        "GUAINIA": "GUAINIA",
        "NARINO": "NARINO",
        "QUINDIO": "QUINDIO",
        "VAUPES": "VAUPES",
    }
    return aliases.get(n, n)


# mapa norm -> nombre canónico de la app
NORM_A_CANONICO = {normalizar_nombre(d): d for d in DEPARTAMENTOS_CANONICOS}


def a_canonico(nombre: str) -> Optional[str]:
    return NORM_A_CANONICO.get(normalizar_nombre(nombre))


# =============================================================================
# CARGA DE DATOS REALES (datos.gov.co SODA API)
# =============================================================================
SODA_BASE = "https://www.datos.gov.co/resource"


@st.cache_data(show_spinner="Descargando PIB departamental (datos.gov.co)…", ttl=3600)
def cargar_pib() -> pd.DataFrame:
    """
    Dataset kgyi-qc7j: PIB por actividad. Se agrega la suma de actividades
    a precios corrientes por departamento-año.
    """
    url = f"{SODA_BASE}/kgyi-qc7j.json"
    params = {
        "$where": "tipo_de_precios='PIB a precios corrientes'",
        "$select": "a_o,departamento,sum(valor_miles_de_millones_de) as pib",
        "$group": "a_o,departamento",
        "$limit": 50000,
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        return pd.DataFrame(columns=["departamento", "año", "pib_mil_millones"])
    df["año"] = pd.to_numeric(df["a_o"], errors="coerce").astype("Int64")
    df["pib_mil_millones"] = pd.to_numeric(df["pib"], errors="coerce")
    df["departamento"] = df["departamento"].map(a_canonico)
    df = df.dropna(subset=["departamento", "año", "pib_mil_millones"])
    return df[["departamento", "año", "pib_mil_millones"]].copy()


@st.cache_data(show_spinner="Descargando homicidios (MinDefensa / datos.gov.co)…", ttl=3600)
def cargar_homicidios() -> pd.DataFrame:
    """
    resource m8fd-ahd9: registros de homicidio. Agregación anual por departamento.
    """
    url = f"{SODA_BASE}/m8fd-ahd9.json"
    # Paginación SODA ($limit máximo típico 50000)
    frames = []
    offset = 0
    page = 50000
    while True:
        params = {
            "$select": "departamento,date_trunc_y(fecha_hecho) as anio,sum(cantidad) as total",
            "$group": "departamento,anio",
            "$limit": page,
            "$offset": offset,
        }
        r = requests.get(url, params=params, timeout=90)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        if len(batch) < page:
            break
        offset += page
        if offset > 200000:  # safety
            break
    if not frames:
        return pd.DataFrame(columns=["departamento", "año", "homicidios_cantidad"])
    df = pd.concat(frames, ignore_index=True)
    df["año"] = pd.to_datetime(df["anio"], errors="coerce").dt.year
    df["homicidios_cantidad"] = pd.to_numeric(df["total"], errors="coerce")
    df["departamento"] = df["departamento"].map(a_canonico)
    df = df.dropna(subset=["departamento", "año", "homicidios_cantidad"])
    return (
        df.groupby(["departamento", "año"], as_index=False)["homicidios_cantidad"]
        .sum()
    )


@st.cache_data(show_spinner="Descargando cobertura educativa (MEN / datos.gov.co)…", ttl=3600)
def cargar_cobertura_media() -> pd.DataFrame:
    """
    resource sras-4t5p: indicadores por ETC. Se usan solo filas departamentales
    (nombre termina en '(ETC)'), no municipios certificados.
    """
    url = f"{SODA_BASE}/sras-4t5p.json"
    params = {
        "$select": "ano,nombre_etc,cobertura_neta_media",
        "$where": "nombre_etc like '%(ETC)%'",
        "$limit": 50000,
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        return pd.DataFrame(columns=["departamento", "año", "cobertura_educacion_media"])
    df["año"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
    # valores vienen como proporción (0–1) o a veces ya en %; MEN doc dice export *100
    val = pd.to_numeric(df["cobertura_neta_media"], errors="coerce")
    # si la mediana es < 2, asumir proporción
    if val.median(skipna=True) is not None and val.median(skipna=True) <= 2:
        val = val * 100
    df["cobertura_educacion_media"] = val
    df["departamento"] = df["nombre_etc"].map(a_canonico)
    df = df.dropna(subset=["departamento", "año", "cobertura_educacion_media"])
    return df[["departamento", "año", "cobertura_educacion_media"]].copy()


@st.cache_data(show_spinner="Integrando panel territorial…", ttl=3600)
def construir_panel() -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Une fuentes reales en un panel largo departamento × año.
    Columnas no disponibles quedan en NaN (sin imputación inventada).
    """
    estados = {}
    try:
        pib = cargar_pib()
        estados["pib_mil_millones"] = f"OK · {len(pib)} filas"
    except Exception as e:
        pib = pd.DataFrame(columns=["departamento", "año", "pib_mil_millones"])
        estados["pib_mil_millones"] = f"Error: {type(e).__name__}: {e}"

    try:
        hom = cargar_homicidios()
        estados["homicidios_cantidad"] = f"OK · {len(hom)} filas"
    except Exception as e:
        hom = pd.DataFrame(columns=["departamento", "año", "homicidios_cantidad"])
        estados["homicidios_cantidad"] = f"Error: {type(e).__name__}: {e}"

    try:
        edu = cargar_cobertura_media()
        estados["cobertura_educacion_media"] = f"OK · {len(edu)} filas"
    except Exception as e:
        edu = pd.DataFrame(columns=["departamento", "año", "cobertura_educacion_media"])
        estados["cobertura_educacion_media"] = f"Error: {type(e).__name__}: {e}"

    estados["ipm_porcentaje"] = "No disponible vía API abierta (usar anexo DANE IPM)"
    estados["tasa_desempleo"] = "No disponible vía API abierta (usar anexo GEIH departamental)"
    estados["inversion_dnp"] = "No disponible vía API abierta (usar TerriData / Mapa Inversiones)"

    # Rango de años a partir de fuentes disponibles
    años = set()
    for d in (pib, hom, edu):
        if not d.empty:
            años.update(d["año"].dropna().astype(int).tolist())
    if not años:
        años = set(range(2010, 2025))
    años = sorted(a for a in años if 2005 <= a <= 2026)

    base = pd.MultiIndex.from_product(
        [DEPARTAMENTOS_CANONICOS, años], names=["departamento", "año"]
    ).to_frame(index=False)

    for d in (pib, hom, edu):
        if not d.empty:
            base = base.merge(d, on=["departamento", "año"], how="left")

    for col in ["ipm_porcentaje", "tasa_desempleo", "inversion_dnp"]:
        if col not in base.columns:
            base[col] = np.nan

    base["año"] = base["año"].astype(int)
    return base.sort_values(["departamento", "año"]).reset_index(drop=True), estados


# =============================================================================
# GEOJSON
# =============================================================================
@st.cache_data(show_spinner="Cargando geometrías…", ttl=86400)
def cargar_geojson() -> Tuple[dict, str]:
    fuentes = [
        {
            "url": "https://raw.githubusercontent.com/caticoa3/colombia_mapa/master/co_2018_MGN_DPTO_POLITICO.geojson",
            "keys": ["DPTO_CNMBR"],
        },
        {
            "url": "https://gist.githubusercontent.com/john-guerra/43c7656821069d00dcbc/raw/be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/Colombia.geo.json",
            "keys": ["NOMBRE_DPT", "DPTO"],
        },
    ]
    for fuente in fuentes:
        try:
            r = requests.get(fuente["url"], timeout=15)
            if r.status_code != 200:
                continue
            geo = r.json()
            if not geo.get("features"):
                continue
            props0 = geo["features"][0].get("properties", {})
            key = next((k for k in fuente["keys"] if k in props0), None)
            if not key:
                continue
            for feat in geo["features"]:
                raw = str(feat["properties"].get(key, ""))
                feat["properties"]["_NOM_NORM"] = normalizar_nombre(raw)
            return geo, "_NOM_NORM"
        except Exception:
            continue
    # fallback bbox
    centros = {
        "Amazonas": (-70.0, -1.5), "Antioquia": (-75.5, 6.5), "Arauca": (-70.8, 6.5),
        "Atlántico": (-74.8, 10.7), "Bogotá D.C.": (-74.1, 4.6), "Bolívar": (-75.0, 9.0),
        "Boyacá": (-73.0, 5.5), "Caldas": (-75.5, 5.1), "Caquetá": (-74.0, 1.0),
        "Casanare": (-71.5, 5.5), "Cauca": (-76.5, 2.5), "Cesar": (-73.5, 9.5),
        "Chocó": (-77.0, 6.0), "Córdoba": (-75.8, 8.5), "Cundinamarca": (-74.2, 5.0),
        "Guainía": (-68.5, 2.5), "Guaviare": (-72.5, 2.0), "Huila": (-75.5, 2.8),
        "La Guajira": (-72.5, 11.5), "Magdalena": (-74.2, 10.5), "Meta": (-73.5, 3.5),
        "Nariño": (-77.5, 1.5), "Norte de Santander": (-72.5, 8.0), "Putumayo": (-76.0, 0.5),
        "Quindío": (-75.7, 4.5), "Risaralda": (-75.8, 5.0),
        "San Andrés y Providencia": (-81.7, 12.5), "Santander": (-73.2, 7.0),
        "Sucre": (-75.0, 9.2), "Tolima": (-75.2, 4.0), "Valle del Cauca": (-76.5, 3.8),
        "Vaupés": (-70.5, 0.8), "Vichada": (-69.5, 4.5),
    }
    feats = []
    for depto, (lon, lat) in centros.items():
        d = 0.55
        poly = [[lon-d, lat-d], [lon+d, lat-d], [lon+d, lat+d], [lon-d, lat+d], [lon-d, lat-d]]
        feats.append({
            "type": "Feature",
            "properties": {"_NOM_NORM": normalizar_nombre(depto)},
            "geometry": {"type": "Polygon", "coordinates": [poly]},
        })
    return {"type": "FeatureCollection", "features": feats}, "_NOM_NORM"


# =============================================================================
# BENCHMARK + UI HELPERS
# =============================================================================
def calcular_benchmark(valor, promedio, mejor_cuando):
    if promedio == 0 or pd.isna(promedio) or pd.isna(valor):
        return 0.0, "kpi-na", "Sin dato comparable"
    diff = ((valor - promedio) / abs(promedio)) * 100
    if mejor_cuando == "alto":
        if diff >= 5:
            return diff, "kpi-positive", f"▲ {diff:+.1f}% vs promedio nacional"
        if diff <= -5:
            return diff, "kpi-negative", f"▼ {diff:+.1f}% vs promedio nacional"
        return diff, "kpi-neutral", f"≈ {diff:+.1f}% vs promedio nacional"
    if diff <= -5:
        return diff, "kpi-positive", f"▼ {diff:+.1f}% vs promedio nacional (mejor)"
    if diff >= 5:
        return diff, "kpi-negative", f"▲ {diff:+.1f}% vs promedio nacional (peor)"
    return diff, "kpi-neutral", f"≈ {diff:+.1f}% vs promedio nacional"


def render_kpi_card(titulo, valor, formato, clase, texto, disponible):
    if not disponible or pd.isna(valor):
        valor_str = "No disponible"
        texto = "Sin serie abierta vía API"
        clase = "kpi-na"
    else:
        valor_str = formato.format(valor)
    st.markdown(
        f"""
        <div class="kpi-card">
            <p class="kpi-title">{titulo}</p>
            <p class="kpi-value">{valor_str}</p>
            <p class="kpi-subtitle {clase}">{texto}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def crear_mapa(df_año, geojson, feature_key, variable, año):
    meta = METADATA_VARIABLES[variable]
    df_map = df_año.dropna(subset=[variable]).copy()
    if df_map.empty:
        return None
    df_map["_NOM_NORM"] = df_map["departamento"].map(normalizar_nombre)
    fig = px.choropleth(
        df_map,
        geojson=geojson,
        locations="_NOM_NORM",
        featureidkey=f"properties.{feature_key}",
        color=variable,
        color_continuous_scale="Blues" if meta["mejor_cuando"] == "alto" else "Reds_r",
        hover_name="departamento",
        hover_data={variable: ":.1f", "_NOM_NORM": False},
        labels={variable: meta["nombre"]},
        title=f"{meta['nombre']} – {año}",
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator")
    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0), height=560,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(title=meta["unidad"], thickness=12, len=0.55),
    )
    return fig


def crear_serie(df_depto, df_nac, variable, depto):
    meta = METADATA_VARIABLES[variable]
    fig = go.Figure()
    d1 = df_depto.dropna(subset=[variable])
    d2 = df_nac.dropna(subset=[variable])
    if not d1.empty:
        fig.add_trace(go.Scatter(
            x=d1["año"], y=d1[variable], mode="lines+markers", name=depto,
            line=dict(color="#2563EB", width=3),
        ))
    if not d2.empty:
        fig.add_trace(go.Scatter(
            x=d2["año"], y=d2[variable], mode="lines", name="Promedio nacional (depts. con dato)",
            line=dict(color="#0D9488", width=2, dash="dash"),
        ))
    fig.update_layout(
        title=f"Evolución de {meta['nombre']}",
        xaxis_title="Año", yaxis_title=meta["unidad"],
        hovermode="x unified", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


def crear_ranking(df_año, variable, depto_sel):
    meta = METADATA_VARIABLES[variable]
    d = df_año.dropna(subset=[variable]).sort_values(
        variable, ascending=(meta["mejor_cuando"] == "bajo")
    )
    if d.empty:
        return None
    colors = ["#2563EB" if x == depto_sel else "#94A3B8" for x in d["departamento"]]
    fig = go.Figure(go.Bar(
        x=d[variable], y=d["departamento"], orientation="h", marker_color=colors,
        text=d[variable].map(lambda v: meta["formato"].format(v)), textposition="outside",
    ))
    fig.update_layout(
        title=f"Ranking – {meta['nombre']}", height=720,
        margin=dict(l=150, r=40, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# =============================================================================
# MAIN
# =============================================================================
def main():
    df, estados_carga = construir_panel()
    geojson, feature_key = cargar_geojson()

    with st.sidebar:
        st.markdown("## 🇨🇴 Observatorio")
        st.markdown("##### Datos reales · datos.gov.co")
        st.markdown("---")

        años_disp = sorted(df["año"].unique(), reverse=True)
        año_sel = st.selectbox("Año de análisis", options=años_disp, index=0)
        depto_sel = st.selectbox(
            "Departamento",
            options=sorted(DEPARTAMENTOS_CANONICOS),
            index=sorted(DEPARTAMENTOS_CANONICOS).index("Bogotá D.C."),
        )
        variable_sel = st.selectbox(
            "Variable (mapa / series)",
            options=VARIABLES_DISPONIBLES,
            format_func=lambda x: METADATA_VARIABLES[x]["nombre"],
        )

        st.markdown("---")
        st.markdown("#### Ficha técnica")
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown(f"**{meta['nombre']}**")
        st.caption(meta["significado"])
        with st.expander("Impacto"):
            st.write(meta["impacto"])
        st.markdown(f"<span class='source-badge'>{meta['fuente']}</span>", unsafe_allow_html=True)
        st.markdown("---")
        with st.expander("Estado de carga de fuentes"):
            for k, v in estados_carga.items():
                st.caption(f"**{k}**: {v}")

    df_año = df[df["año"] == año_sel].copy()
    df_depto = df[df["departamento"] == depto_sel].copy()
    # promedio solo sobre departamentos con dato (no inventar)
    df_nac = (
        df.groupby("año")[VARIABLES_DISPONIBLES]
        .mean(numeric_only=True)
        .reset_index()
    )
    prom_nac = df_año[VARIABLES_DISPONIBLES].mean(numeric_only=True)

    st.markdown(
        f"""
        <div class="hero-container">
            <p class="hero-title">Observatorio de Analítica Económica y Social</p>
            <p class="hero-subtitle">
                Panel territorial con <strong>datos oficiales abiertos</strong> (sin series sintéticas).
                Fuentes: DANE/datos.gov.co (PIB), MinDefensa (homicidios), MEN (cobertura media).
            </p>
            <div class="hero-meta">
                <span class="hero-chip">📍 {depto_sel}</span>
                <span class="hero-chip">📅 {año_sel}</span>
                <span class="hero-chip hero-chip-teal">Solo datos reales · NaN si no hay fuente abierta</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="warn-box">
            <strong>Transparencia metodológica:</strong> IPM, tasa de desempleo e inversión pública
            agregada anual <em>no</em> se inventan. Esas series oficiales se publican en anexos XLS/PDF
            del DANE y DNP sin endpoint SODA completo y estable para las 33 entidades en todo el periodo.
            En esta app aparecen como <strong>No disponible</strong> hasta integrar esos anexos.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_inicio, tab_kpi, tab_mapa, tab_serie, tab_ranking, tab_tabla, tab_fuentes = st.tabs([
        "🏠 Inicio", "📊 KPIs", "🗺️ Mapa", "📈 Serie", "🏆 Ranking", "📋 Tabla", "📚 Fuentes",
    ])

    with tab_inicio:
        st.markdown("### Qué está cargado realmente")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                """<div class="info-box"><strong>PIB departamental</strong><br>
                Agregado de actividades a precios corrientes<br>
                <span class="source-badge">kgyi-qc7j</span></div>""",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                """<div class="info-box"><strong>Homicidios (conteo)</strong><br>
                Víctimas por departamento-año<br>
                <span class="source-badge">m8fd-ahd9</span></div>""",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                """<div class="info-box"><strong>Cobertura neta media</strong><br>
                Solo ETC departamentales MEN<br>
                <span class="source-badge">sras-4t5p</span></div>""",
                unsafe_allow_html=True,
            )

        st.markdown(f"#### Resumen · {depto_sel} ({año_sel})")
        cols = st.columns(3)
        for i, var in enumerate(VARIABLES_DISPONIBLES):
            with cols[i % 3]:
                row = df_año.loc[df_año["departamento"] == depto_sel, var]
                val = row.values[0] if len(row) else np.nan
                m = METADATA_VARIABLES[var]
                st.metric(
                    m["nombre"].split("(")[0].strip(),
                    m["formato"].format(val) if not pd.isna(val) else "N/D",
                )

    with tab_kpi:
        st.markdown(f"### KPIs · {depto_sel} · {año_sel}")
        cols = st.columns(3)
        for idx, var in enumerate(VARIABLES_ORDEN):
            with cols[idx % 3]:
                meta = METADATA_VARIABLES[var]
                row = df_año.loc[df_año["departamento"] == depto_sel, var] if var in df_año.columns else pd.Series([np.nan])
                val = row.values[0] if len(row) else np.nan
                prom = prom_nac[var] if var in prom_nac.index else np.nan
                _, clase, texto = calcular_benchmark(val, prom, meta["mejor_cuando"])
                render_kpi_card(meta["nombre"], val, meta["formato"], clase, texto, meta["disponible"])

    with tab_mapa:
        if variable_sel not in VARIABLES_DISPONIBLES:
            st.warning("Variable sin datos abiertos cargados.")
        else:
            st.markdown(f"#### {METADATA_VARIABLES[variable_sel]['nombre']}")
            fig = crear_mapa(df_año, geojson, feature_key, variable_sel, año_sel)
            if fig is None:
                st.warning("Sin datos para el mapa en este año/variable.")
            else:
                st.plotly_chart(fig, use_container_width=True)

    with tab_serie:
        fig = crear_serie(df_depto, df_nac, variable_sel, depto_sel)
        st.plotly_chart(fig, use_container_width=True)

    with tab_ranking:
        fig = crear_ranking(df_año, variable_sel, depto_sel)
        if fig is None:
            st.warning("Sin datos para ranking.")
        else:
            st.plotly_chart(fig, use_container_width=True)

    with tab_tabla:
        st.markdown(f"#### Panel · {año_sel}")
        cols_show = ["departamento", "año"] + VARIABLES_ORDEN
        cols_show = [c for c in cols_show if c in df_año.columns]
        st.dataframe(df_año[cols_show], use_container_width=True, height=520)
        csv = df_año[cols_show].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV del año",
            data=csv,
            file_name=f"observatorio_real_{año_sel}.csv",
            mime="text/csv",
        )

    with tab_fuentes:
        st.markdown("### Fuentes y limitaciones (sin alucinaciones)")
        st.markdown(
            """
| Variable | Fuente abierta usada | Limitación |
|----------|----------------------|------------|
| PIB | [kgyi-qc7j](https://www.datos.gov.co/d/kgyi-qc7j) | Suma de actividades a precios corrientes (no es el anexo oficial “PIB total” del boletín, pero es la serie abierta agregable) |
| Homicidios | [m8fd-ahd9](https://www.datos.gov.co/d/m8fd-ahd9) | Conteo de víctimas, no tasa por 100.000 (falta población oficial en la misma API) |
| Cobertura media | [sras-4t5p](https://www.datos.gov.co/d/sras-4t5p) | Solo ETC departamentales; municipios certificados no se reasignan |
| IPM | Anexos DANE | Sin API SODA completa histórica departamental |
| Desempleo | GEIH / anexos DANE | 23 departamentos en boletines; no 33 vía API |
| Inversión DNP | TerriData / Mapa Inversiones | Proyectos BPIN; agregación anual departamental no estandarizada aquí |
            """
        )
        st.markdown("#### Estado de esta sesión")
        for k, v in estados_carga.items():
            st.write(f"- **{k}**: {v}")

    st.markdown(
        """
        <div class="footer">
            Observatorio territorial Colombia · Solo datos abiertos reales · Sin series sintéticas
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
