"""
Observatorio de Analítica Económica y Social por Departamentos en Colombia
==========================================================================
Datos REALES (sin series sintéticas):
  - PIB: datos.gov.co kgyi-qc7j (suma actividades, precios corrientes)
  - Homicidios: datos.gov.co m8fd-ahd9 (MinDefensa, conteo de víctimas)
  - Cobertura neta media: datos.gov.co sras-4t5p (MEN, ETC departamentales)
  - IPM: anexo oficial DANE anex-PMultidimensional-Departamental-2025.xlsx
  - Tasa de desempleo: anexo oficial DANE anex-GEIHDepartamentos-2025.xls (23 depts.)
  - Inversión DNP agregada: no hay serie anual departamental estable en API abierta
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import unicodedata
import re
import io
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
    .stApp { background-color: #F8FAFC; color: #0F172A; }

    /* —— Sidebar —— */
    [data-testid="stSidebar"] { background-color: #0F172A !important; }
    [data-testid="stSidebar"] > div:first-child { background-color: #0F172A !important; }
    [data-testid="stSidebar"] label { color: #94A3B8 !important; font-weight: 600 !important; font-size: 0.85rem !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] .stMarkdown { color: #E2E8F0 !important; }
    [data-testid="stSidebar"] .stCaption { color: #94A3B8 !important; }

    /* Selectboxes in sidebar: dark surface, light text */
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #1E293B !important; border: 1px solid #475569 !important;
        border-radius: 10px !important; color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div { color: #F8FAFC !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #F8FAFC !important; }

    /* Dropdown menus */
    div[data-baseweb="popover"] { z-index: 10000 !important; }
    div[data-baseweb="popover"] ul { background-color: #1E293B !important; border: 1px solid #475569 !important; }
    div[data-baseweb="popover"] li { background-color: #1E293B !important; color: #F8FAFC !important; }
    div[data-baseweb="popover"] li span { color: #F8FAFC !important; }
    div[data-baseweb="popover"] li:hover { background-color: #334155 !important; }

    /* Main area selectboxes / inputs: light surface, dark text */
    [data-testid="stAppViewContainer"] [data-baseweb="select"] > div {
        background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important; color: #0F172A !important;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="select"] span { color: #0F172A !important; }

    /* Sliders: readable labels and track */
    [data-testid="stSlider"] label { color: #334155 !important; font-weight: 600 !important; }
    [data-testid="stSlider"] [data-testid="stTickBarMin"],
    [data-testid="stSlider"] [data-testid="stTickBarMax"] { color: #64748B !important; }
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #2563EB !important; border-color: #2563EB !important;
    }
    div[data-baseweb="slider"] [data-testid="stThumbValue"] {
        background: #2563EB !important; color: #FFFFFF !important; border-radius: 6px;
        padding: 2px 6px; font-weight: 600;
    }

    /* Expanders sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #1E293B !important; border: 1px solid #334155 !important; border-radius: 10px;
    }

    /* —— Hero —— */
    .hero-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #1E3A5F 100%);
        border-radius: 16px; padding: 32px 36px; margin-bottom: 22px; color: #F8FAFC;
        box-shadow: 0 12px 28px -6px rgba(15, 23, 42, 0.4);
        position: relative; overflow: hidden;
    }
    .hero-container::after {
        content: ''; position: absolute; right: -40px; top: -40px;
        width: 180px; height: 180px; border-radius: 50%;
        background: radial-gradient(circle, rgba(37,99,235,0.25) 0%, transparent 70%);
    }
    .hero-title { font-size: 1.85rem; font-weight: 800; margin: 0 0 8px 0; color: #FFFFFF !important; letter-spacing: -0.02em; }
    .hero-subtitle { font-size: 1.05rem; color: #94A3B8; margin: 0 0 18px 0; line-height: 1.55; max-width: 820px; }
    .hero-meta { display: flex; flex-wrap: wrap; gap: 10px; }
    .hero-chip {
        background: rgba(37, 99, 235, 0.3); border: 1px solid rgba(37, 99, 235, 0.55);
        color: #93C5FD; font-size: 0.8rem; font-weight: 600; padding: 7px 14px; border-radius: 9999px;
    }
    .hero-chip-teal {
        background: rgba(13, 148, 136, 0.28); border: 1px solid rgba(13, 148, 136, 0.5); color: #5EEAD4;
    }
    .hero-chip-amber {
        background: rgba(245, 158, 11, 0.22); border: 1px solid rgba(245, 158, 11, 0.45); color: #FCD34D;
    }

    /* —— Cards —— */
    .kpi-card {
        background: #FFFFFF; border-left: 5px solid #2563EB; padding: 20px 22px;
        border-radius: 12px; box-shadow: 0 4px 14px -4px rgba(15,23,42,0.08);
        margin-bottom: 14px; transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px -4px rgba(15,23,42,0.12); }
    .kpi-title { font-size: 0.75rem; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin: 0; }
    .kpi-value { font-size: 1.65rem; color: #0F172A; font-weight: 700; margin: 8px 0 4px 0; letter-spacing: -0.02em; }
    .kpi-subtitle { font-size: 0.8rem; font-weight: 500; margin: 0; }
    .kpi-positive { color: #059669; }
    .kpi-negative { color: #DC2626; }
    .kpi-neutral { color: #64748B; }
    .kpi-na { color: #94A3B8; }

    .guide-card {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px;
        padding: 22px 24px; height: 100%; box-shadow: 0 2px 8px rgba(15,23,42,0.04);
        transition: border-color 0.15s ease;
    }
    .guide-card:hover { border-color: #2563EB; }
    .guide-icon { font-size: 1.6rem; margin-bottom: 8px; }
    .guide-title { font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0 0 8px 0; }
    .guide-text { font-size: 0.9rem; color: #64748B; line-height: 1.5; margin: 0; }

    .info-box {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
        padding: 16px 18px; margin-bottom: 12px;
    }
    .source-badge {
        display: inline-block; background: #E0F2FE; color: #0369A1; font-size: 0.7rem;
        padding: 3px 10px; border-radius: 9999px; font-weight: 600;
    }
    .warn-box {
        background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 14px 18px;
        border-radius: 10px; margin: 14px 0; color: #92400E; font-size: 0.9rem; line-height: 1.45;
    }
    .ok-box {
        background: #ECFDF5; border-left: 4px solid #10B981; padding: 14px 18px;
        border-radius: 10px; margin: 14px 0; color: #065F46; font-size: 0.9rem;
    }

    h1, h2, h3 { color: #0F172A !important; font-weight: 700 !important; letter-spacing: -0.02em; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background: #E2E8F0; border-radius: 10px 10px 0 0; padding: 11px 18px;
        font-weight: 600; color: #475569 !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important; color: #FFFFFF !important;
    }

    .footer {
        text-align: center; color: #64748B; font-size: 0.8rem; padding: 28px 0 12px 0;
        border-top: 1px solid #E2E8F0; margin-top: 40px;
    }
    .section-label {
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.08em; color: #64748B; margin-bottom: 6px;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============================================================================
# METADATOS
# =============================================================================
METADATA_VARIABLES: Dict[str, Dict] = {
    "pib_mil_millones": {
        "nombre": "PIB Departamental (Miles de Millones COP)",
        "significado": "Suma del valor de actividades económicas + impuestos a precios corrientes.",
        "impacto": "Tamaño de la economía regional y base productiva/tributaria.",
        "fuente": "DANE · anex-PIBDep-TotalDep-2025pr.xlsx (Cuadro 1, precios corrientes, 2005–2025pr)",
        "unidad": "Miles de millones COP corrientes",
        "mejor_cuando": "alto",
        "formato": "{:,.1f}",
        "disponible": True,
    },
    "homicidios_cantidad": {
        "nombre": "Homicidios (número de víctimas)",
        "significado": "Conteo anual de víctimas de homicidio intencional por departamento.",
        "impacto": "Seguridad ciudadana. (La tasa por 100.000 requiere población DANE aparte.)",
        "fuente": "MinDefensa · datos.gov.co m8fd-ahd9",
        "unidad": "Víctimas",
        "mejor_cuando": "bajo",
        "formato": "{:,.0f}",
        "disponible": True,
    },
    "cobertura_educacion_media": {
        "nombre": "Cobertura Neta Educación Media (%)",
        "significado": "Estudiantes de media en edad teórica / población 15–16. Solo ETC departamentales.",
        "impacto": "Formación de capital humano.",
        "fuente": "MEN · datos.gov.co sras-4t5p + articles-350799_recurso_15.xlsm (Cobertura 2025)",
        "unidad": "%",
        "mejor_cuando": "alto",
        "formato": "{:.1f}%",
        "disponible": True,
    },
    "ipm_porcentaje": {
        "nombre": "Índice de Pobreza Multidimensional (%)",
        "significado": "Incidencia de pobreza multidimensional (Alkire-Foster / ECV-DANE). Dominio Total.",
        "impacto": "Privaciones simultáneas en salud, educación, trabajo y vivienda.",
        "fuente": "DANE · anex-PMultidimensional-Departamental-2025.xlsx (hoja IPM_Departamentos)",
        "unidad": "%",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
        "disponible": True,
    },
    "tasa_desempleo": {
        "nombre": "Tasa de Desempleo / Desocupación (%)",
        "significado": "TD = desocupados / fuerza de trabajo (GEIH anual). Disponible para 23 departamentos.",
        "impacto": "Salud del mercado laboral regional.",
        "fuente": "DANE · anex-GEIHDepartamentos-2025.xls (hoja Departamentos anual)",
        "unidad": "%",
        "mejor_cuando": "bajo",
        "formato": "{:.1f}%",
        "disponible": True,
    },
    "inversion_dnp": {
        "nombre": "Inversión Pública Ejecutada (Millones COP)",
        "significado": "Recursos públicos ejecutados en proyectos de inversión territorial.",
        "impacto": "Palanca de política fiscal e infraestructura.",
        "fuente": "DNP TerriData / Mapa Inversiones (sin serie anual departamental estandarizada en API abierta usable aquí)",
        "unidad": "Millones de pesos",
        "mejor_cuando": "alto",
        "formato": "{:,.0f}",
        "disponible": False,
    },
}


NATIONAL_META = {
    "inflacion_anual": {
        "nombre": "Inflación anual IPC (%)",
        "descripcion": "Variación anual del IPC total nacional (dic/dic). Para el año en curso se usa la variación anual del último mes publicado.",
        "fuente": "DANE · anex-IPC-Indices (serie de empalme 2003–actual)",
        "unidad": "%",
        "formato": "{:.2f}%",
    },
    "trm_promedio": {
        "nombre": "TRM promedio anual (COP/USD)",
        "descripcion": "Promedio anual de la Tasa Representativa del Mercado (dólar).",
        "fuente": "Superintendencia Financiera · datos.gov.co 32sa-8pi3",
        "unidad": "COP por USD",
        "formato": "{:,.2f}",
    },
    "tasa_interes_real": {
        "nombre": "Tasa de interés real (%)",
        "descripcion": "Tasa de interés real (ajuste por inflación). Serie anual compilada por el Banco Mundial a partir de fuentes oficiales.",
        "fuente": "Banco Mundial · FR.INR.RINR (Colombia)",
        "unidad": "%",
        "formato": "{:.2f}%",
    },
    "balanza_cuenta_corriente": {
        "nombre": "Balanza en cuenta corriente (USD)",
        "descripcion": "Saldo de la cuenta corriente de la balanza de pagos (USD corrientes). Negativo = déficit.",
        "fuente": "Banco Mundial · BN.CAB.XOKA.CD (Colombia; basado en BanRep/FMI)",
        "unidad": "USD",
        "formato": "{:,.0f}",
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
    if n.endswith(" ETC"):
        n = n[:-4].strip()
    aliases = {
        "BOGOTA DC": "BOGOTA D C", "BOGOTA D C": "BOGOTA D C", "BOGOTA": "BOGOTA D C",
        "DISTRITO CAPITAL": "BOGOTA D C",
        "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES PROVIDENCIA Y SANTA CATALINA ARCHIPIELAGO": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES": "SAN ANDRES Y PROVIDENCIA",
        "SAN ANDRES Y PROVIDENCIA": "SAN ANDRES Y PROVIDENCIA",
        "NORTE SANTANDER": "NORTE DE SANTANDER",
        "VALLE": "VALLE DEL CAUCA",
    }
    return aliases.get(n, n)


NORM_A_CANONICO = {normalizar_nombre(d): d for d in DEPARTAMENTOS_CANONICOS}


def a_canonico(nombre: str) -> Optional[str]:
    return NORM_A_CANONICO.get(normalizar_nombre(nombre))


SODA = "https://www.datos.gov.co/resource"
HDRS = {"User-Agent": "ObservatorioColombia/1.0 (research; streamlit)"}


# =============================================================================
# LOADERS REALES
# =============================================================================
@st.cache_data(show_spinner="PIB departamental (anexo oficial DANE 2005–2025pr)…", ttl=3600)
def cargar_pib() -> pd.DataFrame:
    """
    Anexo oficial DANE:
    https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx
    Cuadro 1 · PIB a precios corrientes, miles de millones, serie 2005–2025pr.
    (La API kgyi-qc7j solo llega a 2023; este anexo actualiza 2024p y 2025pr.)
    """
    url = "https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx"
    r = requests.get(url, timeout=90, headers=HDRS)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="Cuadro 1", header=None, engine="openpyxl")
    # Fila 9: años (cols 2..). Col 0 código, col 1 nombre.
    # Solo bloque de valores en miles de millones (izq.). El bloque derecho es participación %.
    years_cols = []
    seen = set()
    for j in range(2, df.shape[1]):
        v = df.iloc[9, j]
        if pd.isna(v):
            continue
        m = re.search(r"(20\d{2})", str(v))
        if not m:
            continue
        y = int(m.group(1))
        if y in seen:
            continue  # evita columnas de participación porcentual
        seen.add(y)
        years_cols.append((y, j))
    rows = []
    for i in range(11, df.shape[0]):
        name = df.iloc[i, 1]
        if pd.isna(name):
            continue
        depto = a_canonico(str(name))
        if not depto:
            continue
        for y, c in years_cols:
            val = pd.to_numeric(df.iloc[i, c], errors="coerce")
            if pd.notna(val):
                rows.append({"departamento": depto, "año": y, "pib_mil_millones": float(val)})
    out = pd.DataFrame(rows)
    return out


@st.cache_data(show_spinner="Homicidios MinDefensa (datos.gov.co)…", ttl=3600)
def cargar_homicidios() -> pd.DataFrame:
    frames, offset, page = [], 0, 50000
    while True:
        r = requests.get(
            f"{SODA}/m8fd-ahd9.json",
            params={
                "$select": "departamento,date_trunc_y(fecha_hecho) as anio,sum(cantidad) as total",
                "$group": "departamento,anio",
                "$limit": page,
                "$offset": offset,
            },
            timeout=120,
            headers=HDRS,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        if len(batch) < page:
            break
        offset += page
        if offset > 300000:
            break
    if not frames:
        return pd.DataFrame(columns=["departamento", "año", "homicidios_cantidad"])
    df = pd.concat(frames, ignore_index=True)
    df["año"] = pd.to_datetime(df["anio"], errors="coerce").dt.year
    df["homicidios_cantidad"] = pd.to_numeric(df["total"], errors="coerce")
    df["departamento"] = df["departamento"].map(a_canonico)
    df = df.dropna(subset=["departamento", "año", "homicidios_cantidad"])
    return df.groupby(["departamento", "año"], as_index=False)["homicidios_cantidad"].sum()


@st.cache_data(show_spinner="Cobertura educativa MEN (datos.gov.co + anexo 2025)…", ttl=3600)
def cargar_cobertura_media() -> pd.DataFrame:
    """
    Base histórica: datos.gov.co sras-4t5p (ETC departamentales, hasta 2024).
    Complemento 2025: archivo oficial MEN Cobertura en cifras 2025
    https://www.mineducacion.gov.co/1780/articles-350799_recurso_15.xlsm
    hoja '8 COB NETA' · columna Media (proporción → %).
    """
    frames = []
    # 1) API histórica
    try:
        r = requests.get(
            f"{SODA}/sras-4t5p.json",
            params={
                "$select": "ano,nombre_etc,cobertura_neta_media",
                "$where": "nombre_etc like '%(ETC)%'",
                "$limit": 50000,
            },
            timeout=90,
            headers=HDRS,
        )
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if not df.empty:
            df["año"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int64")
            val = pd.to_numeric(df["cobertura_neta_media"], errors="coerce")
            if val.median(skipna=True) is not None and val.median(skipna=True) <= 2:
                val = val * 100
            df["cobertura_educacion_media"] = val
            df["departamento"] = df["nombre_etc"].map(a_canonico)
            df = df.dropna(subset=["departamento", "año", "cobertura_educacion_media"])
            frames.append(df[["departamento", "año", "cobertura_educacion_media"]])
    except Exception:
        pass

    # 2) Anexo MEN 2025 (y años en el mismo bloque si aparecen)
    try:
        url = "https://www.mineducacion.gov.co/1780/articles-350799_recurso_15.xlsm"
        r = requests.get(url, timeout=180, headers=HDRS)
        r.raise_for_status()
        raw = pd.read_excel(io.BytesIO(r.content), sheet_name="8 COB NETA", header=None, engine="openpyxl")
        rows = []
        current_etc = None
        for i in range(len(raw)):
            # nombre ETC suele estar en col 1 o 2
            for col in (1, 2):
                cell = raw.iloc[i, col] if col < raw.shape[1] else None
                if pd.isna(cell):
                    continue
                s = str(cell).strip()
                # detectar entidad (texto no numérico, no 'AÑO', no 'Variación')
                if s and not s.replace(".", "").replace("-", "").isdigit() and s.upper() not in (
                    "AÑO", "ANO", "ENTIDAD", "TRANSICIÓN", "TRANSICION", "PRIMARIA",
                    "SECUNDARIA", "MEDIA", "BASICA", "BÁSICA", "TOTAL", "COBERTURA NETA",
                ) and not s.lower().startswith("variación") and not s.lower().startswith("fuente"):
                    # posible nombre de ETC
                    depto = a_canonico(s)
                    if depto:
                        current_etc = depto
            # filas de año
            año_cell = raw.iloc[i, 2] if raw.shape[1] > 2 else None
            try:
                año_val = int(float(año_cell)) if pd.notna(año_cell) else None
            except Exception:
                año_val = None
            if current_etc and año_val and 2010 <= año_val <= 2026:
                media = pd.to_numeric(raw.iloc[i, 6], errors="coerce")  # col Media
                if pd.notna(media):
                    if media <= 2:
                        media = media * 100
                    rows.append({
                        "departamento": current_etc,
                        "año": año_val,
                        "cobertura_educacion_media": float(media),
                    })
        if rows:
            frames.append(pd.DataFrame(rows))
    except Exception:
        pass

    if not frames:
        return pd.DataFrame(columns=["departamento", "año", "cobertura_educacion_media"])
    out = pd.concat(frames, ignore_index=True)
    # Preferir valor más reciente de fuente MEN si hay duplicados año-depto
    out = out.drop_duplicates(subset=["departamento", "año"], keep="last")
    return out


@st.cache_data(show_spinner="IPM departamental (anexo oficial DANE)…", ttl=3600)
def cargar_ipm() -> pd.DataFrame:
    """
    Anexo oficial:
    https://www.dane.gov.co/files/operaciones/PM/anex-PMultidimensional-Departamental-2025.xlsx
    Hoja IPM_Departamentos · incidencia Total 2018–2025.
    """
    url = "https://www.dane.gov.co/files/operaciones/PM/anex-PMultidimensional-Departamental-2025.xlsx"
    r = requests.get(url, timeout=90, headers=HDRS)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="IPM_Departamentos", header=None, engine="openpyxl")
    # Fila 11: años; fila 12: Total / Cabeceras / Rural; datos desde 13
    year_row = df.iloc[11]
    years_cols: List[Tuple[int, int]] = []
    for j in range(1, df.shape[1]):
        v = year_row.iloc[j]
        if pd.isna(v):
            continue
        m = re.search(r"(20\d{2})", str(v))
        if not m:
            continue
        lab = str(df.iloc[12, j]).strip().lower() if pd.notna(df.iloc[12, j]) else ""
        if lab.startswith("total"):
            years_cols.append((int(m.group(1)), j))
    rows = []
    for i in range(13, df.shape[0]):
        name = df.iloc[i, 0]
        if pd.isna(name):
            continue
        depto = a_canonico(str(name))
        if not depto:
            continue
        for y, c in years_cols:
            val = pd.to_numeric(df.iloc[i, c], errors="coerce")
            if pd.notna(val):
                rows.append({"departamento": depto, "año": y, "ipm_porcentaje": float(val)})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Tasa de desempleo GEIH (anexo oficial DANE)…", ttl=3600)
def cargar_desempleo() -> pd.DataFrame:
    """
    Anexo oficial:
    https://www.dane.gov.co/files/operaciones/GEIH/anex-GEIHDepartamentos-2025.xls
    Hoja 'Departamentos anual' · Tasa de Desocupación (TD).
    Cobertura: 23 departamentos (serie anual desde ~2007).
    """
    url = "https://www.dane.gov.co/files/operaciones/GEIH/anex-GEIHDepartamentos-2025.xls"
    r = requests.get(url, timeout=120, headers=HDRS)
    r.raise_for_status()
    g = pd.read_excel(io.BytesIO(r.content), sheet_name="Departamentos anual", header=None, engine="xlrd")
    records = []
    i = 0
    while i < len(g):
        cell = g.iloc[i, 0]
        if pd.isna(cell):
            i += 1
            continue
        depto = a_canonico(str(cell))
        if not depto:
            i += 1
            continue
        years = None
        for k in range(i + 1, min(i + 20, len(g))):
            rowvals = [g.iloc[k, j] for j in range(1, g.shape[1])]
            if years is None and any(
                isinstance(v, (int, float)) and not isinstance(v, bool) and 2005 <= float(v) <= 2026
                for v in rowvals if pd.notna(v)
            ):
                years = []
                for j in range(1, g.shape[1]):
                    v = g.iloc[k, j]
                    if pd.notna(v):
                        try:
                            yv = float(v)
                            if 2005 <= yv <= 2026:
                                years.append((int(yv), j))
                        except Exception:
                            pass
            lab = str(g.iloc[k, 0]) if pd.notna(g.iloc[k, 0]) else ""
            if "Tasa de Desocupación" in lab or lab.strip() in ("TD", "Tasa de Desempleo"):
                if years:
                    for y, j in years:
                        val = pd.to_numeric(g.iloc[k, j], errors="coerce")
                        if pd.notna(val):
                            records.append({"departamento": depto, "año": y, "tasa_desempleo": float(val)})
                i = k + 1
                break
        else:
            i += 1
    return pd.DataFrame(records)



@st.cache_data(show_spinner="Inflación IPC nacional (anexo DANE)…", ttl=3600)
def cargar_inflacion_nacional() -> pd.DataFrame:
    """
    Índice IPC nacional (serie de empalme). Inflación anual = (Dic_t / Dic_{t-1} - 1)*100.
    Para el año corriente (sin diciembre): variación anual del último mes disponible
    respecto al mismo mes del año anterior.
    """
    # Intentar meses recientes del patrón de anexos DANE
    candidates = []
    from datetime import datetime
    now = datetime.utcnow()
    meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    # probar últimos 6 meses de ruta sep2026-style
    for back in range(0, 8):
        y = now.year
        m = now.month - 1 - back
        while m <= 0:
            m += 12
            y -= 1
        tag = f"{meses[m-1]}{y}"
        candidates.append(
            f"https://www.dane.gov.co/files/operaciones/IPC/{tag}/anex-IPC-Indices-{tag}.xlsx"
        )
    # fallbacks conocidos
    candidates.extend([
        "https://www.dane.gov.co/files/operaciones/IPC/sep2026/anex-IPC-Indices-sep2026.xlsx",
        "https://www.dane.gov.co/files/operaciones/IPC/ago2026/anex-IPC-Indices-ago2026.xlsx",
        "https://www.dane.gov.co/files/operaciones/IPC/jul2026/anex-IPC-Indices-jul2026.xlsx",
    ])
    content = None
    for url in candidates:
        try:
            r = requests.get(url, timeout=45, headers=HDRS)
            if r.status_code == 200 and len(r.content) > 5000:
                content = r.content
                break
        except Exception:
            continue
    if content is None:
        return pd.DataFrame(columns=["año", "inflacion_anual"])

    df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="openpyxl")
    # fila 8 = años; filas 9-20 = meses
    year_row = df.iloc[8]
    years = []
    for j in range(1, df.shape[1]):
        v = year_row.iloc[j]
        if pd.isna(v):
            continue
        try:
            years.append((int(float(v)), j))
        except Exception:
            continue
    # mapa mes -> fila
    mes_fila = {}
    for i in range(9, min(22, len(df))):
        lab = str(df.iloc[i, 0]).strip().lower() if pd.notna(df.iloc[i, 0]) else ""
        if lab:
            mes_fila[lab] = i
    # construir serie mensual índice
    records = []
    for y, j in years:
        for mes_name, i in mes_fila.items():
            val = pd.to_numeric(df.iloc[i, j], errors="coerce")
            if pd.notna(val):
                records.append({"año": y, "mes": mes_name, "indice": float(val)})
    if not records:
        return pd.DataFrame(columns=["año", "inflacion_anual"])
    ser = pd.DataFrame(records)
    # inflación dic/dic
    dic = ser[ser["mes"].str.contains("iciembre", case=False, na=False)].set_index("año")["indice"].sort_index()
    rows = []
    for y in dic.index:
        if y - 1 in dic.index and dic.loc[y - 1] != 0:
            rows.append({"año": int(y), "inflacion_anual": (dic.loc[y] / dic.loc[y - 1] - 1) * 100})
    # año corriente: último mes vs mismo mes año anterior
    max_y = int(ser["año"].max())
    if max_y not in [r["año"] for r in rows]:
        cur = ser[ser["año"] == max_y]
        if not cur.empty:
            # último mes con dato
            order = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
            cur = cur.copy()
            cur["_ord"] = cur["mes"].str.lower().map({m: i for i, m in enumerate(order)})
            last = cur.sort_values("_ord").iloc[-1]
            prev = ser[(ser["año"] == max_y - 1) & (ser["mes"] == last["mes"])]
            if not prev.empty and prev.iloc[0]["indice"] != 0:
                rows.append({
                    "año": max_y,
                    "inflacion_anual": (last["indice"] / prev.iloc[0]["indice"] - 1) * 100,
                })
    return pd.DataFrame(rows).sort_values("año")


@st.cache_data(show_spinner="TRM promedio anual (datos.gov.co)…", ttl=3600)
def cargar_trm_anual() -> pd.DataFrame:
    """Promedio anual de TRM diaria (Superintendencia Financiera)."""
    frames, offset, page = [], 0, 50000
    while True:
        r = requests.get(
            f"{SODA}/32sa-8pi3.json",
            params={
                "$select": "vigenciadesde,valor",
                "$limit": page,
                "$offset": offset,
                "$order": "vigenciadesde",
            },
            timeout=90,
            headers=HDRS,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        frames.append(pd.DataFrame(batch))
        if len(batch) < page:
            break
        offset += page
        if offset > 200000:
            break
    if not frames:
        return pd.DataFrame(columns=["año", "trm_promedio"])
    df = pd.concat(frames, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["vigenciadesde"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["fecha", "valor"])
    df["año"] = df["fecha"].dt.year
    out = df.groupby("año", as_index=False)["valor"].mean()
    out = out.rename(columns={"valor": "trm_promedio"})
    return out


@st.cache_data(show_spinner="Indicadores nacionales (Banco Mundial)…", ttl=3600)
def cargar_wb_nacional() -> pd.DataFrame:
    """
    Series anuales Colombia vía API Banco Mundial (compilación de fuentes oficiales
    BanRep/FMI/DANE). Se usan porque la API pública de BanRep (Totoro/Suameca)
    está en mantenimiento o con restricciones SSL en este entorno.
    """
    indicators = {
        "tasa_interes_real": "FR.INR.RINR",
        "balanza_cuenta_corriente": "BN.CAB.XOKA.CD",
    }
    frames = []
    for col, code in indicators.items():
        try:
            r = requests.get(
                f"https://api.worldbank.org/v2/country/COL/indicator/{code}",
                params={"format": "json", "per_page": 80},
                timeout=30,
                headers=HDRS,
            )
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                continue
            rows = []
            for item in data[1]:
                if item.get("value") is None:
                    continue
                rows.append({"año": int(item["date"]), col: float(item["value"])})
            if rows:
                frames.append(pd.DataFrame(rows))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["año", "tasa_interes_real", "balanza_cuenta_corriente"])
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="año", how="outer")
    return out.sort_values("año")


@st.cache_data(show_spinner="Consolidando indicadores nacionales…", ttl=3600)
def construir_nacional() -> Tuple[pd.DataFrame, Dict[str, str]]:
    estados = {}
    base = None
    try:
        inf = cargar_inflacion_nacional()
        estados["inflacion_anual"] = f"OK · {len(inf)} años"
        base = inf if base is None else base.merge(inf, on="año", how="outer")
    except Exception as e:
        estados["inflacion_anual"] = f"Error: {type(e).__name__}: {e}"
    try:
        trm = cargar_trm_anual()
        estados["trm_promedio"] = f"OK · {len(trm)} años"
        base = trm if base is None else base.merge(trm, on="año", how="outer")
    except Exception as e:
        estados["trm_promedio"] = f"Error: {type(e).__name__}: {e}"
    try:
        wb = cargar_wb_nacional()
        estados["tasa_interes_real"] = f"OK · {wb['tasa_interes_real'].notna().sum() if 'tasa_interes_real' in wb else 0} años"
        estados["balanza_cuenta_corriente"] = f"OK · {wb['balanza_cuenta_corriente'].notna().sum() if 'balanza_cuenta_corriente' in wb else 0} años"
        base = wb if base is None else base.merge(wb, on="año", how="outer")
    except Exception as e:
        estados["tasa_interes_real"] = f"Error: {e}"
        estados["balanza_cuenta_corriente"] = f"Error: {e}"
    if base is None:
        base = pd.DataFrame(columns=["año"])
    return base.sort_values("año").reset_index(drop=True), estados


@st.cache_data(show_spinner="Integrando panel territorial real…", ttl=3600)
def construir_panel() -> Tuple[pd.DataFrame, Dict[str, str]]:
    estados: Dict[str, str] = {}
    frames = []

    loaders = [
        ("pib_mil_millones", cargar_pib),
        ("homicidios_cantidad", cargar_homicidios),
        ("cobertura_educacion_media", cargar_cobertura_media),
        ("ipm_porcentaje", cargar_ipm),
        ("tasa_desempleo", cargar_desempleo),
    ]
    for col, fn in loaders:
        try:
            d = fn()
            estados[col] = f"OK · {len(d)} filas · {d['departamento'].nunique() if not d.empty else 0} deptos"
            if not d.empty:
                frames.append(d)
        except Exception as e:
            estados[col] = f"Error: {type(e).__name__}: {e}"
    estados["inversion_dnp"] = "No disponible: sin serie anual departamental estandarizada en API abierta"

    años = set()
    for d in frames:
        años.update(d["año"].dropna().astype(int).tolist())
    if not años:
        años = set(range(2010, 2025))
    años = sorted(a for a in años if 2005 <= a <= 2026)

    base = pd.MultiIndex.from_product(
        [DEPARTAMENTOS_CANONICOS, años], names=["departamento", "año"]
    ).to_frame(index=False)
    for d in frames:
        base = base.merge(d, on=["departamento", "año"], how="left")
    if "inversion_dnp" not in base.columns:
        base["inversion_dnp"] = np.nan
    base["año"] = base["año"].astype(int)
    return base.sort_values(["departamento", "año"]).reset_index(drop=True), estados


@st.cache_data(show_spinner="Geometrías…", ttl=86400)
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
            r = requests.get(fuente["url"], timeout=15, headers=HDRS)
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
        poly = [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]
        feats.append({
            "type": "Feature",
            "properties": {"_NOM_NORM": normalizar_nombre(depto)},
            "geometry": {"type": "Polygon", "coordinates": [poly]},
        })
    return {"type": "FeatureCollection", "features": feats}, "_NOM_NORM"


def calcular_benchmark(valor, promedio, mejor_cuando):
    if promedio == 0 or pd.isna(promedio) or pd.isna(valor):
        return 0.0, "kpi-na", "Sin dato comparable"
    diff = ((valor - promedio) / abs(promedio)) * 100
    if mejor_cuando == "alto":
        if diff >= 5:
            return diff, "kpi-positive", f"▲ {diff:+.1f}% vs promedio (depts. con dato)"
        if diff <= -5:
            return diff, "kpi-negative", f"▼ {diff:+.1f}% vs promedio (depts. con dato)"
        return diff, "kpi-neutral", f"≈ {diff:+.1f}% vs promedio (depts. con dato)"
    if diff <= -5:
        return diff, "kpi-positive", f"▼ {diff:+.1f}% vs promedio (mejor)"
    if diff >= 5:
        return diff, "kpi-negative", f"▲ {diff:+.1f}% vs promedio (peor)"
    return diff, "kpi-neutral", f"≈ {diff:+.1f}% vs promedio"


def render_kpi_card(titulo, valor, formato, clase, texto, disponible):
    if (not disponible) or pd.isna(valor):
        valor_str, texto, clase = "No disponible", "Sin dato en fuentes abiertas cargadas", "kpi-na"
    else:
        valor_str = formato.format(valor)
    st.markdown(
        f"""<div class="kpi-card"><p class="kpi-title">{titulo}</p>
        <p class="kpi-value">{valor_str}</p>
        <p class="kpi-subtitle {clase}">{texto}</p></div>""",
        unsafe_allow_html=True,
    )


def crear_mapa(df_año, geojson, feature_key, variable, año):
    """Choropleth defensivo: si falla el GeoJSON o no hay match, usa barras espaciales."""
    meta = METADATA_VARIABLES[variable]
    df_map = df_año.dropna(subset=[variable]).copy()
    if df_map.empty:
        return None, "sin_datos"

    df_map["_NOM_NORM"] = df_map["departamento"].map(normalizar_nombre)
    use_fallback = False
    fig = None

    if geojson and feature_key:
        try:
            # Verificar overlap de llaves
            geo_keys = set()
            for feat in geojson.get("features", []):
                props = feat.get("properties") or {}
                if feature_key in props:
                    geo_keys.add(str(props[feature_key]))
            data_keys = set(df_map["_NOM_NORM"].astype(str))
            overlap = data_keys & geo_keys
            if len(overlap) < max(3, len(data_keys) // 4):
                use_fallback = True
            else:
                fig = px.choropleth(
                    df_map,
                    geojson=geojson,
                    locations="_NOM_NORM",
                    featureidkey=f"properties.{feature_key}",
                    color=variable,
                    color_continuous_scale="Blues" if meta["mejor_cuando"] == "alto" else "Reds_r",
                    hover_name="departamento",
                    hover_data={variable: ":.2f", "_NOM_NORM": False},
                    labels={variable: meta["nombre"]},
                    title=f"{meta['nombre']} · {año}",
                )
                fig.update_geos(
                    fitbounds="locations",
                    visible=False,
                    bgcolor="rgba(0,0,0,0)",
                    projection_type="mercator",
                )
                fig.update_layout(
                    margin=dict(l=0, r=0, t=55, b=0),
                    height=580,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    coloraxis_colorbar=dict(title=meta["unidad"], thickness=12, len=0.55),
                    font=dict(family="Inter, sans-serif"),
                )
        except Exception:
            use_fallback = True
            fig = None
    else:
        use_fallback = True

    if use_fallback or fig is None:
        d = df_map.sort_values(variable, ascending=(meta["mejor_cuando"] == "bajo"))
        colors = ["#2563EB" if i % 2 == 0 else "#0D9488" for i in range(len(d))]
        fig = go.Figure(go.Bar(
            x=d[variable],
            y=d["departamento"],
            orientation="h",
            marker_color=colors,
            text=d[variable].map(lambda v: meta["formato"].format(v)),
            textposition="outside",
            hovertemplate="%{y}<br>%{x}<extra></extra>",
        ))
        fig.update_layout(
            title=f"{meta['nombre']} · {año}  (vista alternativa por disponibilidad geográfica)",
            height=max(480, 22 * len(d)),
            margin=dict(l=140, r=40, t=55, b=30),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=meta["unidad"],
            yaxis=dict(autorange="reversed"),
            font=dict(family="Inter, sans-serif"),
        )
        fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
        return fig, "fallback_barras"

    return fig, "choropleth"


def crear_serie(df_depto, df_nac, variable, depto):
    meta = METADATA_VARIABLES[variable]
    fig = go.Figure()
    d1 = df_depto.dropna(subset=[variable])
    d2 = df_nac.dropna(subset=[variable])
    if not d1.empty:
        fig.add_trace(go.Scatter(x=d1["año"], y=d1[variable], mode="lines+markers", name=depto,
                                 line=dict(color="#2563EB", width=3)))
    if not d2.empty:
        fig.add_trace(go.Scatter(x=d2["año"], y=d2[variable], mode="lines",
                                 name="Promedio (depts. con dato)",
                                 line=dict(color="#0D9488", width=2, dash="dash")))
    fig.update_layout(title=f"Evolución de {meta['nombre']}", xaxis_title="Año",
                      yaxis_title=meta["unidad"], hovermode="x unified", height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0")
    return fig


def crear_ranking(df_año, variable, depto_sel):
    meta = METADATA_VARIABLES[variable]
    d = df_año.dropna(subset=[variable]).sort_values(variable, ascending=(meta["mejor_cuando"] == "bajo"))
    if d.empty:
        return None
    colors = ["#2563EB" if x == depto_sel else "#94A3B8" for x in d["departamento"]]
    fig = go.Figure(go.Bar(
        x=d[variable], y=d["departamento"], orientation="h", marker_color=colors,
        text=d[variable].map(lambda v: meta["formato"].format(v)), textposition="outside",
    ))
    fig.update_layout(title=f"Ranking – {meta['nombre']}", height=720,
                      margin=dict(l=150, r=40, t=50, b=40),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def main():
    df, estados_carga = construir_panel()
    geojson, feature_key = cargar_geojson()
    df_nac_ind, estados_nac = construir_nacional()

    # —— Sidebar ——
    with st.sidebar:
        st.markdown("## 🇨🇴 Observatorio")
        st.markdown("##### Analítica territorial · datos reales")
        st.markdown("---")
        años_disp = sorted(df["año"].unique(), reverse=True)
        año_sel = st.selectbox(
            "Año de análisis",
            options=años_disp,
            index=0,
            help="Año de referencia para mapa, KPIs y ranking. Los años sin dato oficial quedan vacíos.",
        )
        depto_sel = st.selectbox(
            "Departamento",
            options=sorted(DEPARTAMENTOS_CANONICOS),
            index=sorted(DEPARTAMENTOS_CANONICOS).index("Bogotá D.C."),
            help="Entidad territorial sobre la que se centran KPIs y series.",
        )
        variable_sel = st.selectbox(
            "Variable (mapa / series / ranking)",
            options=VARIABLES_DISPONIBLES,
            format_func=lambda x: METADATA_VARIABLES[x]["nombre"],
            help="Indicador activo en mapa, serie histórica y ranking.",
        )
        st.markdown("---")
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown("#### Ficha técnica")
        st.markdown(f"**{meta['nombre']}**")
        st.caption(meta["significado"])
        with st.expander("Impacto en política pública"):
            st.write(meta["impacto"])
        st.markdown(f"<span class='source-badge'>{meta['fuente']}</span>", unsafe_allow_html=True)
        st.markdown("---")
        with st.expander("Estado de carga territorial"):
            for k, v in estados_carga.items():
                st.caption(f"**{k}**: {v}")
        with st.expander("Estado de carga nacional"):
            for k, v in estados_nac.items():
                st.caption(f"**{k}**: {v}")

    df_año = df[df["año"] == año_sel].copy()
    df_depto = df[df["departamento"] == depto_sel].copy()
    df_nac = df.groupby("año")[VARIABLES_DISPONIBLES].mean(numeric_only=True).reset_index()
    prom_nac = df_año[VARIABLES_DISPONIBLES].mean(numeric_only=True)

    # —— Tabs ——
    tabs = st.tabs([
        "🏠 Bienvenida",
        "📊 KPIs",
        "🗺️ Mapa",
        "📈 Series",
        "🏆 Ranking",
        "📋 Tabla",
        "🌐 Nacional",
        "📚 Fuentes",
    ])
    (tab_inicio, tab_kpi, tab_mapa, tab_serie, tab_ranking,
     tab_tabla, tab_nacional, tab_fuentes) = tabs

    # ========== BIENVENIDA ==========
    with tab_inicio:
        st.markdown(
            f"""
            <div class="hero-container">
                <p class="hero-title">Observatorio de Analítica Económica y Social</p>
                <p class="hero-subtitle">
                    Plataforma de lectura territorial con <strong>cifras oficiales</strong> de DANE,
                    MinDefensa, MEN y Superfinanciera. Diseñada para analistas, gobiernos locales
                    y ciudadanos que necesitan evidencia, no estimaciones inventadas.
                </p>
                <div class="hero-meta">
                    <span class="hero-chip">📍 {depto_sel}</span>
                    <span class="hero-chip">📅 {año_sel}</span>
                    <span class="hero-chip-teal">Datos reales · sin series sintéticas</span>
                    <span class="hero-chip-amber">Think Tank UI</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<p class="section-label">Guía rápida</p>', unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown(
                """<div class="guide-card">
                <div class="guide-icon">🧭</div>
                <p class="guide-title">¿Cómo usar el observatorio?</p>
                <p class="guide-text">
                    1) Elige <strong>año</strong> y <strong>departamento</strong> en la barra lateral.<br>
                    2) Revisa <strong>KPIs</strong> con semáforo vs promedio.<br>
                    3) Explora <strong>mapa</strong>, <strong>series</strong> y <strong>ranking</strong>.
                </p></div>""",
                unsafe_allow_html=True,
            )
        with g2:
            st.markdown(
                """<div class="guide-card">
                <div class="guide-icon">📡</div>
                <p class="guide-title">¿De dónde salen los datos?</p>
                <p class="guide-text">
                    Anexos oficiales DANE (PIB, IPM, GEIH, IPC),
                    datos.gov.co (homicidios, TRM, educación) y
                    MEN (cobertura 2025). Cada KPI cita su fuente.
                </p></div>""",
                unsafe_allow_html=True,
            )
        with g3:
            st.markdown(
                """<div class="guide-card">
                <div class="guide-icon">⚠️</div>
                <p class="guide-title">Limitaciones honestas</p>
                <p class="guide-text">
                    Desempleo GEIH: 23 departamentos.
                    IPC es nacional (no hay serie departamental completa).
                    2026 anual departamental aún no publicado.
                </p></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown(f"#### Resumen rápido · {depto_sel} ({año_sel})")
        cols = st.columns(3)
        for i, var in enumerate(VARIABLES_DISPONIBLES):
            with cols[i % 3]:
                row = df_año.loc[df_año["departamento"] == depto_sel, var]
                val = row.values[0] if len(row) else np.nan
                m = METADATA_VARIABLES[var]
                st.metric(
                    m["nombre"].split("(")[0].strip(),
                    m["formato"].format(val) if not pd.isna(val) else "N/D",
                    help=f"{m['significado']} | Fuente: {m['fuente']}",
                )

        st.markdown(
            """
            <div class="warn-box">
                <strong>Nota metodológica:</strong> el promedio nacional de comparación
                solo incluye departamentos con dato en el año seleccionado.
                No se imputan ni inventan valores faltantes.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ========== KPIs ==========
    with tab_kpi:
        st.markdown(f"### KPIs & benchmarking · {depto_sel} · {año_sel}")
        st.caption("Semaforización: diferencia porcentual frente al promedio de departamentos con dato.")
        cols = st.columns(3)
        for idx, var in enumerate(VARIABLES_ORDEN):
            with cols[idx % 3]:
                meta = METADATA_VARIABLES[var]
                row = (
                    df_año.loc[df_año["departamento"] == depto_sel, var]
                    if var in df_año.columns else pd.Series([np.nan])
                )
                val = row.values[0] if len(row) else np.nan
                prom = prom_nac[var] if var in prom_nac.index else np.nan
                _, clase, texto = calcular_benchmark(val, prom, meta["mejor_cuando"])
                render_kpi_card(meta["nombre"], val, meta["formato"], clase, texto, meta["disponible"])
                with st.expander("Ficha del indicador"):
                    st.markdown(f"**Qué mide:** {meta['significado']}")
                    st.markdown(f"**Impacto:** {meta['impacto']}")
                    st.markdown(f"**Fuente:** {meta['fuente']}")
                    st.markdown(f"**Unidad:** {meta['unidad']}")

    # ========== MAPA ==========
    with tab_mapa:
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown(f"#### {meta['nombre']}")
        st.caption(f"{meta['significado']} · Fuente: {meta['fuente']}")
        fig, modo = crear_mapa(df_año, geojson, feature_key, variable_sel, año_sel)
        if fig is None:
            st.warning(
                "Sin datos para el mapa en este año/variable "
                "(p. ej. desempleo solo en 23 departamentos)."
            )
        else:
            if modo == "fallback_barras":
                st.info(
                    "Vista alternativa: el GeoJSON no coincidió o no está disponible. "
                    "Se muestra ranking espacial en barras para no dejar el panel vacío."
                )
            st.plotly_chart(fig, use_container_width=True)

    # ========== SERIES ==========
    with tab_serie:
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown(f"#### Evolución · {meta['nombre']}")
        st.caption(meta["significado"])
        st.plotly_chart(
            crear_serie(df_depto, df_nac, variable_sel, depto_sel),
            use_container_width=True,
        )
        with st.expander("Cómo leer esta serie"):
            st.write(
                f"La línea azul es **{depto_sel}**. La línea punteada teal es el "
                "promedio de departamentos con dato en cada año. "
                f"Mejor cuando el valor es **{meta['mejor_cuando']}**."
            )

    # ========== RANKING ==========
    with tab_ranking:
        meta = METADATA_VARIABLES[variable_sel]
        st.markdown(f"#### Ranking departamental · {meta['nombre']} · {año_sel}")
        fig = crear_ranking(df_año, variable_sel, depto_sel)
        if fig is None:
            st.warning("Sin datos para ranking en este año/variable.")
        else:
            st.plotly_chart(fig, use_container_width=True)

    # ========== TABLA ==========
    with tab_tabla:
        st.markdown(f"#### Panel consolidado · {año_sel}")
        cols_show = ["departamento", "año"] + VARIABLES_ORDEN
        cols_show = [c for c in cols_show if c in df_año.columns]
        st.dataframe(df_año[cols_show], use_container_width=True, height=520)
        st.download_button(
            "⬇️ Descargar CSV del año",
            data=df_año[cols_show].to_csv(index=False).encode("utf-8"),
            file_name=f"observatorio_real_{año_sel}.csv",
            mime="text/csv",
        )

    # ========== NACIONAL ==========
    with tab_nacional:
        st.markdown("### Indicadores macroeconómicos nacionales")
        st.caption(
            "Inflación y TRM: fuentes primarias colombianas. "
            "Tasa de interés real y cuenta corriente: Banco Mundial "
            "(compilación BanRep/FMI; API BanRep no disponible en este entorno)."
        )
        if df_nac_ind.empty:
            st.warning("No se pudieron cargar indicadores nacionales en esta sesión.")
        else:
            años_n = sorted(df_nac_ind["año"].dropna().astype(int).unique(), reverse=True)
            año_n = st.selectbox("Año (nacionales)", options=años_n, index=0, key="año_nac")
            row = df_nac_ind[df_nac_ind["año"] == año_n]
            cols = st.columns(4)
            for i, key in enumerate(
                ["inflacion_anual", "trm_promedio", "tasa_interes_real", "balanza_cuenta_corriente"]
            ):
                meta_n = NATIONAL_META[key]
                with cols[i]:
                    val = (
                        row[key].values[0]
                        if key in row.columns and len(row) and pd.notna(row[key].values[0])
                        else np.nan
                    )
                    st.markdown(
                        f"""<div class="kpi-card"><p class="kpi-title">{meta_n['nombre']}</p>
                        <p class="kpi-value">{meta_n['formato'].format(val) if pd.notna(val) else 'N/D'}</p>
                        <p class="kpi-subtitle kpi-neutral">{meta_n['fuente'][:52]}…</p></div>""",
                        unsafe_allow_html=True,
                    )
            st.markdown("#### Series históricas nacionales")
            for key in ["inflacion_anual", "trm_promedio", "tasa_interes_real", "balanza_cuenta_corriente"]:
                if key not in df_nac_ind.columns:
                    continue
                meta_n = NATIONAL_META[key]
                d = df_nac_ind.dropna(subset=[key])
                if d.empty:
                    continue
                fig = go.Figure(go.Scatter(
                    x=d["año"], y=d[key], mode="lines+markers",
                    line=dict(color="#2563EB", width=2.5),
                    marker=dict(size=6),
                    name=meta_n["nombre"],
                ))
                fig.update_layout(
                    title=meta_n["nombre"], height=300,
                    margin=dict(l=40, r=20, t=45, b=30),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis_title=meta_n["unidad"],
                    xaxis_title="Año",
                    font=dict(family="Inter, sans-serif"),
                )
                fig.update_xaxes(showgrid=True, gridcolor="#E2E8F0")
                fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0")
                st.plotly_chart(fig, use_container_width=True)
            with st.expander("Estado de carga nacional"):
                for k, v in estados_nac.items():
                    st.caption(f"**{k}**: {v}")
            st.dataframe(df_nac_ind, use_container_width=True, height=280)
            st.download_button(
                "⬇️ CSV indicadores nacionales",
                data=df_nac_ind.to_csv(index=False).encode("utf-8"),
                file_name="indicadores_nacionales_colombia.csv",
                mime="text/csv",
            )

    # ========== FUENTES ==========
    with tab_fuentes:
        st.markdown("### Fuentes oficiales utilizadas")
        st.markdown(
            """
| Variable | Archivo / API | Cobertura |
|----------|---------------|-----------|
| PIB | [anex-PIBDep-TotalDep-2025pr.xlsx](https://www.dane.gov.co/files/operaciones/PIB/anex-PIBDep-TotalDep-2025pr.xlsx) | 2005–2025pr, precios corrientes |
| Homicidios | [m8fd-ahd9](https://www.datos.gov.co/d/m8fd-ahd9) | Conteo de víctimas |
| Cobertura media | [sras-4t5p](https://www.datos.gov.co/d/sras-4t5p) + [MEN 2025](https://www.mineducacion.gov.co/1780/articles-350799_recurso_15.xlsm) | ETC departamentales |
| IPM | [Anexo DANE 2025](https://www.dane.gov.co/files/operaciones/PM/anex-PMultidimensional-Departamental-2025.xlsx) | 33 entidades, 2018–2025 |
| Desempleo (TD) | [Anexo GEIH 2025](https://www.dane.gov.co/files/operaciones/GEIH/anex-GEIHDepartamentos-2025.xls) | 23 departamentos |
| Inflación IPC | [Anexo índices DANE](https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc/ipc-informacion-tecnica) | Nacional |
| TRM | [32sa-8pi3](https://www.datos.gov.co/d/32sa-8pi3) | Nacional, promedio anual |
| Tasa interés real | Banco Mundial FR.INR.RINR | Nacional |
| Cuenta corriente | Banco Mundial BN.CAB.XOKA.CD | Nacional |
| Inversión DNP | — | Sin serie anual departamental estandarizada aquí |
            """
        )
        st.markdown("#### Estado de esta sesión")
        for k, v in {**estados_carga, **estados_nac}.items():
            st.write(f"- **{k}**: {v}")

    st.markdown(
        """<div class="footer">
        Observatorio territorial Colombia · Solo cifras oficiales · Sin datos sintéticos ·
        Estándar de transparencia tipo think tank
        </div>""",
        unsafe_allow_html=True,
    )



if __name__ == "__main__":
    main()
