"""
Observatorio de Analítica Económica y Social por Departamentos en Colombia
==========================================================================
Versión corregida: mapa funcional, sidebar legible, KPIs en pestaña, bienvenida.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import unicodedata
from typing import Dict, Optional, Tuple
import warnings

warnings.filterwarnings("ignore")

# =============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =============================================================================
st.set_page_config(
    page_title="Observatorio Económico-Social | Colombia",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background-color: #F8FAFC; }

    /* ---- Sidebar oscuro + widgets legibles ---- */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        background-color: #0F172A !important;
    }
    [data-testid="stSidebar"] label {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stMarkdown {
        color: #E2E8F0 !important;
    }
    /* Selectbox: fondo oscuro + texto claro */
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #1E293B !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div {
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #F8FAFC !important;
        color: #F8FAFC !important;
    }
    /* Menú desplegable (a veces se renderiza fuera del sidebar) */
    div[data-baseweb="popover"] ul,
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
    }
    div[data-baseweb="popover"] li span,
    div[data-baseweb="popover"] li div {
        color: #F8FAFC !important;
    }
    div[data-baseweb="popover"] li:hover {
        background-color: #334155 !important;
    }
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] small {
        color: #94A3B8 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #1E293B !important;
        border-radius: 8px;
        border: 1px solid #334155 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        color: #E2E8F0 !important;
    }

    /* ---- Hero / Bienvenida ---- */
    .hero-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 55%, #1E3A5F 100%);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 20px;
        color: #F8FAFC;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.35);
    }
    .hero-title {
        font-size: 1.7rem;
        font-weight: 800;
        margin: 0 0 6px 0;
        letter-spacing: -0.02em;
        color: #FFFFFF !important;
    }
    .hero-subtitle {
        font-size: 1.02rem;
        color: #94A3B8;
        margin: 0 0 16px 0;
        line-height: 1.45;
    }
    .hero-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 4px;
    }
    .hero-chip {
        background: rgba(37, 99, 235, 0.28);
        border: 1px solid rgba(37, 99, 235, 0.5);
        color: #93C5FD;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 6px 14px;
        border-radius: 9999px;
    }
    .hero-chip-teal {
        background: rgba(13, 148, 136, 0.28);
        border: 1px solid rgba(13, 148, 136, 0.5);
        color: #5EEAD4;
    }

    /* ---- KPI Cards ---- */
    .kpi-card {
        background-color: #FFFFFF;
        border-left: 5px solid #2563EB;
        padding: 18px 22px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
        margin-bottom: 14px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        height: 100%;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
    }
    .kpi-title {
        font-size: 0.78rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 0;
    }
    .kpi-value {
        font-size: 1.65rem;
        color: #0F172A;
        font-weight: 700;
        margin: 6px 0 2px 0;
        line-height: 1.2;
    }
    .kpi-subtitle { font-size: 0.78rem; font-weight: 500; margin: 0; }
    .kpi-positive { color: #059669; }
    .kpi-negative { color: #DC2626; }
    .kpi-neutral  { color: #64748B; }

    h1, h2, h3 { color: #0F172A !important; font-weight: 700 !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #E2E8F0;
        border-radius: 8px 8px 0 0;
        padding: 10px 18px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: white !important;
    }

    .source-badge {
        display: inline-block;
        background: #E0F2FE;
        color: #0369A1;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 9999px;
        font-weight: 600;
    }
    .info-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 10px;
        height: 100%;
    }
    .footer {
        text-align: center;
        color: #64748B;
        font-size: 0.8rem;
        padding: 24px 0 8px 0;
        border-top: 1px solid #E2E8F0;
        margin-top: 36px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# 2. METADATOS
# =============================================================================
METADATA_VARIABLES: Dict[str, Dict] = {
    "pib_mil_millones": {
        "nombre": "PIB Departamental (Miles de Millones COP)",
        "significado": "Valor monetario total de la producción de bienes y servicios finales generados dentro del departamento en un año determinado.",
        "impacto": "Determina la capacidad productiva, el tamaño de la economía regional y la base tributaria. Un crecimiento sostenido habilita mayor empleo e inversión privada y pública.",
        "fuente": "DANE – Cuentas Nacionales Departamentales",
        "unidad": "Miles de millones de pesos corrientes",
        "mejor_cuando": "alto",
        "formato": "{:,.0f}",
    },
    "tasa_homicidios": {
        "nombre": "Tasa de Homicidios (por 100.000 hab)",
        "significado": "Número de homicidios intencionales registrados por cada 100.000 habitantes en un año calendario.",
        "impacto": "Indicador clave de seguridad ciudadana, conflicto y violencia. Tasas elevadas desincentivan la inversión privada, destruyen capital humano y reducen el bienestar social.",
        "fuente": "Ministerio de Defensa / Policía Nacional",
        "unidad": "Homicidios por 100.000 habitantes",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}",
    },
    "inversion_dnp": {
        "nombre": "Inversión Pública Ejecutada (Millones COP)",
        "significado": "Monto de recursos públicos ejecutados en proyectos de inversión aprobados y registrados por el DNP.",
        "impacto": "Impulsa el desarrollo de infraestructura, cobertura social y equidad territorial. Constituye la principal palanca de política fiscal regional.",
        "fuente": "DNP – TerriData",
        "unidad": "Millones de pesos",
        "mejor_cuando": "alto",
        "formato": "{:,.0f}",
    },
    "ipm_porcentaje": {
        "nombre": "Índice de Pobreza Multidimensional (%)",
        "significado": "Porcentaje de la población que experimenta privaciones simultáneas en salud, educación, trabajo, vivienda y servicios públicos.",
        "impacto": "Refleja las condiciones estructurales de vida. Reducir el IPM promueve la equidad social, la movilidad intergeneracional y el desarrollo humano.",
        "fuente": "DANE – Encuesta de Calidad de Vida (ECV)",
        "unidad": "% de la población",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
    },
    "tasa_desempleo": {
        "nombre": "Tasa de Desempleo (%)",
        "significado": "Porcentaje de la fuerza de trabajo que no tiene empleo pero se encuentra en búsqueda activa de trabajo.",
        "impacto": "Mide la eficiencia y salud del mercado laboral regional. Tasas altas generan vulnerabilidad económica, informalidad y pérdida de ingresos de los hogares.",
        "fuente": "DANE – Gran Encuesta Integrada de Hogares (GEIH)",
        "unidad": "% de la PEA",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
    },
    "cobertura_educacion_media": {
        "nombre": "Cobertura Neta Educación Media (%)",
        "significado": "Porcentaje de personas en la edad escolar teórica para educación media que se encuentran matriculadas en dicho nivel educativo.",
        "impacto": "Determina la formación de capital humano calificado, reduce la brecha de productividad y facilita el acceso a la educación superior y a empleos de calidad.",
        "fuente": "Ministerio de Educación Nacional (MEN)",
        "unidad": "% de cobertura neta",
        "mejor_cuando": "alto",
        "formato": "{:.1f}%",
    },
}
VARIABLES_ORDEN = list(METADATA_VARIABLES.keys())

DEPARTAMENTOS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.",
    "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare",
    "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca",
    "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena",
    "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío",
    "Risaralda", "San Andrés y Providencia", "Santander", "Sucre",
    "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
]

# =============================================================================
# 3. NORMALIZACIÓN DE NOMBRES
# =============================================================================
def quitar_acentos(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_nombre(nombre: str) -> str:
    n = quitar_acentos(str(nombre)).upper().strip()
    n = n.replace(".", " ").replace(",", " ").replace("  ", " ").strip()
    while "  " in n:
        n = n.replace("  ", " ")
    aliases = {
        "BOGOTA DC": "BOGOTA D C",
        "BOGOTA D C": "BOGOTA D C",
        "BOGOTA": "BOGOTA D C",
        "DISTRITO CAPITAL": "BOGOTA D C",
        "DISTRITO CAPITAL DE BOGOTA": "BOGOTA D C",
        "SAN ANDRES": "SAN ANDRES Y PROVIDENCIA",
        "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES Y PROVIDENCIA",
        "ARCHIPIELAGO DE SAN ANDRES": "SAN ANDRES Y PROVIDENCIA",
        "NORTE SANTANDER": "NORTE DE SANTANDER",
        "VALLE": "VALLE DEL CAUCA",
    }
    return aliases.get(n, n)


# =============================================================================
# 4. DATASET
# =============================================================================
@st.cache_data(show_spinner="Generando dataset sintético maestro…")
def generar_dataset_maestro(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    años = list(range(2010, 2025))
    base_pib = rng.uniform(8_000, 180_000, size=len(DEPARTAMENTOS))
    base_homicidio = rng.uniform(8, 65, size=len(DEPARTAMENTOS))
    base_inversion = rng.uniform(80_000, 2_500_000, size=len(DEPARTAMENTOS))
    base_ipm = rng.uniform(12, 55, size=len(DEPARTAMENTOS))
    base_desempleo = rng.uniform(6, 18, size=len(DEPARTAMENTOS))
    base_cobertura = rng.uniform(45, 92, size=len(DEPARTAMENTOS))

    records = []
    for i, depto in enumerate(DEPARTAMENTOS):
        for año in años:
            trend = (año - 2010) / 14.0
            pib = base_pib[i] * (1 + 0.035 * trend + rng.normal(0, 0.04))
            hom = max(3.0, min(base_homicidio[i] * (1 - 0.25 * trend + rng.normal(0, 0.08)), 90))
            inv = base_inversion[i] * (1 + 0.045 * trend + rng.normal(0, 0.06))
            ipm = max(5.0, min(base_ipm[i] * (1 - 0.30 * trend + rng.normal(0, 0.05)), 70))
            des = max(3.5, min(base_desempleo[i] * (1 - 0.15 * trend + rng.normal(0, 0.07)), 25))
            cob = max(30.0, min(base_cobertura[i] * (1 + 0.20 * trend + rng.normal(0, 0.04)), 99))
            records.append({
                "departamento": depto,
                "año": año,
                "pib_mil_millones": round(pib, 1),
                "tasa_homicidios": round(hom, 1),
                "inversion_dnp": round(inv, 0),
                "ipm_porcentaje": round(ipm, 1),
                "tasa_desempleo": round(des, 1),
                "cobertura_educacion_media": round(cob, 1),
            })

    df = pd.DataFrame(records)
    cols = list(METADATA_VARIABLES.keys())
    mask = rng.random(df[cols].shape) < 0.03
    df[cols] = df[cols].mask(mask)
    df[cols] = (
        df.groupby("departamento")[cols]
          .transform(lambda x: x.interpolate(method="linear").bfill().ffill())
    )
    df["año"] = df["año"].astype(int)
    return df.sort_values(["departamento", "año"]).reset_index(drop=True)


# =============================================================================
# 5. GEOJSON ROBUSTO
# =============================================================================
@st.cache_data(show_spinner="Cargando geometrías departamentales…")
def cargar_geojson() -> Tuple[dict, str]:
    """
    Retorna (geojson, feature_key).
    Usa fuentes públicas verificadas e inyecta propiedad _NOM_NORM para matching.
    """
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
            r = requests.get(fuente["url"], timeout=12)
            if r.status_code != 200:
                continue
            geo = r.json()
            if not geo.get("features") or len(geo["features"]) < 20:
                continue

            props0 = geo["features"][0].get("properties", {})
            feature_key = None
            for k in fuente["keys"]:
                if k in props0:
                    feature_key = k
                    break
            if not feature_key:
                for k in props0:
                    if "NOM" in k.upper() or "NAME" in k.upper():
                        feature_key = k
                        break
            if not feature_key:
                continue

            for feat in geo["features"]:
                raw = str(feat["properties"].get(feature_key, ""))
                feat["properties"]["_NOM_NORM"] = normalizar_nombre(raw)

            return geo, "_NOM_NORM"
        except Exception:
            continue

    # Fallback sintético (siempre funciona)
    centros = {
        "Amazonas": (-70.0, -1.5), "Antioquia": (-75.5, 6.5),
        "Arauca": (-70.8, 6.5), "Atlántico": (-74.8, 10.7),
        "Bogotá D.C.": (-74.1, 4.6), "Bolívar": (-75.0, 9.0),
        "Boyacá": (-73.0, 5.5), "Caldas": (-75.5, 5.1),
        "Caquetá": (-74.0, 1.0), "Casanare": (-71.5, 5.5),
        "Cauca": (-76.5, 2.5), "Cesar": (-73.5, 9.5),
        "Chocó": (-77.0, 6.0), "Córdoba": (-75.8, 8.5),
        "Cundinamarca": (-74.2, 5.0), "Guainía": (-68.5, 2.5),
        "Guaviare": (-72.5, 2.0), "Huila": (-75.5, 2.8),
        "La Guajira": (-72.5, 11.5), "Magdalena": (-74.2, 10.5),
        "Meta": (-73.5, 3.5), "Nariño": (-77.5, 1.5),
        "Norte de Santander": (-72.5, 8.0), "Putumayo": (-76.0, 0.5),
        "Quindío": (-75.7, 4.5), "Risaralda": (-75.8, 5.0),
        "San Andrés y Providencia": (-81.7, 12.5),
        "Santander": (-73.2, 7.0), "Sucre": (-75.0, 9.2),
        "Tolima": (-75.2, 4.0), "Valle del Cauca": (-76.5, 3.8),
        "Vaupés": (-70.5, 0.8), "Vichada": (-69.5, 4.5),
    }
    features = []
    for depto, (lon, lat) in centros.items():
        d = 0.55
        poly = [[lon-d, lat-d], [lon+d, lat-d], [lon+d, lat+d], [lon-d, lat+d], [lon-d, lat-d]]
        features.append({
            "type": "Feature",
            "properties": {
                "NOMBRE_DPT": depto,
                "_NOM_NORM": normalizar_nombre(depto),
            },
            "geometry": {"type": "Polygon", "coordinates": [poly]},
        })
    return {"type": "FeatureCollection", "features": features}, "_NOM_NORM"


# =============================================================================
# 6. BENCHMARKING
# =============================================================================
def calcular_benchmark(valor, promedio_nacional, mejor_cuando):
    if promedio_nacional == 0 or pd.isna(promedio_nacional) or pd.isna(valor):
        return 0.0, "kpi-neutral", "Sin dato nacional"
    diff_pct = ((valor - promedio_nacional) / abs(promedio_nacional)) * 100
    if mejor_cuando == "alto":
        if diff_pct >= 5:
            return diff_pct, "kpi-positive", f"▲ {diff_pct:+.1f}% vs promedio nacional"
        elif diff_pct <= -5:
            return diff_pct, "kpi-negative", f"▼ {diff_pct:+.1f}% vs promedio nacional"
        else:
            return diff_pct, "kpi-neutral", f"≈ {diff_pct:+.1f}% vs promedio nacional"
    else:
        if diff_pct <= -5:
            return diff_pct, "kpi-positive", f"▼ {diff_pct:+.1f}% vs promedio nacional (mejor)"
        elif diff_pct >= 5:
            return diff_pct, "kpi-negative", f"▲ {diff_pct:+.1f}% vs promedio nacional (peor)"
        else:
            return diff_pct, "kpi-neutral", f"≈ {diff_pct:+.1f}% vs promedio nacional"


def render_kpi_card(titulo, valor, formato, clase, texto_bench, help_text):
    valor_str = formato.format(valor) if not pd.isna(valor) else "N/D"
    html = f"""
    <div class="kpi-card" title="{help_text}">
        <p class="kpi-title">{titulo}</p>
        <p class="kpi-value">{valor_str}</p>
        <p class="kpi-subtitle {clase}">{texto_bench}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# 7. VISUALIZACIONES
