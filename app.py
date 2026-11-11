# -*- coding: utf-8 -*-
"""
======================================================================
 OBSERVATORIO DE ANALÍTICA ECONÓMICA Y SOCIAL POR DEPARTAMENTOS
 Colombia · Datos abiertos oficiales (DANE · MEN · MinDefensa · datos.gov.co)
======================================================================

Ejecutar localmente:
    pip install -r requirements.txt
    streamlit run app.py

Principios de diseño
--------------------
1. SOLO DATOS REALES: todos los indicadores se descargan en vivo desde APIs
   oficiales (datos.gov.co / Socrata y API del Banco Mundial). No se generan
   datos sintéticos. Si una fuente no responde, el módulo lo informa y el
   resto de la aplicación sigue funcionando.
2. ROBUSTEZ: cada pestaña se ejecuta dentro de un "contenedor seguro" que
   captura excepciones; el mapa tiene tres niveles de respaldo
   (coroplético → burbujas geográficas → barras ordenadas).
3. DIDÁCTICA: cada indicador tiene ficha (qué mide, por qué importa para la
   política pública y fuente oficial) disponible en tooltips y expanders.

Las únicas tablas fijas del código son de REFERENCIA (códigos DIVIPOLA,
regiones naturales y coordenadas de capitales), no datos estadísticos.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from typing import Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ======================================================================
# 0. CONFIGURACIÓN GENERAL DE LA PÁGINA
# ======================================================================
st.set_page_config(
    page_title="Observatorio Departamental de Colombia",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta ejecutiva institucional
SLATE = "#0F172A"      # Slate oscuro: barra lateral y contrastes
AZUL = "#2563EB"       # Azul primario institucional
TEAL = "#0D9488"       # Acento
FONDO = "#F8FAFC"      # Fondo limpio
GRIS = "#64748B"
VERDE = "#16A34A"
AMBAR = "#D97706"
ROJO = "#DC2626"

HTTP_TIMEOUT = 30
CACHE_TTL = 60 * 60 * 6   # 6 horas
ANIO_ACTUAL = dt.date.today().year

# ======================================================================
# 1. TABLAS DE REFERENCIA (NO SON DATOS ESTADÍSTICOS)
# ======================================================================
# Códigos DIVIPOLA (DANE) de los 32 departamentos + Bogotá D.C.
DEPARTAMENTOS: dict[str, str] = {
    "05": "Antioquia", "08": "Atlántico", "11": "Bogotá D.C.", "13": "Bolívar",
    "15": "Boyacá", "17": "Caldas", "18": "Caquetá", "19": "Cauca",
    "20": "Cesar", "23": "Córdoba", "25": "Cundinamarca", "27": "Chocó",
    "41": "Huila", "44": "La Guajira", "47": "Magdalena", "50": "Meta",
    "52": "Nariño", "54": "Norte de Santander", "63": "Quindío",
    "66": "Risaralda", "68": "Santander", "70": "Sucre", "73": "Tolima",
    "76": "Valle del Cauca", "81": "Arauca", "85": "Casanare",
    "86": "Putumayo", "88": "San Andrés y Providencia", "91": "Amazonas",
    "94": "Guainía", "95": "Guaviare", "97": "Vaupés", "99": "Vichada",
}

# Regiones naturales (para el benchmarking regional)
REGIONES: dict[str, list[str]] = {
    "Caribe": ["08", "13", "20", "23", "44", "47", "70"],
    "Andina": ["05", "11", "15", "17", "25", "41", "54", "63", "66", "68", "73"],
    "Pacífica": ["19", "27", "52", "76"],
    "Orinoquía": ["50", "81", "85", "99"],
    "Amazonía": ["18", "86", "91", "94", "95", "97"],
    "Insular": ["88"],
}
REGION_DE = {cod: reg for reg, cods in REGIONES.items() for cod in cods}

# Coordenadas aproximadas de capitales (respaldo geográfico del mapa)
COORDENADAS: dict[str, tuple[float, float]] = {
    "05": (6.2442, -75.5812), "08": (10.9685, -74.7813), "11": (4.7110, -74.0721),
    "13": (10.3910, -75.4794), "15": (5.5353, -73.3678), "17": (5.0703, -75.5138),
    "18": (1.6144, -75.6062), "19": (2.4448, -76.6147), "20": (10.4631, -73.2532),
    "23": (8.7479, -75.8814), "25": (5.0000, -74.3000), "27": (5.6919, -76.6583),
    "41": (2.9273, -75.2819), "44": (11.5444, -72.9072), "47": (11.2408, -74.1990),
    "50": (4.1420, -73.6266), "52": (1.2136, -77.2811), "54": (7.8939, -72.5078),
    "63": (4.5339, -75.6811), "66": (4.8133, -75.6961), "68": (7.1193, -73.1227),
    "70": (9.3047, -75.3978), "73": (4.4389, -75.2322), "76": (3.4516, -76.5320),
    "81": (7.0847, -70.7591), "85": (5.3378, -72.3959), "86": (1.1520, -76.6463),
    "88": (12.5847, -81.7006), "91": (-4.2153, -69.9406), "94": (3.8653, -67.9239),
    "95": (2.5729, -72.6459), "97": (1.2537, -70.2345), "99": (6.1890, -67.4859),
}

# ======================================================================
# 2. FUENTES OFICIALES Y METADATOS DE VARIABLES
# ======================================================================
SOCRATA_BASE = "https://www.datos.gov.co/resource/{id}.json"

FUENTES = {
    "MEN": {
        "nombre": "MEN · Estadísticas en educación preescolar, básica y media por departamento",
        "entidad": "Ministerio de Educación Nacional (SIMAT) – publicado en datos.gov.co",
        "dataset": "ji8i-4anb",
        "url": "https://www.datos.gov.co/d/ji8i-4anb",
    },
    "MINDEFENSA": {
        "nombre": "MinDefensa · Homicidio intencional (Policía Nacional – SIEDCO)",
        "entidad": "Ministerio de Defensa Nacional – publicado en datos.gov.co",
        "dataset": "m8fd-ahd9",
        "url": "https://www.datos.gov.co/d/m8fd-ahd9",
    },
    "BM": {
        "nombre": "Banco Mundial · World Development Indicators (Colombia)",
        "entidad": "Banco Mundial (series nacionales construidas con DANE y BanRep)",
        "dataset": "WDI",
        "url": "https://data.worldbank.org/country/colombia",
    },
    "DANE": {
        "nombre": "DANE · DIVIPOLA (codificación territorial) y estadísticas oficiales",
        "entidad": "Departamento Administrativo Nacional de Estadística",
        "dataset": "DIVIPOLA",
        "url": "https://www.dane.gov.co",
    },
}

# Diccionario didáctico de indicadores departamentales.
#   mejor: "alto" | "bajo" | None (None = sin semaforización)
METADATA_VARIABLES: dict[str, dict] = {
    "cobertura_neta": {
        "nombre": "Cobertura neta en educación", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "alto", "decimales": 1,
        "significado": "Porcentaje de niños y jóvenes en edad escolar teórica (5–16 años) que están "
                       "matriculados en el nivel que corresponde a su edad.",
        "impacto": "Mide el acceso efectivo y oportuno al sistema educativo. Brechas de cobertura "
                   "anticipan menor capital humano, menor productividad y transmisión "
                   "intergeneracional de la pobreza; orienta la inversión en cupos, transporte y "
                   "alimentación escolar.",
    },
    "cobertura_bruta": {
        "nombre": "Cobertura bruta en educación", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": None, "decimales": 1,
        "significado": "Matrícula total (sin importar la edad) frente a la población en edad escolar. "
                       "Puede superar 100% por extraedad o repitencia.",
        "impacto": "Indica la capacidad instalada del sistema. Una brecha grande entre cobertura bruta "
                   "y neta señala extraedad y rezago, no necesariamente mayor acceso.",
    },
    "cobertura_neta_media": {
        "nombre": "Cobertura neta en educación media", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "alto", "decimales": 1,
        "significado": "Porcentaje de jóvenes de 15–16 años matriculados en grados 10.º y 11.º.",
        "impacto": "Es el cuello de botella del sistema: define el acceso a educación superior y al "
                   "empleo formal. Clave para programas de permanencia y doble titulación.",
    },
    "tasa_matriculacion_5_16": {
        "nombre": "Tasa de matriculación 5–16 años", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "alto", "decimales": 1,
        "significado": "Porcentaje de la población de 5 a 16 años que está matriculada en cualquier nivel.",
        "impacto": "Aproxima cuántos niños y adolescentes están fuera del sistema escolar; insumo directo "
                   "para estrategias de búsqueda activa y protección de la niñez.",
    },
    "desercion": {
        "nombre": "Tasa de deserción intra-anual", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "bajo", "decimales": 2,
        "significado": "Porcentaje de estudiantes que abandonan el sistema durante el año lectivo.",
        "impacto": "Alerta temprana de vulnerabilidad (trabajo infantil, violencia, pobreza, migración). "
                   "Reducirla es una de las metas más costo-efectivas de la política educativa.",
    },
    "aprobacion": {
        "nombre": "Tasa de aprobación", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "alto", "decimales": 1,
        "significado": "Porcentaje de estudiantes que aprueban el año escolar.",
        "impacto": "Refleja eficiencia interna del sistema; tasas bajas elevan el costo por egresado.",
    },
    "reprobacion": {
        "nombre": "Tasa de reprobación", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "bajo", "decimales": 2,
        "significado": "Porcentaje de estudiantes que no aprueban el año escolar.",
        "impacto": "Asociada con extraedad y posterior deserción; orienta programas de nivelación.",
    },
    "repitencia": {
        "nombre": "Tasa de repitencia", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "bajo", "decimales": 2,
        "significado": "Porcentaje de estudiantes que cursan nuevamente el mismo grado.",
        "impacto": "Implica costos fiscales adicionales y mayor riesgo de abandono escolar.",
    },
    "sedes_conectadas_a_internet": {
        "nombre": "Sedes educativas conectadas a internet", "unidad": "%", "fuente": "MEN",
        "categoria": "Educación", "mejor": "alto", "decimales": 1,
        "significado": "Porcentaje de sedes educativas con conexión a internet.",
        "impacto": "Mide la brecha digital territorial; condiciona la calidad educativa, la "
                   "conectividad rural y la capacidad de respuesta ante emergencias.",
    },
    "tamano_promedio_grupo": {
        "nombre": "Tamaño promedio de grupo", "unidad": "estudiantes", "fuente": "MEN",
        "categoria": "Educación", "mejor": None, "decimales": 1,
        "significado": "Número promedio de estudiantes por grupo (aula).",
        "impacto": "Aproxima la carga docente e infraestructura: grupos muy grandes reducen la atención "
                   "personalizada; muy pequeños pueden indicar dispersión rural.",
    },
    "poblacion_5_16": {
        "nombre": "Población en edad escolar (5–16)", "unidad": "personas", "fuente": "MEN",
        "categoria": "Demografía", "mejor": None, "decimales": 0,
        "significado": "Población de 5 a 16 años usada como denominador de los indicadores educativos "
                       "(basada en proyecciones de población del DANE).",
        "impacto": "Dimensiona la demanda potencial de cupos, docentes y transferencias del Sistema "
                   "General de Participaciones (SGP).",
    },
    "homicidios": {
        "nombre": "Homicidios intencionales (víctimas)", "unidad": "víctimas", "fuente": "MINDEFENSA",
        "categoria": "Seguridad", "mejor": "bajo", "decimales": 0,
        "significado": "Número de víctimas de homicidio intencional o con dolo registradas en el año "
                       "(conteo absoluto, no tasa).",
        "impacto": "Indicador universal de violencia (ODS 16.1.1). Orienta la asignación de pie de fuerza, "
                   "programas de convivencia y prevención. Al ser un conteo, depende del tamaño "
                   "poblacional del departamento: compare con prudencia.",
    },
}

# Indicadores nacionales del Banco Mundial (API pública)
INDICADORES_BM: dict[str, dict] = {
    "NY.GDP.MKTP.KD.ZG": {"nombre": "Crecimiento del PIB real", "unidad": "% anual",
                          "desc": "Variación anual del Producto Interno Bruto a precios constantes."},
    "FP.CPI.TOTL.ZG": {"nombre": "Inflación (IPC)", "unidad": "% anual",
                       "desc": "Variación anual del índice de precios al consumidor."},
    "SL.UEM.TOTL.ZS": {"nombre": "Desempleo", "unidad": "% fuerza laboral",
                       "desc": "Desempleo total (estimación modelada OIT)."},
    "NY.GDP.PCAP.CD": {"nombre": "PIB per cápita", "unidad": "US$ corrientes",
                       "desc": "PIB dividido por la población a mitad de año."},
    "SI.POV.GINI": {"nombre": "Coeficiente de Gini", "unidad": "índice 0–100",
                    "desc": "Desigualdad del ingreso: 0 = igualdad perfecta; 100 = máxima desigualdad."},
    "SI.POV.NAHC": {"nombre": "Pobreza monetaria (línea nacional)", "unidad": "% población",
                    "desc": "Población bajo la línea de pobreza nacional (DANE)."},
}

# ======================================================================
# 3. HOJA DE ESTILOS (UI/UX "THINK TANK")
# ======================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---------- Base clara y legible (se fuerza aunque el usuario use tema oscuro) ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
[data-testid="stHeader"] { background: rgba(248,250,252,0.85) !important; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    color: #0F172A;
}
.stApp [data-testid="stMarkdownContainer"] p { line-height: 1.6; }

/* ---------- Barra lateral slate ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #111C33 100%) !important;
    border-right: 1px solid #1E293B;
}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] * ,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
    color: #E2E8F0 !important;
}

/* ---------- CONTRASTE DE CONTROLES (selectbox, multiselect, inputs) ---------- */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="base-input"] {
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 10px !important;
}
[data-baseweb="select"] *, [data-baseweb="input"] input, [data-baseweb="base-input"] input {
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
    font-weight: 500;
}
[data-baseweb="select"] svg { fill: #334155 !important; }
[data-baseweb="tag"] { background-color: #DBEAFE !important; }
[data-baseweb="tag"] * { color: #1E3A8A !important; }
/* Menú desplegable (se renderiza fuera de la barra lateral) */
[data-baseweb="popover"] ul, [data-baseweb="menu"], ul[role="listbox"] {
    background-color: #FFFFFF !important;
}
[data-baseweb="popover"] li, ul[role="listbox"] li, [role="option"] {
    color: #0F172A !important; background-color: #FFFFFF !important;
}
[role="option"]:hover, [aria-selected="true"][role="option"] { background-color: #EFF6FF !important; }

/* Etiquetas de widgets en el área principal */
.main [data-testid="stWidgetLabel"] p, [data-testid="stMain"] [data-testid="stWidgetLabel"] p {
    color: #0F172A !important; font-weight: 600 !important; font-size: 0.92rem;
}

/* ---------- CONTRASTE DE SLIDERS ---------- */
[data-testid="stSlider"] [role="slider"] {
    background-color: #2563EB !important; border: 3px solid #FFFFFF !important;
    box-shadow: 0 0 0 2px #2563EB !important;
}
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {
    color: #FFFFFF !important; background: #2563EB !important; padding: 1px 8px;
    border-radius: 6px; font-weight: 700 !important;
}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
    color: #475569 !important; font-weight: 600;
}
section[data-testid="stSidebar"] [data-testid="stSliderTickBarMin"],
section[data-testid="stSidebar"] [data-testid="stSliderTickBarMax"] { color: #CBD5E1 !important; }

/* Contenedores con fondo blanco: siempre texto oscuro */
[data-testid="stExpander"] {
    background: #FFFFFF !important; border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important; box-shadow: 0 1px 3px rgba(15,23,42,0.06);
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: #0F172A !important; font-weight: 600; }
section[data-testid="stSidebar"] [data-testid="stExpander"] * { color: #0F172A !important; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
[data-testid="stToggle"] label p { color: inherit; }

/* ---------- Pestañas ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #FFFFFF; padding: 6px; border-radius: 14px;
    border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(15,23,42,0.05); flex-wrap: wrap;
}
.stTabs [data-baseweb="tab"] {
    height: 42px; padding: 0 14px; border-radius: 10px; background: transparent;
    color: #334155 !important; font-weight: 600;
}
.stTabs [data-baseweb="tab"] p { color: #334155 !important; font-weight: 600; font-size: 0.9rem; }
.stTabs [aria-selected="true"] { background: #0F172A !important; }
.stTabs [aria-selected="true"] p { color: #FFFFFF !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* ---------- Banner institucional ---------- */
.hero {
    position: relative; overflow: hidden;
    background: radial-gradient(circle at 85% 20%, rgba(13,148,136,0.45) 0%, transparent 45%),
                linear-gradient(120deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%);
    border-radius: 18px; padding: 38px 40px; margin-bottom: 22px;
    box-shadow: 0 18px 40px -18px rgba(15,23,42,0.55);
}
.hero h1 { color: #FFFFFF !important; font-size: 2.15rem; font-weight: 800; margin: 6px 0 8px 0; letter-spacing: -0.02em; }
.hero p { color: #DBEAFE !important; font-size: 1.05rem; max-width: 880px; margin: 0; }
.hero .kicker { color: #5EEAD4 !important; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }
.hero-stats { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 24px; }
.hero-stat { background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18);
             border-radius: 12px; padding: 12px 18px; min-width: 150px; backdrop-filter: blur(4px); }
.hero-stat .v { color: #FFFFFF !important; font-size: 1.55rem; font-weight: 800; display: block; }
.hero-stat .l { color: #BFDBFE !important; font-size: 0.78rem; font-weight: 500; }

/* ---------- Tarjetas informativas ---------- */
.info-card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 22px;
    height: 100%; box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 8px 24px -16px rgba(15,23,42,0.25);
    transition: transform .18s ease, box-shadow .18s ease;
}
.info-card:hover { transform: translateY(-3px); box-shadow: 0 14px 30px -14px rgba(37,99,235,0.35); }
.info-card .ic { font-size: 1.6rem; }
.info-card h4 { margin: 8px 0 6px 0; font-size: 1.05rem; font-weight: 700; color: #0F172A !important; }
.info-card p, .info-card li { color: #475569 !important; font-size: 0.9rem; }
.module-chip { display: inline-block; background: #EFF6FF; color: #1D4ED8 !important; border-radius: 999px;
               padding: 3px 10px; margin: 3px 4px 3px 0; font-size: 0.78rem; font-weight: 600; }

/* ---------- Tarjetas KPI ---------- */
.kpi-card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px 20px 16px 20px;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 10px 26px -18px rgba(15,23,42,0.30);
    border-top: 4px solid var(--accent, #2563EB); height: 100%; position: relative;
    transition: transform .18s ease;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-card .cat { font-size: 0.70rem; text-transform: uppercase; letter-spacing: 0.10em; color: #64748B !important; font-weight: 700; }
.kpi-card .name { font-size: 0.92rem; font-weight: 600; color: #0F172A !important; margin: 4px 0 8px 0; min-height: 2.4em; }
.kpi-card .value { font-size: 1.85rem; font-weight: 800; color: #0F172A !important; letter-spacing: -0.02em; }
.kpi-card .unit { font-size: 0.85rem; color: #64748B !important; font-weight: 500; margin-left: 4px; }
.kpi-card .meta { font-size: 0.76rem; color: #64748B !important; margin-top: 6px; }
.kpi-card .delta { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; padding: 4px 10px;
                   border-radius: 999px; font-size: 0.80rem; font-weight: 700; }
.delta.good { background: #DCFCE7; color: #166534 !important; }
.delta.mid  { background: #FEF3C7; color: #92400E !important; }
.delta.bad  { background: #FEE2E2; color: #991B1B !important; }
.delta.neu  { background: #F1F5F9; color: #334155 !important; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; position: absolute; top: 16px; right: 16px; }

/* ---------- Insignias de fuente ---------- */
.source-badge {
    display: inline-flex; align-items: center; gap: 6px; background: #F0FDFA; color: #115E59 !important;
    border: 1px solid #99F6E4; border-radius: 999px; padding: 3px 11px; font-size: 0.74rem;
    font-weight: 700; letter-spacing: 0.02em; margin: 2px 4px 2px 0; text-decoration: none !important;
}
.source-badge.off { background: #FEF2F2; color: #991B1B !important; border-color: #FECACA; }
.source-badge.blue { background: #EFF6FF; color: #1D4ED8 !important; border-color: #BFDBFE; }

/* ---------- Títulos de sección ---------- */
.section-title { font-size: 1.35rem; font-weight: 800; color: #0F172A !important; margin: 6px 0 2px 0; letter-spacing: -0.01em; }
.section-sub { color: #64748B !important; font-size: 0.92rem; margin-bottom: 14px; }
.callout { background: #FFFFFF; border-left: 4px solid #0D9488; border-radius: 10px; padding: 14px 18px;
           box-shadow: 0 1px 3px rgba(15,23,42,0.06); margin: 8px 0 16px 0; }
.callout p { margin: 0; color: #334155 !important; }
.side-brand { padding: 6px 2px 14px 2px; border-bottom: 1px solid #1E293B; margin-bottom: 14px; }
.side-brand .t { color: #FFFFFF !important; font-weight: 800; font-size: 1.05rem; line-height: 1.25; }
.side-brand .s { color: #5EEAD4 !important; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }
.footer { text-align: center; color: #94A3B8 !important; font-size: 0.78rem; margin-top: 30px; }

/* Métricas nativas */
[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px;
                           box-shadow: 0 1px 3px rgba(15,23,42,0.06); }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] * { color: #0F172A !important; }
/* Botones */
.stDownloadButton button, .stButton button {
    background: #2563EB !important; color: #FFFFFF !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important; padding: 0.55rem 1.1rem !important;
}
.stDownloadButton button *, .stButton button * { color: #FFFFFF !important; }
.stDownloadButton button:hover, .stButton button:hover { background: #1D4ED8 !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ======================================================================
# 4. CAPA DE DATOS (DESCARGAS REALES, CACHÉ Y NORMALIZACIÓN)
# ======================================================================
def _socrata(dataset_id: str, params: dict) -> pd.DataFrame:
    """Consulta la API Socrata de datos.gov.co y devuelve un DataFrame."""
    url = SOCRATA_BASE.format(id=dataset_id)
    resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT,
                        headers={"Accept": "application/json"})
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def _norm_cod(x) -> str | None:
    """Normaliza un código de departamento DIVIPOLA a 2 dígitos ('5' -> '05')."""
    try:
        s = str(x).strip().split(".")[0]
        if not s.isdigit():
            return None
        s = s.zfill(2)[-2:] if len(s) <= 2 else s[:2]
        return s if s in DEPARTAMENTOS else None
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_educacion() -> tuple[pd.DataFrame, str | None]:
    """MEN – indicadores de educación preescolar, básica y media por departamento."""
    try:
        df = _socrata(FUENTES["MEN"]["dataset"], {"$limit": 50000})
        if df.empty:
            return pd.DataFrame(), "La fuente respondió sin registros."
        # Tolerancia a cambios de nombre de columnas en la fuente
        col_anio = next((c for c in ["ano", "a_o", "anio", "año"] if c in df.columns), None)
        col_cod = next((c for c in ["c_digo_departamento", "codigo_departamento", "cod_depto"]
                        if c in df.columns), None)
        if not col_anio or not col_cod:
            return pd.DataFrame(), f"Estructura inesperada: {list(df.columns)[:8]}"
        df["cod_dpto"] = df[col_cod].map(_norm_cod)
        df["anio"] = pd.to_numeric(df[col_anio], errors="coerce")
        df = df.dropna(subset=["cod_dpto", "anio"])
        variables = [v for v, m in METADATA_VARIABLES.items() if m["fuente"] == "MEN" and v in df.columns]
        largo = df.melt(id_vars=["cod_dpto", "anio"], value_vars=variables,
                        var_name="variable", value_name="valor")
        largo["valor"] = pd.to_numeric(largo["valor"].astype(str).str.replace(",", "."), errors="coerce")
        largo = largo.dropna(subset=["valor"])
        largo = largo.groupby(["cod_dpto", "anio", "variable"], as_index=False)["valor"].mean()
        largo["anio"] = largo["anio"].astype(int)
        return largo, None
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_homicidios() -> tuple[pd.DataFrame, str | None]:
    """MinDefensa – víctimas de homicidio intencional, agregadas por año y departamento (SoQL)."""
    try:
        params = {
            "$select": "date_extract_y(fecha_hecho) as anio, cod_depto, sum(cantidad) as total",
            "$group": "anio, cod_depto",
            "$limit": 50000,
        }
        df = _socrata(FUENTES["MINDEFENSA"]["dataset"], params)
        if df.empty:
            return pd.DataFrame(), "La fuente respondió sin registros."
        df["cod_dpto"] = df["cod_depto"].map(_norm_cod)
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
        df["valor"] = pd.to_numeric(df["total"], errors="coerce")
        df = df.dropna(subset=["cod_dpto", "anio", "valor"])
        df = df.groupby(["cod_dpto", "anio"], as_index=False)["valor"].sum()
        df["anio"] = df["anio"].astype(int)
        df["variable"] = "homicidios"
        return df[["cod_dpto", "anio", "variable", "valor"]], None
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_banco_mundial() -> tuple[pd.DataFrame, str | None]:
    """Banco Mundial – series macro nacionales de Colombia."""
    filas, errores = [], []
    for codigo in INDICADORES_BM:
        try:
            url = f"https://api.worldbank.org/v2/country/COL/indicator/{codigo}"
            r = requests.get(url, params={"format": "json", "per_page": 200, "date": f"1995:{ANIO_ACTUAL}"},
                             timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
                errores.append(codigo)
                continue
            for obs in payload[1]:
                if obs.get("value") is not None:
                    filas.append({"codigo": codigo, "anio": int(obs["date"]), "valor": float(obs["value"])})
        except Exception:  # noqa: BLE001
            errores.append(codigo)
    df = pd.DataFrame(filas)
    err = None if not errores else f"Sin respuesta para: {', '.join(errores)}"
    if df.empty and err is None:
        err = "La API no devolvió observaciones."
    return df, err


# Repositorios públicos de límites departamentales (se prueban en orden)
GEOJSON_URLS = [
    "https://gist.githubusercontent.com/john-guerra/43c7656821069d00dcbc/raw/"
    "be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/Colombia.geo.json",
]


def _norm_txt(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.upper() if ch.isalpha())


def _cod_desde_nombre(nombre: str) -> str | None:
    """Empata nombres de departamento escritos de formas distintas con su código DIVIPOLA."""
    n = _norm_txt(nombre)
    if not n:
        return None
    alias = {"BOGOTA": "11", "SANTAFEDEBOGOTA": "11", "SANANDRES": "88", "ARCHIPIELAGO": "88",
             "VALLE": "76", "GUAJIRA": "44", "NORTEDESANTANDER": "54"}
    for k, v in alias.items():
        if k in n:
            return v
    for cod, nom in DEPARTAMENTOS.items():
        if _norm_txt(nom) == n:
            return cod
    return None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_geojson() -> tuple[dict | None, str | None]:
    """
    Descarga y PREPARA el GeoJSON departamental de forma defensiva:
    detecta automáticamente qué propiedad contiene el código o el nombre,
    y escribe una llave uniforme `properties.cod_dpto` en cada polígono.
    """
    ultimo_error = "Sin URL disponible"
    for url in GEOJSON_URLS:
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            gj = r.json()
            feats = gj.get("features", [])
            if not feats:
                ultimo_error = "GeoJSON sin polígonos"
                continue
            asignados = 0
            for f in feats:
                props = f.setdefault("properties", {}) or {}
                cod = None
                for k in ["DPTO", "DPTO_CCDGO", "COD_DPTO", "cod_dpto", "DPTO_CODIGO", "id"]:
                    if k in props:
                        cod = _norm_cod(props[k])
                        if cod:
                            break
                if not cod:
                    for k in ["NOMBRE_DPT", "DPTO_CNMBR", "NAME_1", "name", "departamento", "DPTO_NOMBRE"]:
                        if k in props:
                            cod = _cod_desde_nombre(props[k])
                            if cod:
                                break
                if not cod and f.get("id") is not None:
                    cod = _norm_cod(f["id"])
                if cod:
                    props["cod_dpto"] = cod
                    asignados += 1
            if asignados >= 20:   # al menos 20 de 33 departamentos empatados
                return gj, None
            ultimo_error = f"Solo {asignados} polígonos coincidieron con códigos DIVIPOLA"
        except Exception as e:  # noqa: BLE001
            ultimo_error = f"{type(e).__name__}: {e}"
    return None, ultimo_error


def construir_panel(incluir_parcial: bool) -> tuple[pd.DataFrame, dict]:
    """Une todas las fuentes en un panel largo: cod_dpto | anio | variable | valor."""
    estado = {}
    edu, e1 = cargar_educacion()
    hom, e2 = cargar_homicidios()
    estado["MEN"] = e1
    estado["MINDEFENSA"] = e2
    if not hom.empty and not incluir_parcial:
        hom = hom[hom["anio"] < ANIO_ACTUAL]
    partes = [p for p in (edu, hom) if not p.empty]
    if not partes:
        return pd.DataFrame(columns=["cod_dpto", "anio", "variable", "valor",
                                     "departamento", "region"]), estado
    panel = pd.concat(partes, ignore_index=True)
    panel["departamento"] = panel["cod_dpto"].map(DEPARTAMENTOS)
    panel["region"] = panel["cod_dpto"].map(REGION_DE)
    return panel, estado


# ======================================================================
# 5. UTILIDADES DE FORMATO, ESTADÍSTICA Y COMPONENTES VISUALES
# ======================================================================
def fmt(v: float | None, dec: int = 1) -> str:
    """Formato numérico colombiano: 1.234.567,8"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def nombre_var(v: str) -> str:
    return METADATA_VARIABLES.get(v, {}).get("nombre", v)


