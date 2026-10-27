"""
Observatorio de Analítica Económica y Social por Departamentos en Colombia
==========================================================================
Aplicación Streamlit de nivel Think Tank internacional.
Autor: Desarrollador Senior + Científico de Datos (Econometría Aplicada)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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

# -----------------------------------------------------------------------------
# CSS Personalizado – Paleta Think Tank
# -----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    /* Variables de color */
    :root {
        --slate-900: #0F172A;
        --slate-800: #1E293B;
        --blue-600: #2563EB;
        --teal-600: #0D9488;
        --slate-50: #F8FAFC;
        --slate-500: #64748B;
        --green-600: #059669;
        --amber-500: #F59E0B;
        --red-600: #DC2626;
    }

    /* Fondo general */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
    }
    [data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stSlider label {
        color: #94A3B8 !important;
        font-weight: 600;
    }

    /* KPI Cards */
    .kpi-card {
        background-color: #FFFFFF;
        border-left: 5px solid #2563EB;
        padding: 18px 22px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07),
                    0 2px 4px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 12px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
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
    .kpi-subtitle {
        font-size: 0.78rem;
        font-weight: 500;
        margin: 0;
    }
    .kpi-positive { color: #059669; }
    .kpi-negative { color: #DC2626; }
    .kpi-neutral  { color: #64748B; }

    /* Headers */
    h1, h2, h3 {
        color: #0F172A !important;
        font-weight: 700 !important;
    }

    /* Metricas nativas de Streamlit */
    [data-testid="stMetric"] {
        background: white;
        padding: 12px 16px;
        border-radius: 8px;
        border-left: 4px solid #2563EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #E2E8F0;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: white !important;
    }

    /* Dataframe */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Footer */
    .footer {
        text-align: center;
        color: #64748B;
        font-size: 0.8rem;
        padding: 24px 0 8px 0;
        border-top: 1px solid #E2E8F0;
        margin-top: 40px;
    }

    /* Badge de fuente */
    .source-badge {
        display: inline-block;
        background: #E0F2FE;
        color: #0369A1;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 9999px;
        font-weight: 600;
        margin-left: 6px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# 2. DICCIONARIO DE METADATOS (VARIABLES SOCIOECONÓMICAS)
# =============================================================================
METADATA_VARIABLES: Dict[str, Dict] = {
    "pib_mil_millones": {
        "nombre": "PIB Departamental (Miles de Millones COP)",
        "significado": (
            "Valor monetario total de la producción de bienes y servicios finales "
            "generados dentro del departamento en un año determinado."
        ),
        "impacto": (
            "Determina la capacidad productiva, el tamaño de la economía regional "
            "y la base tributaria. Un crecimiento sostenido habilita mayor empleo "
            "e inversión privada y pública."
        ),
        "fuente": "DANE – Cuentas Nacionales Departamentales",
        "unidad": "Miles de millones de pesos corrientes",
        "mejor_cuando": "alto",  # mayor es mejor
        "formato": "{:,.0f}",
    },
    "tasa_homicidios": {
        "nombre": "Tasa de Homicidios (por 100.000 hab)",
        "significado": (
            "Número de homicidios intencionales registrados por cada 100.000 "
            "habitantes en un año calendario."
        ),
        "impacto": (
            "Indicador clave de seguridad ciudadana, conflicto y violencia. "
            "Tasas elevadas desincentivan la inversión privada, destruyen capital "
            "humano y reducen el bienestar social."
        ),
        "fuente": "Ministerio de Defensa / Policía Nacional",
        "unidad": "Homicidios por 100.000 habitantes",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}",
    },
    "inversion_dnp": {
        "nombre": "Inversión Pública Ejecutada (Millones COP)",
        "significado": (
            "Monto de recursos públicos ejecutados en proyectos de inversión "
            "aprobados y registrados por el Departamento Nacional de Planeación (DNP)."
        ),
        "impacto": (
            "Impulsa el desarrollo de infraestructura, cobertura social y equidad "
            "territorial. Constituye la principal palanca de política fiscal regional."
        ),
        "fuente": "DNP – TerriData",
        "unidad": "Millones de pesos",
        "mejor_cuando": "alto",
        "formato": "{:,.0f}",
    },
    "ipm_porcentaje": {
        "nombre": "Índice de Pobreza Multidimensional (%)",
        "significado": (
            "Porcentaje de la población que experimenta privaciones simultáneas "
            "en salud, educación, trabajo, vivienda y servicios públicos."
        ),
        "impacto": (
            "Refleja las condiciones estructurales de vida. Reducir el IPM promueve "
            "la equidad social, la movilidad intergeneracional y el desarrollo humano."
        ),
        "fuente": "DANE – Encuesta de Calidad de Vida (ECV)",
        "unidad": "% de la población",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
    },
    "tasa_desempleo": {
        "nombre": "Tasa de Desempleo (%)",
        "significado": (
            "Porcentaje de la fuerza de trabajo que no tiene empleo pero se "
            "encuentra en búsqueda activa de trabajo."
        ),
        "impacto": (
            "Mide la eficiencia y salud del mercado laboral regional. Tasas altas "
            "generan vulnerabilidad económica, informalidad y pérdida de ingresos "
            "de los hogares."
        ),
        "fuente": "DANE – Gran Encuesta Integrada de Hogares (GEIH)",
        "unidad": "% de la PEA",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
    },
    "cobertura_educacion_media": {
        "nombre": "Cobertura Neta Educación Media (%)",
        "significado": (
            "Porcentaje de personas en la edad escolar teórica para educación media "
            "que se encuentran matriculadas en dicho nivel educativo."
        ),
        "impacto": (
            "Determina la formación de capital humano calificado, reduce la brecha "
            "de productividad y facilita el acceso a la educación superior y a "
            "empleos de calidad."
        ),
        "fuente": "Ministerio de Educación Nacional (MEN)",
        "unidad": "% de cobertura neta",
        "mejor_cuando": "alto",
        "formato": "{:.1f}%",
    },
}

# Lista ordenada de variables para UI
VARIABLES_ORDEN = list(METADATA_VARIABLES.keys())

# =============================================================================
# 3. LISTA OFICIAL DE DEPARTAMENTOS + BOGOTÁ
# =============================================================================
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
# 4. GENERACIÓN DE DATASET SINTÉTICO MAESTRO (2010-2024)
# =============================================================================
@st.cache_data(show_spinner="Generando dataset sintético maestro…")
def generar_dataset_maestro(seed: int = 42) -> pd.DataFrame:
    """
    Genera un DataFrame realista de 33 entidades × 15 años (2010-2024).
    Incluye ~3 % de valores nulos y los imputa mediante interpolación
    lineal intragrupo (por departamento).
    """
    rng = np.random.default_rng(seed)
    años = list(range(2010, 2025))
    n_obs = len(DEPARTAMENTOS) * len(años)

    # ---- Parámetros base por departamento (heterogeneidad estructural) ----
    base_pib = rng.uniform(8_000, 180_000, size=len(DEPARTAMENTOS))
    base_homicidio = rng.uniform(8, 65, size=len(DEPARTAMENTOS))
    base_inversion = rng.uniform(80_000, 2_500_000, size=len(DEPARTAMENTOS))
    base_ipm = rng.uniform(12, 55, size=len(DEPARTAMENTOS))
    base_desempleo = rng.uniform(6, 18, size=len(DEPARTAMENTOS))
    base_cobertura = rng.uniform(45, 92, size=len(DEPARTAMENTOS))

    # Tendencias suaves + ruido
    records = []
    for i, depto in enumerate(DEPARTAMENTOS):
        for t, año in enumerate(años):
            # Tendencia temporal (crecimiento / reducción estructural)
            trend = (año - 2010) / 14.0  # 0 → 1

            pib = base_pib[i] * (1 + 0.035 * trend + rng.normal(0, 0.04))
            hom = base_homicidio[i] * (1 - 0.25 * trend + rng.normal(0, 0.08))
            inv = base_inversion[i] * (1 + 0.045 * trend + rng.normal(0, 0.06))
            ipm = base_ipm[i] * (1 - 0.30 * trend + rng.normal(0, 0.05))
            des = base_desempleo[i] * (1 - 0.15 * trend + rng.normal(0, 0.07))
            cob = base_cobertura[i] * (1 + 0.20 * trend + rng.normal(0, 0.04))

            # Restricciones de dominio
            hom = max(3.0, min(hom, 90))
            ipm = max(5.0, min(ipm, 70))
            des = max(3.5, min(des, 25))
            cob = max(30.0, min(cob, 99))

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

    # ---- Introducir ~3 % de valores nulos de forma aleatoria ----
    cols_numericas = [
        "pib_mil_millones", "tasa_homicidios", "inversion_dnp",
        "ipm_porcentaje", "tasa_desempleo", "cobertura_educacion_media",
    ]
    mask = rng.random(df[cols_numericas].shape) < 0.03
    df[cols_numericas] = df[cols_numericas].mask(mask)

    # ---- Imputación: interpolación lineal + bfill + ffill por departamento ----
    df[cols_numericas] = (
        df.groupby("departamento")[cols_numericas]
          .transform(lambda x: x.interpolate(method="linear").bfill().ffill())
    )

    # Asegurar tipos
    df["año"] = df["año"].astype(int)
    df = df.sort_values(["departamento", "año"]).reset_index(drop=True)
    return df


# =============================================================================
# 5. CARGA DE GEOJSON (con fallback defensivo)
# =============================================================================
@st.cache_data(show_spinner="Cargando geometrías departamentales…")
def cargar_geojson() -> Optional[dict]:
    """
    Intenta descargar un GeoJSON oficial de departamentos de Colombia.
    Si falla la red, genera un GeoJSON mínimo (polígonos rectangulares)
    suficiente para que el mapa no se rompa.
    """
    urls = [
        "https://gist.githubusercontent.com/john-guerra/43c7656821069d00dcbc/raw/3a0f40d0a0a8d1d6d0a0c0d0a0a0a0a0a0a0a0a0/colombia.geojson",
        "https://raw.githubusercontent.com/datasets-colombia/departamentos/main/departamentos.geojson",
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                geo = r.json()
                return geo
        except Exception:
            continue

    # ---- Fallback local: GeoJSON sintético (bounding boxes aproximados) ----
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
        delta = 0.6
        poly = [
            [lon - delta, lat - delta],
            [lon + delta, lat - delta],
            [lon + delta, lat + delta],
            [lon - delta, lat + delta],
            [lon - delta, lat - delta],
        ]
        features.append({
            "type": "Feature",
            "properties": {"NOMBRE_DPT": depto, "DPTO": depto},
            "geometry": {"type": "Polygon", "coordinates": [poly]},
        })

    return {"type": "FeatureCollection", "features": features}


# =============================================================================
# 6. UTILIDADES DE BENCHMARKING Y SEMAFORIZACIÓN
# =============================================================================
def calcular_benchmark(
    valor: float,
    promedio_nacional: float,
    mejor_cuando: str,
) -> Tuple[float, str, str]:
    """
    Calcula la diferencia porcentual respecto al promedio nacional y
    asigna color + etiqueta de semaforización.
    Retorna: (diff_pct, clase_css, texto)
    """
    if promedio_nacional == 0 or pd.isna(promedio_nacional) or pd.isna(valor):
        return 0.0, "kpi-neutral", "Sin dato nacional"

    diff_pct = ((valor - promedio_nacional) / abs(promedio_nacional)) * 100

    # Interpretación según si “más alto es mejor” o “más bajo es mejor”
    if mejor_cuando == "alto":
        if diff_pct >= 5:
            return diff_pct, "kpi-positive", f"▲ {diff_pct:+.1f}% vs promedio nacional"
        elif diff_pct <= -5:
            return diff_pct, "kpi-negative", f"▼ {diff_pct:+.1f}% vs promedio nacional"
        else:
            return diff_pct, "kpi-neutral", f"≈ {diff_pct:+.1f}% vs promedio nacional"
    else:  # mejor_cuando == "bajo"
        if diff_pct <= -5:
            return diff_pct, "kpi-positive", f"▼ {diff_pct:+.1f}% vs promedio nacional (mejor)"
        elif diff_pct >= 5:
            return diff_pct, "kpi-negative", f"▲ {diff_pct:+.1f}% vs promedio nacional (peor)"
        else:
            return diff_pct, "kpi-neutral", f"≈ {diff_pct:+.1f}% vs promedio nacional"


def render_kpi_card(
    titulo: str,
    valor: float,
    formato: str,
    diff_pct: float,
    clase: str,
    texto_bench: str,
    help_text: str,
) -> None:
    """Renderiza una tarjeta KPI con borde lateral y subtítulo de semáforo."""
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
# 7. COMPONENTES DE VISUALIZACIÓN
# =============================================================================
def crear_mapa_coropletico(
    df_año: pd.DataFrame,
    geojson: dict,
    variable: str,
    año: int,
) -> go.Figure:
    """Mapa coroplético departamental con Plotly."""
    meta = METADATA_VARIABLES[variable]

    # Intentar mapear nombres (algunos GeoJSON usan DPTO o NOMBRE_DPT)
    feature_key = None
    if geojson and "features" in geojson and geojson["features"]:
        props = geojson["features"][0].get("properties", {})
        for k in ["NOMBRE_DPT", "DPTO", "name", "NOMBRE", "departamento"]:
            if k in props:
                feature_key = k
                break

    fig = px.choropleth(
        df_año,
        geojson=geojson,
        locations="departamento",
        featureidkey=f"properties.{feature_key}" if feature_key else "properties.NOMBRE_DPT",
        color=variable,
        color_continuous_scale="Blues" if meta["mejor_cuando"] == "alto" else "Reds_r",
        range_color=(df_año[variable].min(), df_año[variable].max()),
        hover_name="departamento",
        hover_data={variable: ":.1f", "departamento": False},
        labels={variable: meta["nombre"]},
        title=f"{meta['nombre']} – {año}",
    )
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(
            title=meta["unidad"],
            thickness=12,
            len=0.6,
        ),
        height=520,
        font=dict(family="Inter, sans-serif", size=12),
    )
    return fig


def crear_serie_temporal(
    df_depto: pd.DataFrame,
    df_nacional: pd.DataFrame,
    variable: str,
    depto: str,
) -> go.Figure:
    """Serie de tiempo departamento vs promedio nacional."""
    meta = METADATA_VARIABLES[variable]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_depto["año"],
        y=df_depto[variable],
        mode="lines+markers",
        name=depto,
        line=dict(color="#2563EB", width=3),
        marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=df_nacional["año"],
        y=df_nacional[variable],
        mode="lines",
        name="Promedio Nacional",
        line=dict(color="#0D9488", width=2, dash="dash"),
    ))
    fig.update_layout(
        title=f"Evolución de {meta['nombre']}",
        xaxis_title="Año",
        yaxis_title=meta["unidad"],
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=40, r=20, t=60, b=40),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


def crear_ranking_horizontal(
    df_año: pd.DataFrame,
    variable: str,
    depto_seleccionado: str,
) -> go.Figure:
    """Barras horizontales de ranking departamental."""
    meta = METADATA_VARIABLES[variable]
    df_sorted = df_año.sort_values(variable, ascending=(meta["mejor_cuando"] == "bajo"))

    colors = [
        "#2563EB" if d == depto_seleccionado else "#94A3B8"
        for d in df_sorted["departamento"]
    ]

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
        height=700,
        margin=dict(l=140, r=40, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=11),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


# =============================================================================
# 8. APLICACIÓN PRINCIPAL
# =============================================================================
def main():
    # ---- Carga de datos ----
    df = generar_dataset_maestro()
    geojson = cargar_geojson()

    # ---- Sidebar ----
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
            index=DEPARTAMENTOS.index("Bogotá D.C.") if "Bogotá D.C." in DEPARTAMENTOS else 0,
        )
        variable_sel = st.selectbox(
            "Variable principal",
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
        st.markdown(
            f"<span class='source-badge'>{meta['fuente']}</span>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.caption("Datos sintéticos 2010-2024 · Imputación lineal intragrupo · Benchmarking en tiempo real")

    # ---- Filtros derivados ----
    df_año = df[df["año"] == año_sel].copy()
    df_depto = df[df["departamento"] == depto_sel].copy()
    df_nacional = (
        df.groupby("año")[VARIABLES_ORDEN]
          .mean()
          .reset_index()
    )

    # Promedios nacionales del año seleccionado
    prom_nac = df_año[VARIABLES_ORDEN].mean()

    # ---- Header ----
    st.markdown(
        f"# Observatorio de Analítica Económica y Social"
    )
    st.markdown(
        f"#### {depto_sel} · Año {año_sel} · Benchmarking vs promedio nacional"
    )
    st.markdown("")

    # ---- KPI Cards (6 variables) ----
    st.markdown("### Indicadores Clave de Desempeño (KPI)")
    cols = st.columns(3)
    for idx, var in enumerate(VARIABLES_ORDEN):
        with cols[idx % 3]:
            valor = df_año.loc[df_año["departamento"] == depto_sel, var].values
            valor = valor[0] if len(valor) > 0 else np.nan
            meta = METADATA_VARIABLES[var]
            diff, clase, texto = calcular_benchmark(
                valor, prom_nac[var], meta["mejor_cuando"]
            )
            help_txt = (
                f"{meta['significado']}\n\n"
                f"Impacto: {meta['impacto']}\n\n"
                f"Fuente: {meta['fuente']}"
            )
            render_kpi_card(
                titulo=meta["nombre"],
                valor=valor,
                formato=meta["formato"],
                diff_pct=diff,
                clase=clase,
                texto_bench=texto,
                help_text=help_txt,
            )

    st.markdown("---")

    # ---- Tabs de análisis ----
    tab_mapa, tab_serie, tab_ranking, tab_tabla, tab_glosario = st.tabs(
        ["🗺️ Mapa Territorial", "📈 Serie Temporal", "🏆 Ranking", "📋 Tabla Completa", "📖 Glosario Metodológico"]
    )

    with tab_mapa:
        st.markdown(f"#### Distribución espacial – {METADATA_VARIABLES[variable_sel]['nombre']}")
        if geojson:
            fig_mapa = crear_mapa_coropletico(df_año, geojson, variable_sel, año_sel)
            st.plotly_chart(fig_mapa, use_container_width=True)
        else:
            st.warning("No se pudo cargar el GeoJSON. Muestra solo datos tabulares.")
            st.dataframe(
                df_año[["departamento", variable_sel]].sort_values(
                    variable_sel, ascending=False
                ),
                use_container_width=True,
            )

    with tab_serie:
        fig_serie = crear_serie_temporal(df_depto, df_nacional, variable_sel, depto_sel)
        st.plotly_chart(fig_serie, use_container_width=True)

        # Mini-tabla de crecimiento
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

    with tab_ranking:
        fig_rank = crear_ranking_horizontal(df_año, variable_sel, depto_sel)
        st.plotly_chart(fig_rank, use_container_width=True)

    with tab_tabla:
        st.markdown(f"#### Datos del año {año_sel}")
        st.dataframe(
            df_año.style.format({
                v: METADATA_VARIABLES[v]["formato"] for v in VARIABLES_ORDEN
            }),
            use_container_width=True,
            height=500,
        )
        csv = df_año.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Descargar CSV del año seleccionado",
            data=csv,
            file_name=f"observatorio_colombia_{año_sel}.csv",
            mime="text/csv",
        )

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
                st.markdown(
                    f"**Orientación de deseabilidad**  \n"
                    f"{'Mayor valor es preferible' if meta['mejor_cuando'] == 'alto' else 'Menor valor es preferible'}"
                )

    # ---- Footer ----
    st.markdown(
        """
        <div class="footer">
            Observatorio de Analítica Económica y Social por Departamentos en Colombia<br>
            Datos sintéticos generados con semilla reproducible · Imputación lineal por grupo · 
            Benchmarking dinámico vs promedio nacional · Diseño Think Tank
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