# =============================================================================
def crear_mapa_coropletico(df_año, geojson, feature_key, variable, año):
    meta = METADATA_VARIABLES[variable]
    df_map = df_año.copy()
    df_map["_NOM_NORM"] = df_map["departamento"].apply(normalizar_nombre)

    fig = px.choropleth(
        df_map,
        geojson=geojson,
        locations="_NOM_NORM",
        featureidkey=f"properties.{feature_key}",
        color=variable,
        color_continuous_scale="Blues" if meta["mejor_cuando"] == "alto" else "Reds_r",
        range_color=(df_map[variable].min(), df_map[variable].max()),
        hover_name="departamento",
        hover_data={variable: ":.1f", "_NOM_NORM": False, "departamento": False},
        labels={variable: meta["nombre"]},
        title=f"{meta['nombre']} – {año}",
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor="rgba(0,0,0,0)",
        projection_type="mercator",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(title=meta["unidad"], thickness=12, len=0.55),
        height=560,
        font=dict(family="Inter, sans-serif", size=12),
    )
    return fig


def crear_serie_temporal(df_depto, df_nacional, variable, depto):
    meta = METADATA_VARIABLES[variable]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_depto["año"], y=df_depto[variable],
        mode="lines+markers", name=depto,
        line=dict(color="#2563EB", width=3), marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=df_nacional["año"], y=df_nacional[variable],
        mode="lines", name="Promedio Nacional",
        line=dict(color="#0D9488", width=2, dash="dash"),
    ))
    fig.update_layout(
        title=f"Evolución de {meta['nombre']}",
        xaxis_title="Año", yaxis_title=meta["unidad"],
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=40, r=20, t=60, b=40),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