def ayuda_var(v: str) -> str:
    m = METADATA_VARIABLES.get(v, {})
    return (f"{m.get('significado', '')}\n\nImpacto en política pública: {m.get('impacto', '')}\n\n"
            f"Fuente: {FUENTES.get(m.get('fuente', ''), {}).get('entidad', '')}")


def badge(texto: str, clase: str = "", url: str | None = None) -> str:
    if url:
        return f'<a class="source-badge {clase}" href="{url}" target="_blank">🔗 {texto}</a>'
    return f'<span class="source-badge {clase}">● {texto}</span>'


def badge_fuente(v: str) -> str:
    f = FUENTES.get(METADATA_VARIABLES[v]["fuente"], {})
    return badge(f"Fuente: {f.get('entidad', '').split(' – ')[0]} · {f.get('dataset', '')}", url=f.get("url"))


def titulo(texto: str, sub: str = "") -> None:
    st.markdown(f'<div class="section-title">{texto}</div>'
                + (f'<div class="section-sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


def ficha_indicador(v: str, expandido: bool = False) -> None:
    """Ficha didáctica desplegable con metadatos del indicador."""
    m = METADATA_VARIABLES[v]
    f = FUENTES[m["fuente"]]
    with st.expander(f"📘 Ficha técnica: {m['nombre']}", expanded=expandido):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**1. ¿Qué mide?**  \n{m['significado']}")
            st.markdown(f"**Unidad:** {m['unidad']} · **Categoría:** {m['categoria']}")
            sentido = {"alto": "⬆️ Más alto es mejor", "bajo": "⬇️ Más bajo es mejor",
                       None: "↔️ Indicador de contexto (sin juicio de valor)"}[m["mejor"]]
            st.markdown(f"**Lectura:** {sentido}")
        with c2:
            st.markdown(f"**2. ¿Por qué importa para la política pública?**  \n{m['impacto']}")
            st.markdown(f"**3. Fuente oficial:** {f['entidad']}")
            st.markdown(badge(f"datos.gov.co · {f['dataset']}", url=f["url"]), unsafe_allow_html=True)


def valor_ref(panel: pd.DataFrame, var: str, anio_ref: int) -> tuple[pd.DataFrame, int | None]:
    """
    Devuelve los valores por departamento del último año disponible <= anio_ref
    para la variable (año efectivo). Así nunca hay vacíos por desfase de fuentes.
    """
    d = panel[panel["variable"] == var]
    if d.empty:
        return d, None
    anios = sorted(d["anio"].unique())
    validos = [a for a in anios if a <= anio_ref]
    anio_ef = validos[-1] if validos else anios[0]
    return d[d["anio"] == anio_ef].copy(), int(anio_ef)


def semaforo(valor: float, ref: float, mejor: str | None) -> tuple[str, str, float | None]:
    """Clasifica el desempeño frente a una referencia. Retorna (clase CSS, color, % diferencia)."""
    if ref is None or np.isnan(ref) or ref == 0 or valor is None or np.isnan(valor):
        return "neu", GRIS, None
    diff = (valor - ref) / abs(ref) * 100
    if mejor is None:
        return "neu", GRIS, diff
    favorable = diff > 0 if mejor == "alto" else diff < 0
    if abs(diff) <= 5:
        return "mid", AMBAR, diff
    return ("good", VERDE, diff) if favorable else ("bad", ROJO, diff)


def kpi_card_html(v: str, valor: float, anio: int, ref: float | None, etiqueta_ref: str) -> str:
    m = METADATA_VARIABLES[v]
    clase, color, diff = semaforo(valor, ref, m["mejor"])
    if diff is None:
        delta_txt = "Sin referencia comparable"
    else:
        flecha = "▲" if diff > 0 else ("▼" if diff < 0 else "■")
        delta_txt = f"{flecha} {fmt(abs(diff), 1)}% vs {etiqueta_ref}"
    unidad = "%" if m["unidad"] == "%" else m["unidad"]
    tooltip = m["significado"].replace('"', "'")
    return f"""
    <div class="kpi-card" style="--accent:{color}" title="{tooltip}">
        <span class="dot" style="background:{color}"></span>
        <div class="cat">{m['categoria']}</div>
        <div class="name">{m['nombre']}</div>
        <div><span class="value">{fmt(valor, m['decimales'])}</span><span class="unit">{unidad}</span></div>
        <div class="delta {clase}">{delta_txt}</div>
        <div class="meta">Año {anio} · Ref. {etiqueta_ref}: {fmt(ref, m['decimales'])}</div>
    </div>"""


def ols(x: np.ndarray, y: np.ndarray) -> dict | None:
    """Regresión lineal simple por MCO: y = a + b·x. Devuelve coeficientes y R²."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 3 or np.ptp(x) == 0:
        return None
    b, a = np.polyfit(x, y, 1)
    yhat = a + b * x
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return {"a": a, "b": b, "r2": r2, "n": len(x), "r": float(np.corrcoef(x, y)[0, 1])}


def estilo_fig(fig: go.Figure, alto: int = 460) -> go.Figure:
    """Plantilla visual institucional para todas las figuras."""
    fig.update_layout(
        template="plotly_white", height=alto,
        font=dict(family="Inter, Segoe UI, sans-serif", color=SLATE, size=13),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=60, b=20),
        title_font=dict(size=16, color=SLATE),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#E2E8F0", borderwidth=1,
                    font=dict(color=SLATE)),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color=SLATE, bordercolor=AZUL),
    )
    fig.update_xaxes(gridcolor="#EEF2F7", linecolor="#CBD5E1", tickfont=dict(color="#334155"),
                     title_font=dict(color="#334155"))
    fig.update_yaxes(gridcolor="#EEF2F7", linecolor="#CBD5E1", tickfont=dict(color="#334155"),
                     title_font=dict(color="#334155"))
    return fig


def mostrar(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False, "locale": "es"})


def seguro(funcion: Callable, *args) -> None:
    """Ejecuta un módulo capturando cualquier excepción para no romper la aplicación."""
    try:
        funcion(*args)
    except Exception as e:  # noqa: BLE001
        st.error("⚠️ Este módulo encontró un problema inesperado y fue aislado para no afectar el resto "
                 f"del observatorio.\n\nDetalle técnico: `{type(e).__name__}: {e}`")


def sin_datos() -> None:
    st.warning("No fue posible obtener datos de las fuentes oficiales en este momento. "
               "Revise la pestaña **📚 Fuentes Oficiales** para ver el estado de cada conexión "
               "y recargue la página en unos minutos.")


# ======================================================================
# 6. CARGA DE DATOS + ESTADO DE SESIÓN SINCRONIZADO
# ======================================================================
if "incluir_parcial" not in st.session_state:
    st.session_state["incluir_parcial"] = False

with st.spinner("Conectando con datos.gov.co (MEN · MinDefensa) …"):
    PANEL, ESTADO = construir_panel(st.session_state["incluir_parcial"])

VARS_DISPONIBLES = [v for v in METADATA_VARIABLES if v in set(PANEL["variable"].unique())]
if not VARS_DISPONIBLES:
    VARS_DISPONIBLES = list(METADATA_VARIABLES.keys())
ANIOS = sorted(PANEL["anio"].unique().tolist()) if not PANEL.empty else [ANIO_ACTUAL - 1]
ANIO_MIN, ANIO_MAX = int(min(ANIOS)), int(max(ANIOS))
CODIGOS = list(DEPARTAMENTOS.keys())


def _init_estado() -> None:
    """Estado canónico + copias para los widgets de la barra lateral (sb_) y la portada (qc_)."""
    defaults = {"depto": "05", "var": VARS_DISPONIBLES[0], "anio": ANIO_MAX}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    # Validaciones defensivas (p. ej. si cambió el rango de años)
    if st.session_state["var"] not in VARS_DISPONIBLES:
        st.session_state["var"] = VARS_DISPONIBLES[0]
    st.session_state["anio"] = int(min(max(st.session_state["anio"], ANIO_MIN), ANIO_MAX))
    for pref in ("sb_", "qc_"):
        for k in defaults:
            st.session_state[pref + k] = st.session_state[k]


def _sync(origen: str, campo: str) -> None:
    """Callback: propaga un cambio desde un panel de control a todos los demás."""
    valor = st.session_state[f"{origen}_{campo}"]
    st.session_state[campo] = valor
    for pref in ("sb", "qc"):
        st.session_state[f"{pref}_{campo}"] = valor


_init_estado()


def controles(prefijo: str, contenedor) -> None:
    """Dibuja el trío de controles (departamento, indicador, año) con sincronización."""
    with contenedor:
        st.selectbox("🏛️ Departamento", CODIGOS, key=f"{prefijo}_depto",
                     format_func=lambda c: DEPARTAMENTOS[c], on_change=_sync, args=(prefijo, "depto"),
                     help="Territorio de análisis. Las comparaciones se hacen frente al promedio de los "
                          "departamentos con dato y frente a su región natural.")
        st.selectbox("📐 Indicador principal", VARS_DISPONIBLES, key=f"{prefijo}_var",
                     format_func=nombre_var, on_change=_sync, args=(prefijo, "var"),
                     help=ayuda_var(st.session_state["var"]))
        if ANIO_MIN < ANIO_MAX:
            st.slider("📅 Año de referencia", ANIO_MIN, ANIO_MAX, key=f"{prefijo}_anio",
                      on_change=_sync, args=(prefijo, "anio"),
                      help="Si un indicador no tiene dato para el año elegido se usa automáticamente "
                           "el último año disponible anterior (año efectivo).")
        else:
            st.caption(f"📅 Año disponible: {ANIO_MAX}")


# ======================================================================
# 7. BARRA LATERAL
# ======================================================================
with st.sidebar:
    st.markdown('<div class="side-brand"><div class="s">Observatorio Territorial</div>'
                '<div class="t">🇨🇴 Analítica Económica y Social por Departamentos</div></div>',
                unsafe_allow_html=True)
    controles("sb", st.container())
    st.toggle("Incluir año en curso (cifras parciales de homicidio)", key="incluir_parcial",
              help="El registro de MinDefensa se actualiza mes a mes; el año en curso está incompleto "
                   "y no es comparable con años cerrados.")
    st.markdown("---")
    st.markdown("**Estado de las fuentes**")
    for k in ("MEN", "MINDEFENSA"):
        ok = ESTADO.get(k) is None
        st.markdown(badge(f"{k} {'en línea' if ok else 'sin conexión'}", "" if ok else "off"),
                    unsafe_allow_html=True)
    st.caption(f"Actualización: caché de 6 h · Consulta: {dt.datetime.now():%d/%m/%Y %H:%M}")

DEPTO = st.session_state["depto"]
VAR = st.session_state["var"]
ANIO = int(st.session_state["anio"])
NOM_DEPTO = DEPARTAMENTOS[DEPTO]
REGION = REGION_DE[DEPTO]

# ======================================================================
# 8. MÓDULOS (PESTAÑAS)
# ======================================================================
def tab_bienvenida() -> None:
    n_vars = PANEL["variable"].nunique() if not PANEL.empty else 0
    n_dptos = PANEL["cod_dpto"].nunique() if not PANEL.empty else 0
    fuentes_ok = sum(1 for e in ESTADO.values() if e is None)
    st.markdown(f"""
    <div class="hero">
        <div class="kicker">Plataforma de datos abiertos · Colombia</div>
        <h1>Observatorio de Analítica Económica y Social por Departamentos</h1>
        <p>Indicadores oficiales de educación, demografía y seguridad para los 32 departamentos y Bogotá D.C.,
        con benchmarking regional, mapas, series históricas y herramientas econométricas para la toma de
        decisiones de gobernadores, analistas y ciudadanía.</p>
        <div class="hero-stats">
            <div class="hero-stat"><span class="v">{n_dptos}</span><span class="l">territorios con dato</span></div>
            <div class="hero-stat"><span class="v">{n_vars}</span><span class="l">indicadores oficiales</span></div>
            <div class="hero-stat"><span class="v">{ANIO_MIN}–{ANIO_MAX}</span><span class="l">cobertura temporal</span></div>
            <div class="hero-stat"><span class="v">{fuentes_ok}/{len(ESTADO)}</span><span class="l">fuentes en línea</span></div>
        </div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""<div class="info-card"><div class="ic">🧭</div><h4>¿Cómo usar este observatorio?</h4>
        <ol><li>Elija un <b>departamento</b>, un <b>indicador</b> y un <b>año</b> (aquí abajo o en la barra lateral).</li>
        <li>Revise su desempeño en <b>📊 KPIs</b> con semáforo frente al promedio nacional.</li>
        <li>Explore el territorio, la evolución y el ranking en las demás pestañas.</li>
        <li>Descargue la tabla consolidada en CSV para su propio análisis.</li></ol></div>""",
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="info-card"><div class="ic">🏛️</div><h4>¿De dónde provienen los datos?</h4>
        <p>Todo se consulta <b>en vivo</b> desde APIs oficiales, sin datos simulados:</p>
        {badge('MEN · ji8i-4anb', url=FUENTES['MEN']['url'])}
        {badge('MinDefensa · m8fd-ahd9', url=FUENTES['MINDEFENSA']['url'])}
        {badge('Banco Mundial · WDI', 'blue', url=FUENTES['BM']['url'])}
        {badge('DANE · DIVIPOLA', 'blue', url=FUENTES['DANE']['url'])}
        <p style="margin-top:10px">Los códigos territoriales siguen la DIVIPOLA del DANE.</p></div>""",
                    unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="info-card"><div class="ic">🚀</div><h4>Módulos clave</h4>
        <p>Use las pestañas superiores para navegar:</p>
        <span class="module-chip">📊 KPIs & Benchmarking</span><span class="module-chip">🗺️ Mapa Interactivo</span>
        <span class="module-chip">📈 Series + tendencia MCO</span><span class="module-chip">🏆 Rankings y correlaciones</span>
        <span class="module-chip">📋 Tabla + CSV</span><span class="module-chip">🌐 Macro nacional</span>
        <span class="module-chip">📚 Fuentes y glosario</span></div>""", unsafe_allow_html=True)

    st.write("")
    titulo("⚡ Panel de control rápido", "Personalice su experiencia: estos controles están sincronizados "
                                         "con la barra lateral y con todas las pestañas.")
    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    controles("qc", col_ctrl)
    with col_prev:
        if PANEL.empty:
            sin_datos()
            return
        d, anio_ef = valor_ref(PANEL, VAR, ANIO)
        fila = d[d["cod_dpto"] == DEPTO]
        if fila.empty:
            st.info(f"{NOM_DEPTO} no reporta **{nombre_var(VAR)}** para el periodo seleccionado.")
        else:
            prom = d["valor"].mean()
            st.markdown(kpi_card_html(VAR, float(fila["valor"].iloc[0]), anio_ef, prom, "promedio nacional"),
                        unsafe_allow_html=True)
            pos = d.sort_values("valor", ascending=METADATA_VARIABLES[VAR]["mejor"] == "bajo")
            rank = list(pos["cod_dpto"]).index(DEPTO) + 1
            if METADATA_VARIABLES[VAR]["mejor"]:
                st.markdown(f'<div class="callout"><p>📌 <b>{NOM_DEPTO}</b> ocupa el puesto <b>{rank} de {len(pos)}</b> '
                            f'en {nombre_var(VAR).lower()} ({anio_ef}).</p></div>', unsafe_allow_html=True)
        ficha_indicador(VAR)


def tab_kpis() -> None:
    if PANEL.empty:
        sin_datos(); return
    titulo(f"📊 KPIs & Benchmarking · {NOM_DEPTO}",
           f"Región {REGION} · Año de referencia {ANIO}. Semáforo: 🟢 mejor que la referencia por más de 5% · "
           "🟡 dentro de ±5% · 🔴 peor por más de 5% · ⚪ indicador de contexto.")
    ref_tipo = st.radio("Comparar contra:", ["Promedio nacional (departamentos con dato)", f"Promedio región {REGION}"],
                        horizontal=True, key="kpi_ref",
                        help="El promedio es simple (no ponderado por población) entre los departamentos con dato.")
    usar_region = ref_tipo.startswith("Promedio región")
    etiqueta = f"región {REGION}" if usar_region else "promedio nacional"

    categorias = {}
    for v in VARS_DISPONIBLES:
        categorias.setdefault(METADATA_VARIABLES[v]["categoria"], []).append(v)

    resumen = []
    for cat, vars_cat in categorias.items():
        st.markdown(f"#### {cat}")
        cols = st.columns(4)
        i = 0
        for v in vars_cat:
            d, anio_ef = valor_ref(PANEL, v, ANIO)
            fila = d[d["cod_dpto"] == DEPTO]
            if fila.empty:
                continue
            base = d[d["region"] == REGION] if usar_region else d
            ref = base["valor"].mean()
            val = float(fila["valor"].iloc[0])
            with cols[i % 4]:
                st.markdown(kpi_card_html(v, val, anio_ef, ref, etiqueta), unsafe_allow_html=True)
                st.write("")
            i += 1
            clase, _, diff = semaforo(val, ref, METADATA_VARIABLES[v]["mejor"])
            resumen.append({"Indicador": nombre_var(v), "Año": anio_ef, NOM_DEPTO: val,
                            f"Ref. {etiqueta}": ref, "Diferencia %": diff,
                            "Estado": {"good": "🟢 Favorable", "mid": "🟡 Similar", "bad": "🔴 Desfavorable",
                                       "neu": "⚪ Contexto"}[clase]})
        if i == 0:
            st.caption("Sin datos para este departamento en esta categoría.")

    if resumen:
        st.markdown("---")
        titulo("🧾 Balance de desempeño", "Resumen tabular del semáforo para informes y comités técnicos.")
        df_r = pd.DataFrame(resumen)
        n_good = (df_r["Estado"] == "🟢 Favorable").sum()
        n_bad = (df_r["Estado"] == "🔴 Desfavorable").sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Indicadores favorables", int(n_good))
        c2.metric("Indicadores desfavorables", int(n_bad))
        c3.metric("Indicadores evaluados", len(df_r))
        st.dataframe(df_r, hide_index=True, column_config={
            NOM_DEPTO: st.column_config.NumberColumn(format="%.2f"),
            f"Ref. {etiqueta}": st.column_config.NumberColumn(format="%.2f"),
            "Diferencia %": st.column_config.NumberColumn(format="%.1f%%"),
        })

    titulo("📘 Glosario didáctico de los indicadores")
    for v in VARS_DISPONIBLES:
        ficha_indicador(v)


def _mapa_coropletico(d: pd.DataFrame, var: str, gj: dict, anio_ef: int) -> go.Figure:
    m = METADATA_VARIABLES[var]
    escala = "RdYlGn_r" if m["mejor"] == "bajo" else ("RdYlGn" if m["mejor"] == "alto" else "Blues")
    fig = px.choropleth(d, geojson=gj, locations="cod_dpto", featureidkey="properties.cod_dpto",
                        color="valor", hover_name="departamento", color_continuous_scale=escala,
                        hover_data={"cod_dpto": False, "valor": ":,.2f", "region": True},
                        labels={"valor": m["nombre"], "region": "Región"})
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="#FFFFFF")
    sel = d[d["cod_dpto"] == DEPTO]
    if not sel.empty and DEPTO in COORDENADAS:
        lat, lon = COORDENADAS[DEPTO]
        fig.add_trace(go.Scattergeo(lat=[lat], lon=[lon], mode="markers+text", text=[f"📍 {NOM_DEPTO}"],
                                    textposition="top center", marker=dict(size=11, color=SLATE,
                                    line=dict(color="#FFFFFF", width=2)),
                                    textfont=dict(color=SLATE, size=12), showlegend=False, hoverinfo="skip"))
    fig.update_layout(title=f"{m['nombre']} · {anio_ef}",
                      coloraxis_colorbar=dict(title=m["unidad"], tickfont=dict(color=SLATE)))
    return estilo_fig(fig, 640)


def _mapa_burbujas(d: pd.DataFrame, var: str, anio_ef: int) -> go.Figure:
    m = METADATA_VARIABLES[var]
    d = d.copy()
    d["lat"] = d["cod_dpto"].map(lambda c: COORDENADAS[c][0])
    d["lon"] = d["cod_dpto"].map(lambda c: COORDENADAS[c][1])
    vmin, vmax = d["valor"].min(), d["valor"].max()
    d["tam"] = 8 + 30 * (d["valor"] - vmin) / (vmax - vmin) if vmax > vmin else 18
    escala = "RdYlGn_r" if m["mejor"] == "bajo" else ("RdYlGn" if m["mejor"] == "alto" else "Blues")
    fig = px.scatter_geo(d, lat="lat", lon="lon", color="valor", size="tam", hover_name="departamento",
                         hover_data={"lat": False, "lon": False, "tam": False, "valor": ":,.2f"},
                         color_continuous_scale=escala, labels={"valor": m["nombre"]})
    fig.update_geos(scope="south america", center=dict(lat=4.5, lon=-73.5), projection_scale=4.2,
                    showcountries=True, countrycolor="#94A3B8", showland=True, landcolor="#F1F5F9",
                    showocean=True, oceancolor="#E0F2FE", bgcolor="#FFFFFF")
    fig.update_layout(title=f"{m['nombre']} · {anio_ef} (vista por capitales departamentales)")
    return estilo_fig(fig, 640)


def _barras_espaciales(d: pd.DataFrame, var: str, anio_ef: int) -> go.Figure:
    m = METADATA_VARIABLES[var]
    d = d.sort_values("valor")
    colores = [TEAL if c == DEPTO else AZUL for c in d["cod_dpto"]]
    fig = go.Figure(go.Bar(x=d["valor"], y=d["departamento"], orientation="h", marker_color=colores,
                           hovertemplate="%{y}: %{x:,.2f}<extra></extra>"))
    fig.update_layout(title=f"{m['nombre']} · {anio_ef} (ordenado por valor)")
    return estilo_fig(fig, max(500, 22 * len(d)))


def tab_mapa() -> None:
    if PANEL.empty:
        sin_datos(); return
    titulo("🗺️ Mapa Interactivo Territorial",
           "Distribución espacial del indicador. Pase el cursor para ver el detalle de cada departamento.")
    c1, c2 = st.columns([2, 1])
    with c1:
        var_mapa = st.selectbox("Indicador a mapear", VARS_DISPONIBLES, index=VARS_DISPONIBLES.index(VAR),
                                format_func=nombre_var, key="map_var", help=ayuda_var(VAR))
    with c2:
        vista = st.radio("Tipo de vista", ["Automática", "Burbujas", "Barras"], horizontal=True, key="map_vista",
                         help="Automática intenta el mapa coroplético y, si falla, cae a burbujas y luego a barras.")
    d, anio_ef = valor_ref(PANEL, var_mapa, ANIO)
    if d.empty:
        st.info("No hay datos para este indicador."); return

    # Sistema defensivo de tres niveles: el mapa NUNCA queda en blanco
    fig, nivel = None, ""
    if vista == "Automática":
        try:
            gj, err = cargar_geojson()
            if gj is not None:
                fig, nivel = _mapa_coropletico(d, var_mapa, gj, anio_ef), "coroplético"
            else:
                st.caption(f"ℹ️ Límites departamentales no disponibles ({err}); se usa vista alternativa.")
        except Exception as e:  # noqa: BLE001
            st.caption(f"ℹ️ El mapa coroplético falló ({type(e).__name__}); se usa vista alternativa.")
            fig = None
    if fig is None and vista in ("Automática", "Burbujas"):
        try:
            fig, nivel = _mapa_burbujas(d, var_mapa, anio_ef), "burbujas"
        except Exception:  # noqa: BLE001
            fig = None
    if fig is None:
        fig, nivel = _barras_espaciales(d, var_mapa, anio_ef), "barras"
    mostrar(fig, key=f"mapa_{nivel}")

    m = METADATA_VARIABLES[var_mapa]
    c1, c2, c3, c4 = st.columns(4)
    mx, mn = d.loc[d["valor"].idxmax()], d.loc[d["valor"].idxmin()]
    c1.metric("Valor máximo", fmt(mx["valor"], m["decimales"]), mx["departamento"], delta_color="off")
    c2.metric("Valor mínimo", fmt(mn["valor"], m["decimales"]), mn["departamento"], delta_color="off")
    c3.metric("Promedio departamental", fmt(d["valor"].mean(), m["decimales"]))
    cv = d["valor"].std() / d["valor"].mean() * 100 if d["valor"].mean() else np.nan
    c4.metric("Dispersión (coef. variación)", f"{fmt(cv, 1)}%",
              help="Desviación estándar / media. Valores altos indican mayor desigualdad territorial.")
    st.markdown(badge_fuente(var_mapa), unsafe_allow_html=True)

    titulo("🧩 Promedios por región natural")
    reg = d.groupby("region", as_index=False)["valor"].mean().sort_values("valor")
    fig_r = px.bar(reg, x="valor", y="region", orientation="h", text_auto=".1f",
                   color="region", color_discrete_sequence=[AZUL, TEAL, "#7C3AED", "#F59E0B", "#0EA5E9", "#EC4899"])
    fig_r.update_layout(showlegend=False, xaxis_title=m["nombre"], yaxis_title="")
    mostrar(estilo_fig(fig_r, 340), key="map_reg")


def tab_series() -> None:
    if PANEL.empty:
        sin_datos(); return
    titulo("📈 Series Históricas y Tendencia",
           "Evolución del departamento frente al promedio nacional, con tendencia lineal estimada por MCO.")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        var_s = st.selectbox("Indicador", VARS_DISPONIBLES, index=VARS_DISPONIBLES.index(VAR),
                             format_func=nombre_var, key="ser_var", help=ayuda_var(VAR))
    with c2:
        otros = st.multiselect("Comparar con otros departamentos", [c for c in CODIGOS if c != DEPTO],
                               format_func=lambda c: DEPARTAMENTOS[c], max_selections=5, key="ser_otros")
    d = PANEL[PANEL["variable"] == var_s]
    if d.empty:
        st.info("Sin datos."); return
    anios = sorted(d["anio"].unique())
    if len(anios) > 1:
        rango = st.slider("Rango de años", int(anios[0]), int(anios[-1]), (int(anios[0]), int(anios[-1])),
                          key=f"ser_rango_{var_s}")
        d = d[(d["anio"] >= rango[0]) & (d["anio"] <= rango[1])]
    m = METADATA_VARIABLES[var_s]
    prom = d.groupby("anio", as_index=False)["valor"].mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prom["anio"], y=prom["valor"], name="Promedio nacional", mode="lines",
                             line=dict(color=GRIS, width=2, dash="dash")))
    paleta = ["#7C3AED", "#F59E0B", "#EC4899", "#0EA5E9", "#84CC16"]
    for i, c in enumerate(otros):
        s = d[d["cod_dpto"] == c].sort_values("anio")
        fig.add_trace(go.Scatter(x=s["anio"], y=s["valor"], name=DEPARTAMENTOS[c], mode="lines+markers",
                                 line=dict(color=paleta[i % 5], width=2)))
    s = d[d["cod_dpto"] == DEPTO].sort_values("anio")
    fig.add_trace(go.Scatter(x=s["anio"], y=s["valor"], name=NOM_DEPTO, mode="lines+markers",
                             line=dict(color=AZUL, width=4), marker=dict(size=8)))
    res = ols(s["anio"].values, s["valor"].values) if not s.empty else None
    if res:
        xs = np.array([s["anio"].min(), s["anio"].max()])
        fig.add_trace(go.Scatter(x=xs, y=res["a"] + res["b"] * xs, name="Tendencia MCO", mode="lines",
                                 line=dict(color=TEAL, width=2, dash="dot")))
    fig.update_layout(title=f"{m['nombre']} · {NOM_DEPTO}", xaxis_title="Año", yaxis_title=m["unidad"],
                      hovermode="x unified", legend=dict(orientation="h", y=-0.18))
    mostrar(estilo_fig(fig, 520), key="ser_fig")

    if len(s) >= 2:
        v0, v1 = s["valor"].iloc[0], s["valor"].iloc[-1]
        n = s["anio"].iloc[-1] - s["anio"].iloc[0]
        tcac = ((v1 / v0) ** (1 / n) - 1) * 100 if v0 > 0 and v1 > 0 and n > 0 else np.nan
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Valor {int(s['anio'].iloc[-1])}", fmt(v1, m["decimales"]),
                  f"{fmt(v1 - v0, m['decimales'])} desde {int(s['anio'].iloc[0])}",
                  delta_color="inverse" if m["mejor"] == "bajo" else ("normal" if m["mejor"] else "off"))
        c2.metric("Tasa de crecimiento anual compuesta", f"{fmt(tcac, 2)}%",
                  help="TCAC = (valor final / valor inicial)^(1/años) − 1")
        if res:
            c3.metric("Pendiente MCO (cambio por año)", fmt(res["b"], 3),
                      help="Coeficiente β de la regresión valor = α + β·año.")
            c4.metric("Ajuste de la tendencia (R²)", fmt(res["r2"], 2),
                      help="Proporción de la variación explicada por la tendencia lineal (0–1).")
        if res:
            direccion = "aumenta" if res["b"] > 0 else "disminuye"
            st.markdown(f'<div class="callout"><p>📐 <b>Lectura econométrica:</b> en el periodo, el indicador '
                        f'{direccion} en promedio <b>{fmt(abs(res["b"]), 3)} {m["unidad"]}</b> por año en {NOM_DEPTO} '
                        f'(R² = {fmt(res["r2"], 2)}, n = {res["n"]}). Un R² bajo indica que la trayectoria no es '
                        f'lineal y conviene analizar choques o quiebres estructurales.</p></div>',
                        unsafe_allow_html=True)
    st.markdown(badge_fuente(var_s), unsafe_allow_html=True)
    ficha_indicador(var_s)


def tab_rankings() -> None:
    if PANEL.empty:
        sin_datos(); return
    titulo("🏆 Rankings Departamentales",
           "Posición relativa de los territorios. El departamento seleccionado se resalta en teal.")
    var_r = st.selectbox("Indicador", VARS_DISPONIBLES, index=VARS_DISPONIBLES.index(VAR),
                         format_func=nombre_var, key="rk_var", help=ayuda_var(VAR))
    d, anio_ef = valor_ref(PANEL, var_r, ANIO)
    if d.empty:
        st.info("Sin datos."); return
    m = METADATA_VARIABLES[var_r]
    asc = m["mejor"] == "bajo"
    d = d.sort_values("valor", ascending=not asc).reset_index(drop=True)
    d["Puesto"] = d.index + 1
    colores = [TEAL if c == DEPTO else "#93C5FD" for c in d["cod_dpto"]]
    fig = go.Figure(go.Bar(x=d["departamento"], y=d["valor"], marker_color=colores,
                           text=[fmt(v, m["decimales"]) for v in d["valor"]], textposition="outside",
                           hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
    fig.add_hline(y=d["valor"].mean(), line_dash="dash", line_color=SLATE,
                  annotation_text=f"Promedio: {fmt(d['valor'].mean(), m['decimales'])}",
                  annotation_font_color=SLATE)
    orden = "mejor → peor" if m["mejor"] else "mayor → menor"
    fig.update_layout(title=f"{m['nombre']} · {anio_ef} ({orden})", xaxis_tickangle=-45,
                      yaxis_title=m["unidad"], xaxis_title="")
    mostrar(estilo_fig(fig, 540), key="rk_fig")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🥇 Top 5**")
        st.dataframe(d.head(5)[["Puesto", "departamento", "valor"]].rename(
            columns={"departamento": "Departamento", "valor": m["nombre"]}), hide_index=True)
    with c2:
        st.markdown("**⚠️ Últimos 5**")
        st.dataframe(d.tail(5)[["Puesto", "departamento", "valor"]].rename(
            columns={"departamento": "Departamento", "valor": m["nombre"]}), hide_index=True)

    st.markdown("---")
    titulo("🔬 Laboratorio de correlación (corte transversal)",
           "Relación entre dos indicadores entre departamentos, con recta MCO. Correlación ≠ causalidad.")
    c1, c2 = st.columns(2)
    opciones_y = [v for v in VARS_DISPONIBLES if v != var_r] or VARS_DISPONIBLES
    with c1:
        vx = st.selectbox("Eje X", VARS_DISPONIBLES, index=VARS_DISPONIBLES.index(var_r),
                          format_func=nombre_var, key="cor_x")
    with c2:
        vy = st.selectbox("Eje Y", opciones_y, format_func=nombre_var, key="cor_y")
    dx, ax = valor_ref(PANEL, vx, ANIO)
    dy, ay = valor_ref(PANEL, vy, ANIO)
    if dx.empty or dy.empty:
        st.info("Sin datos suficientes."); return
    j = dx[["cod_dpto", "departamento", "region", "valor"]].merge(
        dy[["cod_dpto", "valor"]], on="cod_dpto", suffixes=("_x", "_y"))
    fig = px.scatter(j, x="valor_x", y="valor_y", color="region", hover_name="departamento",
                     labels={"valor_x": f"{nombre_var(vx)} ({ax})", "valor_y": f"{nombre_var(vy)} ({ay})",
                             "region": "Región"},
                     color_discrete_sequence=[AZUL, TEAL, "#7C3AED", "#F59E0B", "#0EA5E9", "#EC4899"])
    fig.update_traces(marker=dict(size=13, line=dict(width=1, color="#FFFFFF")))
    res = ols(j["valor_x"].values, j["valor_y"].values)
    if res:
        xs = np.linspace(j["valor_x"].min(), j["valor_x"].max(), 50)
        fig.add_trace(go.Scatter(x=xs, y=res["a"] + res["b"] * xs, mode="lines", name="Recta MCO",
                                 line=dict(color=SLATE, dash="dash")))
    sel = j[j["cod_dpto"] == DEPTO]
    if not sel.empty:
        fig.add_annotation(x=sel["valor_x"].iloc[0], y=sel["valor_y"].iloc[0], text=NOM_DEPTO,
                           showarrow=True, arrowhead=2, font=dict(color=SLATE, size=12),
                           bgcolor="#FFFFFF", bordercolor=TEAL)
    mostrar(estilo_fig(fig, 500), key="cor_fig")
    if res:
        c1, c2, c3 = st.columns(3)
        c1.metric("Correlación de Pearson (r)", fmt(res["r"], 2))
        c2.metric("Pendiente β", fmt(res["b"], 3))
        c3.metric("R²", fmt(res["r2"], 2), help=f"n = {res['n']} departamentos")


def tab_tabla() -> None:
    if PANEL.empty:
        sin_datos(); return
    titulo("📋 Tabla Consolidada", "Todos los indicadores por departamento (año efectivo más cercano al de "
                                   "referencia). Descargable para análisis propio.")
    bloques = []
    for v in VARS_DISPONIBLES:
        d, anio_ef = valor_ref(PANEL, v, ANIO)
        if not d.empty:
            bloques.append(d.assign(col=f"{nombre_var(v)} ({anio_ef})")[["cod_dpto", "col", "valor"]])
    if not bloques:
        st.info("Sin datos."); return
    ancho = pd.concat(bloques).pivot_table(index="cod_dpto", columns="col", values="valor").reset_index()
    ancho.insert(1, "Departamento", ancho["cod_dpto"].map(DEPARTAMENTOS))
    ancho.insert(2, "Región", ancho["cod_dpto"].map(REGION_DE))
    ancho = ancho.rename(columns={"cod_dpto": "Código DIVIPOLA"})

    regiones = st.multiselect("Filtrar por región", list(REGIONES.keys()), default=list(REGIONES.keys()),
                              key="tab_reg")
    ancho_f = ancho[ancho["Región"].isin(regiones)]
    st.dataframe(ancho_f, hide_index=True, height=560)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ Descargar tabla consolidada (CSV)",
                           ancho_f.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name=f"observatorio_consolidado_{ANIO}.csv", mime="text/csv",
                           help="Separador ';' y coma decimal (compatible con Excel en español).")
    with c2:
        largo = PANEL.copy()
        largo["indicador"] = largo["variable"].map(nombre_var)
        largo["fuente"] = largo["variable"].map(lambda v: FUENTES[METADATA_VARIABLES[v]["fuente"]]["entidad"])
        st.download_button("⬇️ Descargar panel histórico completo (CSV)",
                           largo.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                           file_name="observatorio_panel_historico.csv", mime="text/csv",
                           help="Formato largo (departamento × año × indicador), ideal para econometría de panel.")


def tab_nacionales() -> None:
    titulo("🌐 Indicadores Macroeconómicos Nacionales",
           "Contexto macro de Colombia según la API oficial del Banco Mundial (series construidas con DANE y BanRep).")
    with st.spinner("Consultando API del Banco Mundial…"):
        bm, err = cargar_banco_mundial()
    if bm.empty:
        st.warning(f"No fue posible consultar el Banco Mundial en este momento. {err or ''}")
        return
    if err:
        st.caption(f"ℹ️ {err}")
    cods = [c for c in INDICADORES_BM if c in set(bm["codigo"])]
    cols = st.columns(3)
    for i, c in enumerate(cods):
        s = bm[bm["codigo"] == c].sort_values("anio")
        ult, prev = s.iloc[-1], (s.iloc[-2] if len(s) > 1 else None)
        meta = INDICADORES_BM[c]
        dec = 0 if c == "NY.GDP.PCAP.CD" else 1
        with cols[i % 3]:
            st.metric(f"{meta['nombre']} ({int(ult['anio'])})", f"{fmt(ult['valor'], dec)} {meta['unidad']}",
                      None if prev is None else f"{fmt(ult['valor'] - prev['valor'], dec)} vs {int(prev['anio'])}",
                      delta_color="off", help=meta["desc"])
    sel = st.selectbox("Serie a graficar", cods, format_func=lambda c: INDICADORES_BM[c]["nombre"], key="bm_sel")
    s = bm[bm["codigo"] == sel].sort_values("anio")
    fig = go.Figure(go.Scatter(x=s["anio"], y=s["valor"], mode="lines+markers", fill="tozeroy",
                               line=dict(color=AZUL, width=3), fillcolor="rgba(37,99,235,0.10)",
                               name=INDICADORES_BM[sel]["nombre"]))
    fig.update_layout(title=f"Colombia · {INDICADORES_BM[sel]['nombre']}", yaxis_title=INDICADORES_BM[sel]["unidad"],
                      xaxis_title="Año")
    mostrar(estilo_fig(fig, 460), key="bm_fig")
    st.markdown(badge("Banco Mundial · World Development Indicators", "blue", url=FUENTES["BM"]["url"]),
                unsafe_allow_html=True)


def tab_fuentes() -> None:
    titulo("📚 Fuentes Oficiales, Metodología y Glosario",
           "Transparencia total: origen de cada dato, estado de la conexión y definiciones.")
    filas = []
    for k, f in FUENTES.items():
        if k in ESTADO:
            est = "🟢 En línea" if ESTADO[k] is None else f"🔴 {ESTADO[k][:120]}"
        else:
            est = "🔵 Consulta bajo demanda / referencia"
        filas.append({"Fuente": f["nombre"], "Entidad": f["entidad"], "Conjunto": f["dataset"],
                      "Enlace": f["url"], "Estado": est})
    st.dataframe(pd.DataFrame(filas), hide_index=True,
                 column_config={"Enlace": st.column_config.LinkColumn("Enlace")})

    st.markdown("#### 🧪 Notas metodológicas")
    st.markdown(
        "- **Promedio nacional**: promedio simple de los departamentos con dato en el año efectivo "
        "(no ponderado por población), tal como se usa en la semaforización.\n"
        "- **Año efectivo**: si un indicador no tiene dato para el año de referencia se usa el último "
        "disponible anterior; el año efectivo se muestra siempre en cada tarjeta y gráfico.\n"
        "- **Homicidios**: conteo de víctimas de homicidio intencional (MinDefensa/Policía). El año en curso es "
        "parcial y se excluye por defecto. Al ser un conteo, compárelo con prudencia entre departamentos de "
        "distinto tamaño.\n"
        "- **Educación**: indicadores del MEN a partir del SIMAT y proyecciones de población del DANE.\n"
        "- **Tendencias y correlaciones**: regresión lineal simple por Mínimos Cuadrados Ordinarios (MCO); "
        "son descriptivas y no implican causalidad.\n"
        "- **Mapa**: límites departamentales desde un GeoJSON público; si no está disponible se usa una vista "
        "por capitales o un ranking de barras, de modo que el módulo nunca queda vacío."
    )
    st.markdown("#### 📘 Glosario de indicadores departamentales")
    glos = pd.DataFrame([{"Indicador": m["nombre"], "Categoría": m["categoria"], "Unidad": m["unidad"],
                          "Qué mide": m["significado"], "Relevancia para política pública": m["impacto"],
                          "Fuente": FUENTES[m["fuente"]]["entidad"]} for m in METADATA_VARIABLES.values()])
    st.dataframe(glos, hide_index=True)
    st.download_button("⬇️ Descargar glosario (CSV)", glos.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="glosario_observatorio.csv", mime="text/csv")


# ======================================================================
# 9. NAVEGACIÓN PRINCIPAL
# ======================================================================
tabs = st.tabs([
    "🏠 Bienvenida & Guía",
    "📊 KPIs & Benchmarking",
    "🗺️ Mapa Interactivo",
    "📈 Series Históricas",
    "🏆 Rankings",
    "📋 Tabla Consolidada",
    "🌐 Indicadores Nacionales",
    "📚 Fuentes Oficiales",
])
modulos = [tab_bienvenida, tab_kpis, tab_mapa, tab_series, tab_rankings, tab_tabla, tab_nacionales, tab_fuentes]
for tab, modulo in zip(tabs, modulos):
    with tab:
        seguro(modulo)

st.markdown('<div class="footer">Observatorio de Analítica Económica y Social por Departamentos · '
            'Datos abiertos oficiales de Colombia (datos.gov.co · DANE · MEN · MinDefensa) y Banco Mundial · '
            'Construido con Python, Streamlit y Plotly.</div>', unsafe_allow_html=True)