def crear_ranking_horizontal(df_año, variable, depto_seleccionado):
    meta = METADATA_VARIABLES[variable]
    df_sorted = df_año.sort_values(variable, ascending=(meta["mejor_cuando"] == "bajo"))
    colors = ["#2563EB" if d == depto_seleccionado else "#94A3B8" for d in df_sorted["departamento"]]
    fig = go.Figure(go.Bar(
        x=df_sorted[variable],
        y=df_sorted["departamento"],
        orientation="h",
        marker_color=colors,
        text=df_sorted[variable].map(lambda x: meta["formato"].format(x)),
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Ranking Departamental – {meta['nombre']}",
        xaxis_title=meta["unidad"],
        yaxis_title="",
        height=720,
        margin=dict(l=150, r=40, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=11),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


# =============================================================================
# 8. MAIN
# =============================================================================
def main():
    df = generar_dataset_maestro()
    geojson, feature_key = cargar_geojson()

    with st.sidebar:
        st.markdown("## 🇨🇴 Observatorio")
        st.markdown("##### Analítica Económica y Social")
        st.markdown("---")

        año_sel = st.selectbox(
            "Año de análisis",
            options=sorted(df["año"].unique(), reverse=True),
            index=0,
        )
        depto_sel = st.selectbox(
            "Departamento",
            options=sorted(DEPARTAMENTOS),
            index=sorted(DEPARTAMENTOS).index("Bogotá D.C."),
        )
        variable_sel = st.selectbox(
            "Variable principal (mapa / series)",
            options=VARIABLES_ORDEN,
            format_func=lambda x: METADATA_VARIABLES[x]["nombre"],
            index=0,
        )

        st.markdown("---")
        st.markdown("#### Ficha Técnica")
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown(f"**{meta['nombre']}**")
        st.caption(meta["significado"])
        with st.expander("Impacto socioeconómico"):
            st.write(meta["impacto"])
        st.markdown(f"<span class='source-badge'>{meta['fuente']}</span>", unsafe_allow_html=True)
        st.markdown("---")
        st.caption("Datos sintéticos 2010-2024 · Imputación lineal · Benchmarking en tiempo real")

    df_año = df[df["año"] == año_sel].copy()
    df_depto = df[df["departamento"] == depto_sel].copy()
    df_nacional = df.groupby("año")[VARIABLES_ORDEN].mean().reset_index()
    prom_nac = df_año[VARIABLES_ORDEN].mean()

    # ---- Hero / Bienvenida ----
    st.markdown(
        f"""
        <div class="hero-container">
            <p class="hero-title">Observatorio de Analítica Económica y Social</p>
            <p class="hero-subtitle">
                Plataforma territorial para los 32 departamentos y Bogotá D.C.
                Explore producción, seguridad, inversión pública, pobreza, empleo y educación
                con benchmarking frente al promedio nacional.
            </p>
            <div class="hero-meta">
                <span class="hero-chip">📍 {depto_sel}</span>
                <span class="hero-chip">📅 {año_sel}</span>
                <span class="hero-chip hero-chip-teal">33 entidades · 2010–2024 · 6 indicadores</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_inicio, tab_kpi, tab_mapa, tab_serie, tab_ranking, tab_tabla, tab_glosario = st.tabs([
        "🏠 Inicio",
        "📊 KPIs",
        "🗺️ Mapa Territorial",
        "📈 Serie Temporal",
        "🏆 Ranking",
        "📋 Tabla",
        "📖 Glosario",
    ])

    # ---- INICIO ----
    with tab_inicio:
        st.markdown("### Cómo usar el Observatorio")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                """<div class="info-box"><strong>1. Filtros</strong><br>
                En el panel izquierdo elija <em>año</em>, <em>departamento</em>
                y la <em>variable principal</em> para mapa y series.</div>""",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                """<div class="info-box"><strong>2. KPIs</strong><br>
                En la pestaña <em>KPIs</em> verá los 6 indicadores con
                semaforización vs. promedio nacional.</div>""",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                """<div class="info-box"><strong>3. Análisis</strong><br>
                Use el mapa, las series de tiempo y el ranking para
                comparar territorios y trayectorias.</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown(f"#### Resumen rápido · {depto_sel} ({año_sel})")
        r1 = st.columns(3)
        for i, var in enumerate(VARIABLES_ORDEN[:3]):
            with r1[i]:
                valor = df_año.loc[df_año["departamento"] == depto_sel, var].values
                valor = valor[0] if len(valor) else np.nan
                m = METADATA_VARIABLES[var]
                st.metric(
                    label=m["nombre"].split("(")[0].strip(),
                    value=m["formato"].format(valor) if not pd.isna(valor) else "N/D",
                )
        r2 = st.columns(3)
        for i, var in enumerate(VARIABLES_ORDEN[3:]):
            with r2[i]:
                valor = df_año.loc[df_año["departamento"] == depto_sel, var].values
                valor = valor[0] if len(valor) else np.nan
                m = METADATA_VARIABLES[var]
                st.metric(
                    label=m["nombre"].split("(")[0].strip(),
                    value=m["formato"].format(valor) if not pd.isna(valor) else "N/D",
                )

        st.info(
            "💡 Los datos de esta versión son **sintéticos** (reproducibles con semilla 42) "
            "y siguen patrones realistas de heterogeneidad regional. Ideal para demostración "
            "metodológica y diseño de interfaces de análisis territorial."
        )

    # ---- KPIs ----
    with tab_kpi:
        st.markdown(f"### Indicadores Clave de Desempeño · {depto_sel} · {año_sel}")
        st.caption(
            "Comparación en tiempo real frente al promedio nacional del mismo año. "
            "Colores según deseabilidad del indicador."
        )
        cols = st.columns(3)
        for idx, var in enumerate(VARIABLES_ORDEN):
            with cols[idx % 3]:
                valor = df_año.loc[df_año["departamento"] == depto_sel, var].values
                valor = valor[0] if len(valor) else np.nan
                meta = METADATA_VARIABLES[var]
                _, clase, texto = calcular_benchmark(valor, prom_nac[var], meta["mejor_cuando"])
                help_txt = f"{meta['significado']}\n\nImpacto: {meta['impacto']}\n\nFuente: {meta['fuente']}"
                render_kpi_card(
                    titulo=meta["nombre"],
                    valor=valor,
                    formato=meta["formato"],
                    clase=clase,
                    texto_bench=texto,
                    help_text=help_txt,
                )
        st.markdown("---")
        st.markdown("#### Interpretación de la semaforización")
        st.markdown(
            """
            - **Verde**: el departamento se desvía ≥ 5 % en la dirección deseable respecto al promedio nacional.
            - **Rojo**: se desvía ≥ 5 % en la dirección no deseable.
            - **Gris**: diferencia inferior a 5 % (comportamiento cercano al promedio).
            """
        )

    # ---- MAPA ----
    with tab_mapa:
        st.markdown(f"#### Distribución espacial – {METADATA_VARIABLES[variable_sel]['nombre']}")
        try:
            fig_mapa = crear_mapa_coropletico(
                df_año, geojson, feature_key, variable_sel, año_sel
            )
            st.plotly_chart(fig_mapa, use_container_width=True)
        except Exception as e:
            st.error(f"No se pudo renderizar el mapa: {type(e).__name__}: {e}")
            st.dataframe(
                df_año[["departamento", variable_sel]].sort_values(
                    variable_sel, ascending=False
                ),
                use_container_width=True,
            )

    # ---- SERIE ----
    with tab_serie:
        fig_serie = crear_serie_temporal(df_depto, df_nacional, variable_sel, depto_sel)
        st.plotly_chart(fig_serie, use_container_width=True)
        st.markdown("##### Variación interanual reciente")
        df_tmp = df_depto[["año", variable_sel]].copy()
        df_tmp["var_pct"] = df_tmp[variable_sel].pct_change() * 100
        st.dataframe(
            df_tmp.tail(6).style.format({
                variable_sel: METADATA_VARIABLES[variable_sel]["formato"],
                "var_pct": "{:+.1f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

    # ---- RANKING ----
    with tab_ranking:
        fig_rank = crear_ranking_horizontal(df_año, variable_sel, depto_sel)
        st.plotly_chart(fig_rank, use_container_width=True)

    # ---- TABLA ----
    with tab_tabla:
        st.markdown(f"#### Datos del año {año_sel}")
        st.dataframe(
            df_año.style.format({
                v: METADATA_VARIABLES[v]["formato"] for v in VARIABLES_ORDEN
            }),
            use_container_width=True,
            height=520,
        )
        csv = df_año.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Descargar CSV del año seleccionado",
            data=csv,
            file_name=f"observatorio_colombia_{año_sel}.csv",
            mime="text/csv",
        )

    # ---- GLOSARIO ----
    with tab_glosario:
        st.markdown("### Glosario Metodológico y Fichas Técnicas")
        st.markdown(
            "Cada indicador incluye definición, impacto socioeconómico y fuente oficial. "
            "Los datos de esta demostración son **sintéticos** pero siguen patrones "
            "realistas de heterogeneidad regional colombiana."
        )
        for var, meta in METADATA_VARIABLES.items():
            with st.expander(f"📌 {meta['nombre']}"):
                st.markdown(f"**Significado**  \n{meta['significado']}")
                st.markdown(f"**Impacto**  \n{meta['impacto']}")
                st.markdown(f"**Fuente oficial**  \n{meta['fuente']}")
                st.markdown(f"**Unidad de medida**  \n{meta['unidad']}")
                orient = (
                    "Mayor valor es preferible"
                    if meta["mejor_cuando"] == "alto"
                    else "Menor valor es preferible"
                )
                st.markdown(f"**Orientación de deseabilidad**  \n{orient}")

    st.markdown(
        """
        <div class="footer">
            Observatorio de Analítica Económica y Social por Departamentos en Colombia<br>
            Datos sintéticos · Imputación lineal por grupo · Benchmarking dinámico · Diseño Think Tank
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
