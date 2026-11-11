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
try:  # Tema base claro con azul institucional como color primario (antes de renderizar)
    for _k, _v in {"theme.base": "light", "theme.primaryColor": "#2563EB",
                   "theme.backgroundColor": "#F8FAFC", "theme.textColor": "#0F172A"}.items():
        st._config.set_option(_k, _v)
except Exception:  # noqa: BLE001
    pass

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
    "DANE_PIB": {
        "nombre": "DANE · PIB departamental por actividad económica (cuentas departamentales, base 2015)",
        "entidad": "DANE – Cuentas departamentales (publicado en datos.gov.co por la Gobernación de Caldas)",
        "dataset": "kgyi-qc7j",
        "url": "https://www.datos.gov.co/d/kgyi-qc7j",
    },
    "MINSALUD": {
        "nombre": "MinSalud · BDUA – Afiliados activos a los regímenes subsidiado y contributivo",
        "entidad": "Ministerio de Salud y Protección Social (ADRES/BDUA) – publicado en datos.gov.co",
        "dataset": "d7a5-cnra / tq4m-hmg2",
        "url": "https://www.datos.gov.co/d/d7a5-cnra",
    },
    "ANM": {
        "nombre": "ANM · Volumen de explotación de minerales y regalías pagadas",
        "entidad": "Agencia Nacional de Minería – publicado en datos.gov.co",
        "dataset": "r85m-vv6c",
        "url": "https://www.datos.gov.co/d/r85m-vv6c",
    },
    "MINAGRI": {
        "nombre": "MinAgricultura · Exportaciones agrícolas tradicionales y no tradicionales",
        "entidad": "Ministerio de Agricultura y Desarrollo Rural – publicado en datos.gov.co",
        "dataset": "5fct-ib9u",
        "url": "https://www.datos.gov.co/d/5fct-ib9u",
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
    # ------------------------------ ECONOMÍA ------------------------------
    "crecimiento_pib": {
        "nombre": "Crecimiento real del PIB", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": "alto", "decimales": 1,
        "significado": "Variación anual del PIB departamental a precios constantes de 2015 (descuenta la "
                       "inflación): mide cuánto creció realmente la producción del territorio.",
        "impacto": "Termómetro del ciclo económico regional: anticipa empleo, recaudo tributario propio y "
                   "demanda de servicios sociales. Caídas fuertes justifican medidas contracíclicas.",
    },
    "pib_corriente": {
        "nombre": "PIB departamental (precios corrientes)", "unidad": "miles de millones COP",
        "fuente": "DANE_PIB", "categoria": "Economía", "mejor": None, "decimales": 0,
        "significado": "Valor de todos los bienes y servicios finales producidos en el departamento en el año, "
                       "a precios de ese año.",
        "impacto": "Dimensiona el tamaño de la economía y la base tributaria potencial; insumo para "
                   "distribuir regalías, comparar capacidad fiscal y priorizar inversión.",
    },
    "pib_real": {
        "nombre": "PIB real (precios constantes de 2015)", "unidad": "miles de millones COP",
        "fuente": "DANE_PIB", "categoria": "Economía", "mejor": None, "decimales": 0,
        "significado": "PIB valorado a precios de 2015, lo que permite comparar volúmenes de producción entre años.",
        "impacto": "Es la medida correcta para evaluar crecimiento de largo plazo y convergencia regional.",
    },
    "participacion_pib": {
        "nombre": "Participación en el PIB nacional", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 2,
        "significado": "Porcentaje del PIB de Colombia (suma de departamentos) que aporta el departamento.",
        "impacto": "Revela la concentración geográfica de la actividad económica y el peso del territorio "
                   "en la economía nacional.",
    },
    "part_agro": {
        "nombre": "Peso del sector agropecuario", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 1,
        "significado": "Participación de agricultura, ganadería, silvicultura y pesca en el valor agregado "
                       "departamental (precios corrientes).",
        "impacto": "Indica dependencia rural: orienta políticas de desarrollo agropecuario, vías terciarias, "
                   "crédito rural y gestión de riesgos climáticos.",
    },
    "part_mineria": {
        "nombre": "Peso de la minería e hidrocarburos", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 1,
        "significado": "Participación de la explotación de minas y canteras (incluye petróleo y carbón) en el "
                       "valor agregado departamental.",
        "impacto": "Alta dependencia minero-energética implica volatilidad por precios internacionales y "
                   "riesgo de 'enfermedad holandesa'; clave para planear la transición energética.",
    },
    "part_industria": {
        "nombre": "Peso de la industria manufacturera", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 1,
        "significado": "Participación de la industria manufacturera en el valor agregado departamental.",
        "impacto": "Aproxima el grado de sofisticación productiva y generación de empleo formal; base de las "
                   "políticas de reindustrialización y clústeres.",
    },
    "part_construccion": {
        "nombre": "Peso de la construcción", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 1,
        "significado": "Participación de edificaciones y obras civiles en el valor agregado departamental.",
        "impacto": "Sector intensivo en empleo y sensible a la inversión pública (vías, vivienda).",
    },
    "part_comercio": {
        "nombre": "Peso de comercio, transporte y alojamiento", "unidad": "%", "fuente": "DANE_PIB",
        "categoria": "Economía", "mejor": None, "decimales": 1,
        "significado": "Participación de comercio, reparación de vehículos, transporte, alojamiento y "
                       "servicios de comida en el valor agregado.",
        "impacto": "Concentra buena parte del empleo urbano (y la informalidad); relevante para turismo y "
                   "logística regional.",
    },
    "ihh_sectorial": {
        "nombre": "Concentración productiva (índice Herfindahl-Hirschman)", "unidad": "índice 0–10.000",
        "fuente": "DANE_PIB", "categoria": "Economía", "mejor": "bajo", "decimales": 0,
        "significado": "Suma de los cuadrados de las participaciones (%) de las 12 ramas en el valor agregado. "
                       "Valores altos = economía concentrada en pocos sectores.",
        "impacto": "Mide la diversificación económica: territorios concentrados son más vulnerables a choques "
                   "sectoriales (precios del petróleo, clima, etc.).",
    },
    "export_agro": {
        "nombre": "Exportaciones agropecuarias", "unidad": "miles US$ FOB", "fuente": "MINAGRI",
        "categoria": "Economía", "mejor": "alto", "decimales": 0,
        "significado": "Valor FOB de las exportaciones agrícolas, pecuarias y pesqueras (tradicionales y no "
                       "tradicionales) según departamento de origen. Solo años completos.",
        "impacto": "Mide la inserción internacional del agro regional y la generación de divisas; orienta "
                   "admisibilidad sanitaria, logística y promoción comercial.",
    },
    "regalias_mineras": {
        "nombre": "Regalías mineras pagadas", "unidad": "millones COP", "fuente": "ANM",
        "categoria": "Economía", "mejor": None, "decimales": 0,
        "significado": "Regalías liquidadas y pagadas por la explotación de minerales (no incluye hidrocarburos) "
                       "en los municipios del departamento.",
        "impacto": "Fuente de financiación del Sistema General de Regalías; indica dependencia de rentas "
                   "extractivas y presiones ambientales y sociales asociadas a la minería.",
    },
    # ----------------------- POBREZA Y PROTECCIÓN SOCIAL -----------------------
    "pct_subsidiado": {
        "nombre": "Afiliados al régimen subsidiado de salud", "unidad": "% de afiliados", "fuente": "MINSALUD",
        "categoria": "Salud y pobreza", "mejor": "bajo", "decimales": 1,
        "significado": "Porcentaje de los afiliados a salud que pertenecen al régimen subsidiado (población sin "
                       "capacidad de pago, focalizada con el Sisbén). Corte vigente de la BDUA.",
        "impacto": "Proxy robusto de pobreza e informalidad laboral: cuanto mayor, menor proporción de "
                   "población con empleo formal que cotiza. Determina presiones sobre el gasto en salud del "
                   "departamento y la nación.",
    },
    "afiliados_subsidiado": {
        "nombre": "Personas en el régimen subsidiado", "unidad": "personas", "fuente": "MINSALUD",
        "categoria": "Salud y pobreza", "mejor": None, "decimales": 0,
        "significado": "Número de afiliados activos al régimen subsidiado de salud (corte vigente BDUA).",
        "impacto": "Dimensiona la población vulnerable que depende de subsidios estatales en salud.",
    },
    "afiliados_contributivo": {
        "nombre": "Personas en el régimen contributivo", "unidad": "personas", "fuente": "MINSALUD",
        "categoria": "Salud y pobreza", "mejor": None, "decimales": 0,
        "significado": "Número de afiliados activos al régimen contributivo (cotizantes y beneficiarios).",
        "impacto": "Aproxima el tamaño del mercado laboral formal y la base de cotización a seguridad social.",
    },
    # ------------------------------ EDUCACIÓN ------------------------------
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

# Módulos temáticos: agrupan los indicadores en el selector y en las tarjetas KPI
MODULOS: dict[str, dict] = {
    "Economía": {"icono": "💼", "color": "#2563EB",
                 "desc": "PIB, crecimiento real, estructura productiva, exportaciones agropecuarias y regalías."},
    "Salud y pobreza": {"icono": "🏥", "color": "#DB2777",
                        "desc": "Afiliación a salud subsidiada y contributiva: proxy de pobreza e informalidad."},
    "Educación": {"icono": "🎓", "color": "#7C3AED",
                  "desc": "Cobertura, deserción, aprobación, repitencia y conectividad de sedes educativas."},
    "Demografía": {"icono": "👥", "color": "#0D9488",
                   "desc": "Población en edad escolar, base de la demanda de servicios sociales."},
    "Seguridad": {"icono": "🛡️", "color": "#EA580C",
                  "desc": "Homicidio intencional, indicador universal de violencia (ODS 16)."},
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
    "SI.POV.DDAY": {"nombre": "Pobreza extrema internacional", "unidad": "% población",
                    "desc": "Población que vive con menos de la línea internacional de pobreza extrema (US$/día, PPA)."},
    "SI.POV.UMIC": {"nombre": "Pobreza (línea países de ingreso medio-alto)", "unidad": "% población",
                    "desc": "Población bajo la línea de pobreza para países de ingreso medio-alto (US$/día, PPA)."},
    "SL.UEM.1524.ZS": {"nombre": "Desempleo juvenil (15–24)", "unidad": "% fuerza laboral joven",
                       "desc": "Desempleo de jóvenes de 15 a 24 años (estimación modelada OIT)."},
    "SL.TLF.CACT.ZS": {"nombre": "Participación laboral", "unidad": "% población 15+",
                       "desc": "Población de 15 años o más económicamente activa (estimación OIT)."},
    "NE.EXP.GNFS.ZS": {"nombre": "Exportaciones de bienes y servicios", "unidad": "% del PIB",
                       "desc": "Valor de las exportaciones como proporción del PIB."},
    "BX.KLT.DINV.WD.GD.ZS": {"nombre": "Inversión extranjera directa (entradas netas)", "unidad": "% del PIB",
                             "desc": "Entradas netas de inversión extranjera directa como proporción del PIB."},
    "SP.POP.TOTL": {"nombre": "Población total", "unidad": "personas",
                    "desc": "Población residente a mitad de año (proyecciones DANE / ONU)."},
}

# ======================================================================
# 3. HOJA DE ESTILOS (UI/UX "THINK TANK")
# ======================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

:root {
    --slate: #0F172A; --azul: #2563EB; --teal: #0D9488; --fondo: #F8FAFC;
    --borde: #E2E8F0; --muted: #64748B; --radius: 14px;
    --sh-sm: 0 1px 2px rgba(15,23,42,.05), 0 1px 3px rgba(15,23,42,.07);
    --sh-md: 0 12px 32px -14px rgba(15,23,42,.28);
}

/* ===================== BASE (tema claro forzado y legible) ===================== */
html, body, [data-testid="stAppViewContainer"], .stApp {
    color: #0F172A !important;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
.stApp, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1100px 420px at 0% -8%, rgba(37,99,235,.09), transparent 60%),
        radial-gradient(900px 380px at 100% 0%, rgba(13,148,136,.09), transparent 60%),
        #F8FAFC !important;
}
[data-testid="stHeader"] { background: rgba(248,250,252,.80) !important; backdrop-filter: blur(8px); }
footer { visibility: hidden; }
.block-container { padding-top: 3.6rem; padding-bottom: 2rem; max-width: 1440px; }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #0F172A; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; letter-spacing: -0.01em; }
.stApp [data-testid="stMarkdownContainer"] p { line-height: 1.62; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 10px; border: 2px solid #F8FAFC; }

/* ===================== BARRA LATERAL ===================== */
section[data-testid="stSidebar"] {
    background: linear-gradient(185deg, #0F172A 0%, #0B1324 60%, #0F1F3A 100%) !important;
    border-right: 1px solid #1E293B;
}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * { color: #E2E8F0 !important; }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-weight: 600 !important; font-size: .86rem; }
section[data-testid="stSidebar"] hr { border-color: #1E293B !important; }
.side-brand { padding: 4px 2px 16px 2px; border-bottom: 1px solid #1E293B; margin-bottom: 8px; }
.side-brand .logo { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; font-size: 1.4rem;
                    background: linear-gradient(135deg, #2563EB, #0D9488); box-shadow: 0 8px 20px -8px rgba(37,99,235,.7); margin-bottom: 10px; }
.side-brand .t { color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.04rem; line-height: 1.3; }
.side-brand .s { color: #5EEAD4 !important; font-size: .70rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.side-label { color: #5EEAD4 !important; font-size: .68rem; font-weight: 800; letter-spacing: .14em;
              text-transform: uppercase; margin: 18px 0 8px 0; display: flex; align-items: center; gap: 8px; }
.side-label::after { content: ""; flex: 1; height: 1px; background: #1E293B; }
.side-mod { display: flex; gap: 10px; align-items: flex-start; background: rgba(255,255,255,.05);
            border: 1px solid rgba(255,255,255,.08); border-left: 4px solid var(--c); border-radius: 10px;
            padding: 10px 12px; margin: 4px 0 10px 0; }
.side-mod .i { font-size: 1.2rem; }
.side-mod .n { color: #FFFFFF !important; font-weight: 700; font-size: .85rem; }
.side-mod .d { color: #94A3B8 !important; font-size: .74rem; line-height: 1.4; }

/* ===================== CONTROLES: CONTRASTE IMPECABLE ===================== */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="base-input"] {
    background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important; border-radius: 10px !important;
    transition: border-color .15s ease, box-shadow .15s ease;
}
[data-baseweb="select"] > div:hover { border-color: #2563EB !important; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
[data-baseweb="select"] *, [data-baseweb="input"] input, [data-baseweb="base-input"] input {
    color: #0F172A !important; -webkit-text-fill-color: #0F172A !important; font-weight: 500;
}
[data-baseweb="select"] svg { fill: #334155 !important; }
[data-baseweb="tag"] { background-color: #DBEAFE !important; border-radius: 8px !important; }
[data-baseweb="tag"] * { color: #1E3A8A !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"], ul[role="listbox"] {
    background-color: #FFFFFF !important; border-radius: 12px !important; box-shadow: var(--sh-md) !important;
}
[data-baseweb="popover"] li, ul[role="listbox"] li, [role="option"] { color: #0F172A !important; background-color: #FFFFFF !important; }
[role="option"]:hover, [aria-selected="true"][role="option"] { background-color: #EFF6FF !important; }
[data-testid="stMain"] [data-testid="stWidgetLabel"] p, .main [data-testid="stWidgetLabel"] p {
    color: #0F172A !important; font-weight: 600 !important; font-size: .9rem;
}
[data-testid="stSlider"] [role="slider"] {
    background-color: #2563EB !important; border: 3px solid #FFFFFF !important; box-shadow: 0 0 0 2px #2563EB !important;
}
[data-testid="stSliderThumbValue"], [data-testid="stSliderThumbValue"] * {
    color: #FFFFFF !important; background: #2563EB !important; padding: 1px 8px; border-radius: 6px; font-weight: 700 !important;
}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] { color: #475569 !important; font-weight: 600; }
section[data-testid="stSidebar"] [data-testid="stSliderTickBarMin"],
section[data-testid="stSidebar"] [data-testid="stSliderTickBarMax"] { color: #CBD5E1 !important; }
[data-testid="stRadio"] label p { font-weight: 500; }

/* ===================== CONTENEDORES ===================== */
[data-testid="stExpander"] {
    background: #FFFFFF !important; border: 1px solid var(--borde) !important; border-radius: var(--radius) !important;
    box-shadow: var(--sh-sm); overflow: hidden;
}
[data-testid="stExpander"] summary { padding-top: .8rem; padding-bottom: .8rem; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: #0F172A !important; font-weight: 600; }
section[data-testid="stSidebar"] [data-testid="stExpander"] * { color: #0F172A !important; }
[data-testid="stPlotlyChart"] {
    background: #FFFFFF; border: 1px solid var(--borde); border-radius: var(--radius);
    box-shadow: var(--sh-sm); padding: 8px 6px 2px 6px; overflow: hidden;
}
[data-testid="stDataFrame"] { border: 1px solid var(--borde); border-radius: 12px; overflow: hidden; box-shadow: var(--sh-sm); }
[data-testid="stAlert"] { border-radius: 12px !important; }
[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid var(--borde); border-radius: var(--radius); padding: 16px 18px;
    box-shadow: var(--sh-sm); border-top: 3px solid #2563EB;
}
[data-testid="stMetricValue"] { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800 !important; }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] * { color: #0F172A !important; }
hr { border-color: #E2E8F0 !important; margin: 1.6rem 0 !important; }

/* ===================== PESTAÑAS (compatibles con Streamlit clásico y react-aria) ===================== */
.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {
    gap: 4px; background: rgba(255,255,255,.95); padding: 6px; border-radius: 16px;
    border: 1px solid var(--borde); box-shadow: var(--sh-sm); flex-wrap: wrap; margin-bottom: 6px;
}
.stTabs [data-baseweb="tab"], .stTabs [role="tab"] {
    min-height: 42px; padding: 0 15px; border-radius: 11px; background: transparent;
    display: flex; align-items: center; transition: background .15s ease; border: none !important;
}
.stTabs [data-baseweb="tab"]:hover, .stTabs [role="tab"]:hover { background: #F1F5F9; }
.stTabs [data-baseweb="tab"] p, .stTabs [role="tab"] p { color: #334155 !important; font-weight: 600; font-size: .88rem; margin: 0; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #0F172A, #1E3A8A) !important;
                                 box-shadow: 0 6px 16px -8px rgba(15,23,42,.6); }
.stTabs [aria-selected="true"] p { color: #FFFFFF !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"],
.stTabs .react-aria-SelectionIndicator { display: none !important; }
.stTabs [data-baseweb="tab-panel"], .stTabs [data-testid="stTabPanel"] { padding-top: 18px; }

/* ===================== HERO ===================== */
.hero {
    position: relative; overflow: hidden; border-radius: 22px; padding: 42px 44px 34px 44px; margin-bottom: 26px;
    background:
        radial-gradient(circle at 88% 18%, rgba(45,212,191,.40) 0%, transparent 38%),
        radial-gradient(circle at 70% 120%, rgba(59,130,246,.55) 0%, transparent 45%),
        linear-gradient(125deg, #0F172A 0%, #172554 50%, #1D4ED8 100%);
    box-shadow: 0 24px 50px -24px rgba(15,23,42,.65);
}
.hero::before {
    content: ""; position: absolute; inset: 0; opacity: .22;
    background-image: linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px);
    background-size: 34px 34px; mask-image: linear-gradient(90deg, transparent, #000 60%);
    -webkit-mask-image: linear-gradient(90deg, transparent, #000 60%);
}
.hero > * { position: relative; }
.hero .kicker { display: inline-flex; align-items: center; gap: 8px; color: #99F6E4 !important; font-size: .74rem; font-weight: 800;
                letter-spacing: .16em; text-transform: uppercase; background: rgba(13,148,136,.22);
                border: 1px solid rgba(94,234,212,.35); padding: 5px 12px; border-radius: 999px; }
.hero .h1, .hero .h1 * { color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 2.3rem; font-weight: 800; margin: 14px 0 10px 0; line-height: 1.15; max-width: 900px; }
.hero p { color: #DBEAFE !important; font-size: 1.04rem; max-width: 860px; margin: 0; line-height: 1.6; }
.hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-top: 28px; max-width: 900px; }
.hero-stat { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.16); border-radius: 14px;
             padding: 14px 18px; backdrop-filter: blur(6px); }
.hero-stat .v { color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.7rem; font-weight: 800; display: block; }
.hero-stat .l { color: #BFDBFE !important; font-size: .78rem; font-weight: 500; }

/* ===================== TÍTULOS DE SECCIÓN ===================== */
.section-title { display: flex; align-items: center; gap: 12px; font-family: 'Plus Jakarta Sans', sans-serif;
                 font-size: 1.32rem; font-weight: 800; color: #0F172A !important; margin: 10px 0 4px 0; }
.section-title::before { content: ""; width: 6px; height: 26px; border-radius: 6px; background: linear-gradient(180deg, #2563EB, #0D9488); flex: none; }
.section-sub { color: #64748B !important; font-size: .92rem; margin: 0 0 16px 18px; }
.callout { background: linear-gradient(90deg, #F0FDFA, #FFFFFF 60%); border: 1px solid #CCFBF1; border-left: 4px solid #0D9488;
           border-radius: 12px; padding: 14px 18px; box-shadow: var(--sh-sm); margin: 10px 0 18px 0; }
.callout p { margin: 0; color: #334155 !important; }

/* ===================== PASOS (portada) ===================== */
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 8px; }
.step { background: #FFFFFF; border: 1px solid var(--borde); border-radius: var(--radius); padding: 18px; box-shadow: var(--sh-sm);
        transition: transform .18s ease, box-shadow .18s ease; }
.step:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.step .num { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; font-weight: 800; color: #FFFFFF !important;
             background: linear-gradient(135deg, #2563EB, #0D9488); margin-bottom: 10px; }
.step h5 { margin: 0 0 4px 0; font-size: .98rem; font-weight: 700; color: #0F172A !important; font-family: 'Plus Jakarta Sans', sans-serif; }
.step p { margin: 0; color: #475569 !important; font-size: .86rem; line-height: 1.5; }

/* ===================== MÓDULOS TEMÁTICOS ===================== */
.mod-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 8px; }
.mod-card { background: #FFFFFF; border: 1px solid var(--borde); border-radius: var(--radius); padding: 18px; box-shadow: var(--sh-sm);
            border-top: 4px solid var(--c); transition: transform .18s ease, box-shadow .18s ease; }
.mod-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.mod-card .ico { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; font-size: 1.3rem;
                 background: #F1F5F9; background: color-mix(in srgb, var(--c) 14%, white); margin-bottom: 10px; }
.mod-card h5 { margin: 0 0 4px 0; font-size: 1rem; font-weight: 800; color: #0F172A !important; font-family: 'Plus Jakarta Sans', sans-serif; }
.mod-card p { margin: 0 0 10px 0; color: #475569 !important; font-size: .84rem; line-height: 1.5; }
.mod-card .cnt { font-size: .74rem; font-weight: 700; color: var(--c) !important; }
.mod-header { display: flex; align-items: center; gap: 12px; margin: 26px 0 14px 0; padding: 12px 16px; background: #FFFFFF;
              border: 1px solid var(--borde); border-left: 5px solid var(--c); border-radius: 12px; box-shadow: var(--sh-sm); }
.mod-header .ico { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; font-size: 1.15rem;
                   background: #F1F5F9; background: color-mix(in srgb, var(--c) 14%, white); }
.mod-header .t { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.08rem; color: #0F172A !important; }
.mod-header .d { font-size: .82rem; color: #64748B !important; }
.mod-chip { display: inline-flex; align-items: center; gap: 5px; font-size: .68rem; font-weight: 800; letter-spacing: .06em;
            text-transform: uppercase; padding: 3px 9px; border-radius: 999px; color: var(--c) !important;
            background: #F1F5F9; background: color-mix(in srgb, var(--c) 11%, white); }

/* ===================== TARJETAS KPI ===================== */
.kpi-card {
    background: linear-gradient(180deg, #FFFFFF 0%, #FBFDFF 100%); border: 1px solid var(--borde); border-radius: var(--radius);
    padding: 16px 18px 15px 18px; box-shadow: var(--sh-sm); border-top: 4px solid var(--accent, #2563EB);
    height: 100%; position: relative; transition: transform .18s ease, box-shadow .18s ease;
}
.kpi-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); }
.kpi-card .name { font-size: .9rem; font-weight: 600; color: #0F172A !important; margin: 10px 0 8px 0; min-height: 2.5em; line-height: 1.3; }
.kpi-card .value { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.85rem; font-weight: 800; color: #0F172A !important; letter-spacing: -0.02em; }
.kpi-card .unit { font-size: .82rem; color: #64748B !important; font-weight: 500; margin-left: 5px; }
.kpi-card .meta { font-size: .74rem; color: #64748B !important; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #E2E8F0; }
.kpi-card .delta { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; padding: 4px 10px;
                   border-radius: 999px; font-size: .78rem; font-weight: 700; }
.delta.good { background: #DCFCE7; color: #166534 !important; }
.delta.mid  { background: #FEF3C7; color: #92400E !important; }
.delta.bad  { background: #FEE2E2; color: #991B1B !important; }
.delta.neu  { background: #F1F5F9; color: #334155 !important; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; position: absolute; top: 18px; right: 16px;
       box-shadow: 0 0 0 4px rgba(148,163,184,.15); }

/* ===================== FUENTES OFICIALES ===================== */
.src-wrap { background: #FFFFFF; border: 1px solid var(--borde); border-radius: 20px; padding: 26px; box-shadow: var(--sh-sm); margin-top: 6px; }
.src-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 16px; }
.src-card { border: 1px solid var(--borde); border-radius: 14px; padding: 18px; display: flex; flex-direction: column; gap: 8px;
            background: linear-gradient(180deg, #FFFFFF, #F8FAFC); transition: transform .18s ease, box-shadow .18s ease, border-color .18s; }
.src-card:hover { transform: translateY(-3px); box-shadow: var(--sh-md); border-color: #BFDBFE; }
.src-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.src-ent { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.02rem; color: #0F172A !important; }
.src-name { color: #334155 !important; font-size: .86rem; line-height: 1.45; }
.src-meta { color: #64748B !important; font-size: .76rem; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: .72rem; font-weight: 800; white-space: nowrap; }
.pill.ok { background: #DCFCE7; color: #166534 !important; }
.pill.off { background: #FEE2E2; color: #991B1B !important; }
.pill.ref { background: #E0E7FF; color: #3730A3 !important; }
.src-link { margin-top: auto; display: inline-flex; align-items: center; gap: 6px; align-self: flex-start; text-decoration: none !important;
            background: #0F172A; color: #FFFFFF !important; font-size: .78rem; font-weight: 700; padding: 7px 13px; border-radius: 9px; }
.src-link:hover { background: #2563EB; }

/* ===================== INSIGNIAS ===================== */
.source-badge {
    display: inline-flex; align-items: center; gap: 6px; background: #F0FDFA; color: #115E59 !important;
    border: 1px solid #99F6E4; border-radius: 999px; padding: 3px 11px; font-size: .74rem;
    font-weight: 700; letter-spacing: .02em; margin: 2px 4px 2px 0; text-decoration: none !important;
}
.source-badge.off { background: #FEF2F2; color: #991B1B !important; border-color: #FECACA; }
.source-badge.blue { background: #EFF6FF; color: #1D4ED8 !important; border-color: #BFDBFE; }
section[data-testid="stSidebar"] .source-badge { background: rgba(20,184,166,.12); border-color: rgba(94,234,212,.35); color: #99F6E4 !important; }
section[data-testid="stSidebar"] .source-badge.off { background: rgba(239,68,68,.15); border-color: rgba(252,165,165,.4); color: #FCA5A5 !important; }

/* ===================== BOTONES ===================== */
.stDownloadButton button, .stButton button {
    background: linear-gradient(135deg, #2563EB, #1D4ED8) !important; color: #FFFFFF !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important; padding: .55rem 1.1rem !important;
    box-shadow: 0 8px 18px -10px rgba(37,99,235,.8);
}
.stDownloadButton button *, .stButton button * { color: #FFFFFF !important; }
.stDownloadButton button:hover, .stButton button:hover { filter: brightness(1.08); }

/* ===================== PIE DE PÁGINA ===================== */
.footer { margin-top: 40px; border-radius: 18px; padding: 22px 26px; background: linear-gradient(120deg, #0F172A, #172554);
          display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; align-items: center; }
.footer .b { color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; }
.footer .s { color: #94A3B8 !important; font-size: .8rem; }
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


def _socrata_paginado(dataset_id: str, params: dict, pagina: int = 50000, max_paginas: int = 8) -> pd.DataFrame:
    """Descarga completa con paginación ($limit/$offset) para conjuntos grandes."""
    partes, offset = [], 0
    for _ in range(max_paginas):
        p = dict(params)
        p.update({"$limit": pagina, "$offset": offset})
        p.setdefault("$order", ":id")
        d = _socrata(dataset_id, p)
        if d.empty:
            break
        partes.append(d)
        if len(d) < pagina:
            break
        offset += pagina
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def _sector_corto(actividad: str) -> str:
    """Abrevia las 12 ramas de actividad de las cuentas departamentales del DANE (+ impuestos)."""
    a = _norm_txt(actividad)
    reglas = [("IMPUESTO", "Impuestos"), ("AGRICULTURA", "Agropecuario"), ("MINAS", "Minería"),
              ("MANUFACTUR", "Industria"), ("ELECTRICIDAD", "Servicios públicos"),
              ("CONSTRUCCION", "Construcción"), ("COMERCIO", "Comercio, transporte y alojamiento"),
              ("INFORMACION", "Información y comunicaciones"), ("FINANCIERAS", "Financiero"),
              ("INMOBILIARIAS", "Inmobiliario"), ("PROFESIONALES", "Profesionales y administrativos"),
              ("ADMINISTRACIONPUBLICA", "Admin. pública, educación y salud"),
              ("ARTISTICAS", "Artes y otros servicios")]
    for clave, corto in reglas:
        if clave in a:
            return corto
    return "Otros"


SECTOR_A_VARIABLE = {"Agropecuario": "part_agro", "Minería": "part_mineria", "Industria": "part_industria",
                     "Construcción": "part_construccion", "Comercio, transporte y alojamiento": "part_comercio"}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_pib() -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """
    DANE – PIB departamental por actividad (precios corrientes y constantes de 2015).
    Devuelve (panel largo de indicadores derivados, composición sectorial, error).
    """
    try:
        df = _socrata_paginado(FUENTES["DANE_PIB"]["dataset"], {})
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), "La fuente respondió sin registros."
        vcol = next((c for c in df.columns if c.startswith("valor")), None)
        ccol = next((c for c in df.columns if "departamento" in c and c.startswith(("c_digo", "codigo", "cod"))), None)
        acol = next((c for c in ["a_o", "ano", "anio"] if c in df.columns), None)
        if not (vcol and ccol and acol and "tipo_de_precios" in df.columns and "actividad" in df.columns):
            return pd.DataFrame(), pd.DataFrame(), f"Estructura inesperada: {list(df.columns)}"
        df["cod_dpto"] = df[ccol].map(_norm_cod)
        df["anio"] = pd.to_numeric(df[acol], errors="coerce")
        df["valor"] = pd.to_numeric(df[vcol].astype(str).str.replace(",", "."), errors="coerce")
        df["precios"] = np.where(df["tipo_de_precios"].str.lower().str.contains("corriente"), "corrientes", "constantes")
        df["sector"] = df["actividad"].map(_sector_corto)
        df = df.dropna(subset=["cod_dpto", "anio", "valor"])
        df["anio"] = df["anio"].astype(int)

        # PIB total = suma de ramas + impuestos
        tot = df.groupby(["cod_dpto", "anio", "precios"], as_index=False)["valor"].sum()
        cor = tot[tot["precios"] == "corrientes"][["cod_dpto", "anio", "valor"]]
        con = tot[tot["precios"] == "constantes"][["cod_dpto", "anio", "valor"]].sort_values(["cod_dpto", "anio"])
        con = con.assign(crec=con.groupby("cod_dpto")["valor"].pct_change() * 100)
        nac = cor.groupby("anio")["valor"].transform("sum")
        partes = [
            cor.assign(variable="pib_corriente"),
            con[["cod_dpto", "anio", "valor"]].assign(variable="pib_real"),
            con.dropna(subset=["crec"])[["cod_dpto", "anio", "crec"]].rename(columns={"crec": "valor"})
               .assign(variable="crecimiento_pib"),
            cor.assign(valor=cor["valor"] / nac * 100, variable="participacion_pib"),
        ]
        # Estructura del valor agregado (precios corrientes, sin impuestos)
        sect = (df[(df["precios"] == "corrientes") & (df["sector"] != "Impuestos")]
                .groupby(["cod_dpto", "anio", "sector"], as_index=False)["valor"].sum())
        sect["share"] = sect["valor"] / sect.groupby(["cod_dpto", "anio"])["valor"].transform("sum") * 100
        for sec, var in SECTOR_A_VARIABLE.items():
            s = sect[sect["sector"] == sec][["cod_dpto", "anio", "share"]].rename(columns={"share": "valor"})
            partes.append(s.assign(variable=var))
        ihh = sect.assign(c=sect["share"] ** 2).groupby(["cod_dpto", "anio"], as_index=False)["c"].sum()
        partes.append(ihh.rename(columns={"c": "valor"}).assign(variable="ihh_sectorial"))
        largo = pd.concat(partes, ignore_index=True)[["cod_dpto", "anio", "variable", "valor"]]
        return largo, sect, None
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame(), pd.DataFrame(), f"{type(e).__name__}: {e}"


def _suma_por_departamento(dataset_id: str) -> pd.DataFrame:
    """Suma la columna 'cantidad' por departamento probando el casteo numérico de SoQL."""
    ultimo = None
    for expr in ("sum(cantidad::number)", "sum(cantidad)"):
        try:
            d = _socrata(dataset_id, {"$select": f"dpr_nombre, {expr} as total", "$group": "dpr_nombre",
                                      "$limit": 1000})
            if not d.empty:
                return d
        except Exception as e:  # noqa: BLE001
            ultimo = e
    raise ultimo or RuntimeError("Sin datos")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_salud() -> tuple[pd.DataFrame, str | None]:
    """MinSalud – BDUA: afiliados activos a los regímenes subsidiado y contributivo (corte vigente)."""
    try:
        res = {}
        for regimen, ds in (("subsidiado", "d7a5-cnra"), ("contributivo", "tq4m-hmg2")):
            d = _suma_por_departamento(ds)
            d["cod_dpto"] = d["dpr_nombre"].map(_cod_desde_nombre)
            d["total"] = pd.to_numeric(d["total"], errors="coerce")
            res[regimen] = d.dropna(subset=["cod_dpto", "total"]).groupby("cod_dpto")["total"].sum()
        m = pd.concat(res, axis=1).fillna(0)
        m["pct"] = m["subsidiado"] / (m["subsidiado"] + m["contributivo"]) * 100
        anio = ANIO_ACTUAL  # La BDUA es un corte vigente (sin columna de fecha)
        partes = [
            m["pct"].rename("valor").reset_index().assign(variable="pct_subsidiado"),
            m["subsidiado"].rename("valor").reset_index().assign(variable="afiliados_subsidiado"),
            m["contributivo"].rename("valor").reset_index().assign(variable="afiliados_contributivo"),
        ]
        largo = pd.concat(partes, ignore_index=True).assign(anio=anio)
        return largo[["cod_dpto", "anio", "variable", "valor"]], None
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_regalias() -> tuple[pd.DataFrame, str | None]:
    """ANM – regalías mineras pagadas, agregadas por departamento y año de liquidación."""
    try:
        df = _socrata_paginado(FUENTES["ANM"]["dataset"],
                               {"$select": "codigo_dane, nombre_departamento, a_o_liquidado, regalias_pagadas"})
        if df.empty:
            return pd.DataFrame(), "La fuente respondió sin registros."
        cod_mun = df["codigo_dane"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(5).str[:2]
        df["cod_dpto"] = cod_mun.map(_norm_cod)
        faltan = df["cod_dpto"].isna()
        df.loc[faltan, "cod_dpto"] = df.loc[faltan, "nombre_departamento"].map(_cod_desde_nombre)
        df["anio"] = pd.to_numeric(df["a_o_liquidado"], errors="coerce")
        # Formato de origen '1,721,567.00' (separador de miles = coma)
        limpio = df["regalias_pagadas"].astype(str).str.replace(",", "").str.replace(r"[^\d\.\-]", "", regex=True)
        df["valor"] = pd.to_numeric(limpio, errors="coerce").fillna(0) / 1e6
        df = df.dropna(subset=["cod_dpto", "anio"])
        g = df.groupby(["cod_dpto", "anio"], as_index=False)["valor"].sum()
        g["anio"] = g["anio"].astype(int)
        return g.assign(variable="regalias_mineras")[["cod_dpto", "anio", "variable", "valor"]], None
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def cargar_exportaciones_agro() -> tuple[pd.DataFrame, str | None]:
    """MinAgricultura – exportaciones agropecuarias (miles US$ FOB) por departamento y año."""
    try:
        df = _socrata(FUENTES["MINAGRI"]["dataset"], {
            "$select": "a_o, mes, departamento, sum(exportaciones_en_valor_miles) as v",
            "$group": "a_o, mes, departamento", "$limit": 50000})
        if df.empty:
            return pd.DataFrame(), "La fuente respondió sin registros."
        df["anio"] = pd.to_numeric(df["a_o"], errors="coerce")
        df["valor"] = pd.to_numeric(df["v"], errors="coerce")
        df["cod_dpto"] = df["departamento"].map(_cod_desde_nombre)
        meses = df.groupby("anio")["mes"].nunique()
        completos = meses[meses >= 12].index           # solo años con los 12 meses
        df = df[df["anio"].isin(completos)].dropna(subset=["cod_dpto", "anio", "valor"])
        g = df.groupby(["cod_dpto", "anio"], as_index=False)["valor"].sum()
        g["anio"] = g["anio"].astype(int)
        return g.assign(variable="export_agro")[["cod_dpto", "anio", "variable", "valor"]], None
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


def construir_panel(incluir_parcial: bool) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Une todas las fuentes en un panel largo: cod_dpto | anio | variable | valor.
    Devuelve también la composición sectorial del PIB y el estado de cada fuente.
    """
    estado = {}
    edu, estado["MEN"] = cargar_educacion()
    hom, estado["MINDEFENSA"] = cargar_homicidios()
    pib, sectores, estado["DANE_PIB"] = cargar_pib()
    salud, estado["MINSALUD"] = cargar_salud()
    reg, estado["ANM"] = cargar_regalias()
    exp_, estado["MINAGRI"] = cargar_exportaciones_agro()
    # Registros administrativos del año en curso están incompletos → se excluyen por defecto
    if not incluir_parcial:
        hom = hom[hom["anio"] < ANIO_ACTUAL] if not hom.empty else hom
        reg = reg[reg["anio"] < ANIO_ACTUAL] if not reg.empty else reg
    partes = [p for p in (pib, salud, edu, hom, reg, exp_) if not p.empty]
    if not partes:
        return pd.DataFrame(columns=["cod_dpto", "anio", "variable", "valor",
                                     "departamento", "region"]), sectores, estado
    panel = pd.concat(partes, ignore_index=True)
    panel = panel[np.isfinite(panel["valor"])]
    panel["departamento"] = panel["cod_dpto"].map(DEPARTAMENTOS)
    panel["region"] = panel["cod_dpto"].map(REGION_DE)
    return panel, sectores, estado


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


def nombre_var_mod(v: str) -> str:
    """Nombre del indicador precedido por el icono de su módulo temático (para los selectores)."""
    cat = METADATA_VARIABLES.get(v, {}).get("categoria", "")
    return f"{MODULOS.get(cat, {}).get('icono', '')} {nombre_var(v)}"


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
        <span class="mod-chip" style="--c:{MODULOS.get(m['categoria'], {}).get('color', AZUL)}">{MODULOS.get(m['categoria'], {}).get('icono', '')} {m['categoria']}</span>
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
        colorway=[AZUL, TEAL, "#7C3AED", "#F59E0B", "#DB2777", "#0EA5E9", "#84CC16", "#EA580C"],
        font=dict(family="Inter, Segoe UI, sans-serif", color=SLATE, size=13),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=60, b=20),
        title_font=dict(size=16, color=SLATE, family="Plus Jakarta Sans, Inter, sans-serif"),
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

with st.spinner("Conectando con datos.gov.co (DANE · MinSalud · MEN · MinDefensa · ANM · MinAgricultura) …"):
    PANEL, SECTORES, ESTADO = construir_panel(st.session_state["incluir_parcial"])

VARS_DISPONIBLES = [v for v in METADATA_VARIABLES if v in set(PANEL["variable"].unique())]
if not VARS_DISPONIBLES:
    VARS_DISPONIBLES = list(METADATA_VARIABLES.keys())
ANIOS = sorted(PANEL["anio"].unique().tolist()) if not PANEL.empty else [ANIO_ACTUAL - 1]
ANIO_MIN, ANIO_MAX = int(min(ANIOS)), int(max(ANIOS))
CODIGOS = list(DEPARTAMENTOS.keys())
# Indicadores agrupados por módulo temático (en el orden definido en MODULOS)
VARS_POR_CAT: dict[str, list[str]] = {}
for _v in VARS_DISPONIBLES:
    VARS_POR_CAT.setdefault(METADATA_VARIABLES[_v]["categoria"], []).append(_v)
CATS_DISPONIBLES = [c for c in MODULOS if c in VARS_POR_CAT] + [c for c in VARS_POR_CAT if c not in MODULOS]


def categoria_de(v: str) -> str:
    return METADATA_VARIABLES[v]["categoria"]


def etiqueta_mod(c: str) -> str:
    return f"{MODULOS.get(c, {}).get('icono', '•')} {c}"


def _init_estado() -> None:
    """Estado canónico + copias para los widgets de la barra lateral (sb_) y la portada (qc_)."""
    preferidas = [v for v in ("crecimiento_pib", "pct_subsidiado", "cobertura_neta") if v in VARS_DISPONIBLES]
    defaults = {"depto": "05", "var": (preferidas or VARS_DISPONIBLES)[0], "anio": ANIO_MAX}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    # Validaciones defensivas (p. ej. si cambió el rango de años)
    if st.session_state["var"] not in VARS_DISPONIBLES:
        st.session_state["var"] = VARS_DISPONIBLES[0]
    st.session_state["anio"] = int(min(max(st.session_state["anio"], ANIO_MIN), ANIO_MAX))
    st.session_state["cat"] = categoria_de(st.session_state["var"])
    for pref in ("sb_", "qc_"):
        for k in list(defaults) + ["cat"]:
            st.session_state[pref + k] = st.session_state[k]


def _sync(origen: str, campo: str) -> None:
    """Callback: propaga un cambio desde un panel de control a todos los demás."""
    valor = st.session_state[f"{origen}_{campo}"]
    st.session_state[campo] = valor
    for pref in ("sb", "qc"):
        st.session_state[f"{pref}_{campo}"] = valor


def _sync_cat(origen: str) -> None:
    """Callback: al cambiar de módulo se elige su primer indicador (si el actual no pertenece a él)."""
    cat = st.session_state[f"{origen}_cat"]
    var = st.session_state["var"]
    if categoria_de(var) != cat:
        var = VARS_POR_CAT[cat][0]
    st.session_state["cat"], st.session_state["var"] = cat, var
    for pref in ("sb", "qc"):
        st.session_state[f"{pref}_cat"] = cat
        st.session_state[f"{pref}_var"] = var


_init_estado()


def controles(prefijo: str, contenedor) -> None:
    """Dibuja el trío de controles (departamento, indicador, año) con sincronización."""
    with contenedor:
        st.selectbox("🏛️ Departamento", CODIGOS, key=f"{prefijo}_depto",
                     format_func=lambda c: DEPARTAMENTOS[c], on_change=_sync, args=(prefijo, "depto"),
                     help="Territorio de análisis. Las comparaciones se hacen frente al promedio de los "
                          "departamentos con dato y frente a su región natural.")
        st.selectbox("🧩 Módulo temático", CATS_DISPONIBLES, key=f"{prefijo}_cat", format_func=etiqueta_mod,
                     on_change=_sync_cat, args=(prefijo,),
                     help="Agrupa los indicadores por área: Economía, Salud y pobreza, Educación, "
                          "Demografía y Seguridad.")
        cat = st.session_state["cat"]
        st.selectbox(f"📐 Indicador principal · {len(VARS_POR_CAT[cat])} disponibles", VARS_POR_CAT[cat],
                     key=f"{prefijo}_var", format_func=nombre_var_mod, on_change=_sync, args=(prefijo, "var"),
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
    st.markdown('<div class="side-brand"><div class="logo">🇨🇴</div><div class="s">Observatorio Territorial</div>'
                '<div class="t">Analítica Económica y Social por Departamentos</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="side-label">Panel de análisis</div>', unsafe_allow_html=True)
    controles("sb", st.container())
    _m = MODULOS.get(st.session_state["cat"], {})
    st.markdown(f'<div class="side-mod" style="--c:{_m.get("color", AZUL)}"><div class="i">{_m.get("icono", "")}</div>'
                f'<div><div class="n">{st.session_state["cat"]}</div><div class="d">{_m.get("desc", "")}</div></div></div>',
                unsafe_allow_html=True)
    st.toggle("Incluir año en curso (cifras parciales)", key="incluir_parcial",
              help="Homicidios (MinDefensa) y regalías (ANM) se actualizan durante el año; el año en curso "
                   "está incompleto y no es comparable con años cerrados.")
    st.markdown('<div class="side-label">Estado de las fuentes</div>', unsafe_allow_html=True)
    etiquetas = {"DANE_PIB": "DANE PIB", "MINSALUD": "MinSalud", "MEN": "MEN", "MINDEFENSA": "MinDefensa",
                 "ANM": "ANM", "MINAGRI": "MinAgricultura"}
    st.markdown(" ".join(badge(f"{etiquetas.get(k, k)} {'✓' if e is None else '✗'}", "" if e is None else "off")
                         for k, e in ESTADO.items()), unsafe_allow_html=True)
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
        <div class="h1">Observatorio de Analítica Económica y Social por Departamentos</div>
        <p>Indicadores oficiales de economía (PIB, estructura productiva, exportaciones, regalías), pobreza y
        protección social, educación, demografía y seguridad para los 32 departamentos y Bogotá D.C., con
        benchmarking regional, mapas, series históricas y herramientas econométricas para la toma de
        decisiones de gobernadores, analistas y ciudadanía.</p>
        <div class="hero-stats">
            <div class="hero-stat"><span class="v">{n_dptos}</span><span class="l">territorios con dato</span></div>
            <div class="hero-stat"><span class="v">{n_vars}</span><span class="l">indicadores oficiales</span></div>
            <div class="hero-stat"><span class="v">{ANIO_MIN}–{ANIO_MAX}</span><span class="l">cobertura temporal</span></div>
            <div class="hero-stat"><span class="v">{fuentes_ok}/{len(ESTADO)}</span><span class="l">fuentes en línea</span></div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ---------- 1. Cómo usar ----------
    titulo("🧭 ¿Cómo usar este observatorio?", "Cuatro pasos para pasar de los datos a la decisión.")
    pasos = [
        ("Elija territorio y módulo", "Seleccione un <b>departamento</b>, un <b>módulo temático</b> y su "
                                      "<b>indicador</b> en el panel de abajo o en la barra lateral."),
        ("Diagnostique", "En <b>📊 KPIs</b> vea el semáforo frente al promedio nacional o de su región."),
        ("Profundice", "Use <b>💼 Economía & Pobreza</b>, <b>🗺️ Mapa</b>, <b>📈 Series</b> y <b>🏆 Rankings</b> "
                       "para entender causas, brechas y tendencias."),
        ("Descargue y comparta", "Exporte la <b>📋 Tabla consolidada</b> en CSV y consulte la metodología en "
                                 "<b>📚 Fuentes</b>."),
    ]
    st.markdown('<div class="steps">' + "".join(
        f'<div class="step"><div class="num">{i}</div><h5>{t}</h5><p>{d}</p></div>'
        for i, (t, d) in enumerate(pasos, 1)) + "</div>", unsafe_allow_html=True)

    # ---------- 2. Módulos temáticos ----------
    st.write("")
    titulo("🧩 Módulos temáticos", "Los indicadores están organizados por área de política pública.")
    tarjetas = []
    for cat in CATS_DISPONIBLES:
        mod = MODULOS.get(cat, {})
        n = len(VARS_POR_CAT.get(cat, []))
        tarjetas.append(f'<div class="mod-card" style="--c:{mod.get("color", AZUL)}"><div class="ico">{mod.get("icono", "")}</div>'
                        f'<h5>{cat}</h5><p>{mod.get("desc", "")}</p><span class="cnt">{n} indicador{"es" if n != 1 else ""}</span></div>')
    st.markdown('<div class="mod-grid">' + "".join(tarjetas) + "</div>", unsafe_allow_html=True)

    st.write("")
    titulo("⚡ Panel de control rápido", "Personalice su experiencia: estos controles están sincronizados "
                                         "con la barra lateral y con todas las pestañas.")
    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")
    controles("qc", col_ctrl)
    with col_prev:
        _vista_previa()
    st.write("")
    _fuentes_portada()


def _vista_previa() -> None:
    """Vista previa del indicador seleccionado en el panel de control rápido."""
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


def _fuentes_portada() -> None:
    """Sección a todo el ancho con las fuentes oficiales, su estado y enlace al conjunto de datos."""
    titulo("🏛️ Fuentes oficiales", "Todos los datos se consultan en vivo desde APIs públicas, sin datos simulados. "
                                   "Cada tarjeta indica el estado de la conexión y cuántos indicadores alimenta.")
    iconos = {"DANE_PIB": "📈", "MINSALUD": "🏥", "MEN": "🎓", "MINDEFENSA": "🛡️", "ANM": "⛏️",
              "MINAGRI": "🌾", "BM": "🌐", "DANE": "🗺️"}
    cortos = {"DANE_PIB": "DANE", "MINSALUD": "MinSalud", "MEN": "MinEducación", "MINDEFENSA": "MinDefensa",
              "ANM": "Agencia Nacional de Minería", "MINAGRI": "MinAgricultura", "BM": "Banco Mundial",
              "DANE": "DANE · DIVIPOLA"}
    orden = ["DANE_PIB", "MINSALUD", "MEN", "MINDEFENSA", "ANM", "MINAGRI", "BM", "DANE"]
    tarjetas = []
    for k in [o for o in orden if o in FUENTES] + [o for o in FUENTES if o not in orden]:
        f = FUENTES[k]
        if k in ESTADO:
            pill = '<span class="pill ok">● En línea</span>' if ESTADO[k] is None else '<span class="pill off">● Sin conexión</span>'
        else:
            pill = '<span class="pill ref">● Referencia</span>'
        n = sum(1 for v in VARS_DISPONIBLES if METADATA_VARIABLES[v]["fuente"] == k)
        extra = f"{n} indicador{'es' if n != 1 else ''} · " if n else ""
        entidad = cortos.get(k, f["entidad"].split(" – ")[0].split(" (")[0])
        tarjetas.append(
            f'<div class="src-card"><div class="src-top"><span class="src-ent">{iconos.get(k, "📄")} {entidad}</span>{pill}</div>'
            f'<div class="src-name">{f["nombre"].split(" · ", 1)[-1]}</div>'
            f'<div class="src-meta">{extra}Conjunto: {f["dataset"]}</div>'
            f'<a class="src-link" href="{f["url"]}" target="_blank">Ver conjunto de datos ↗</a></div>')
    st.markdown('<div class="src-wrap"><div class="src-grid">' + "".join(tarjetas) + "</div></div>",
                unsafe_allow_html=True)


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

    resumen = []
    for cat in CATS_DISPONIBLES:
        vars_cat = VARS_POR_CAT[cat]
        mod = MODULOS.get(cat, {})
        st.markdown(f'<div class="mod-header" style="--c:{mod.get("color", AZUL)}"><div class="ico">{mod.get("icono", "")}</div>'
                    f'<div><div class="t">{cat}</div><div class="d">{mod.get("desc", "")}</div></div></div>',
                    unsafe_allow_html=True)
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

    titulo("📘 Glosario didáctico de los indicadores",
           f"{len(VARS_DISPONIBLES)} indicadores disponibles. Elija uno para ver su ficha técnica.")
    v_ficha = st.selectbox("Consultar ficha de:", VARS_DISPONIBLES, format_func=nombre_var_mod, key="kpi_ficha")
    ficha_indicador(v_ficha, expandido=True)


def tab_economia() -> None:
    """Perfil económico y social: estructura productiva, crecimiento y pobreza/protección social."""
    if PANEL.empty:
        sin_datos(); return
    titulo(f"💼 Economía & Pobreza · {NOM_DEPTO}",
           "Estructura productiva (DANE), crecimiento real, inserción exportadora, rentas mineras y "
           "proxies de pobreza e informalidad (afiliación a salud).")

    # ---------- Tarjetas resumen ----------
    claves = ["pib_corriente", "crecimiento_pib", "participacion_pib", "ihh_sectorial",
              "pct_subsidiado", "export_agro", "regalias_mineras", "afiliados_contributivo"]
    claves = [v for v in claves if v in VARS_DISPONIBLES]
    cols = st.columns(4)
    for i, v in enumerate(claves):
        d, anio_ef = valor_ref(PANEL, v, ANIO)
        fila = d[d["cod_dpto"] == DEPTO]
        if fila.empty:
            continue
        with cols[i % 4]:
            st.markdown(kpi_card_html(v, float(fila["valor"].iloc[0]), anio_ef, d["valor"].mean(),
                                      "promedio nacional"), unsafe_allow_html=True)
            st.write("")

    # ---------- Estructura productiva ----------
    if SECTORES.empty:
        st.info("La estructura sectorial del PIB no está disponible en este momento.")
    else:
        st.markdown("---")
        titulo("🏭 Estructura productiva", "Participación de cada rama en el valor agregado (precios corrientes).")
        anios_s = sorted(SECTORES["anio"].unique())
        anio_s = max([a for a in anios_s if a <= ANIO] or [anios_s[0]])
        sd = SECTORES[(SECTORES["cod_dpto"] == DEPTO)]
        c1, c2 = st.columns([1.25, 1])
        with c1:
            fig = px.area(sd.sort_values("anio"), x="anio", y="share", color="sector",
                          labels={"anio": "Año", "share": "% del valor agregado", "sector": "Rama"},
                          color_discrete_sequence=px.colors.qualitative.Safe)
            fig.update_layout(title=f"Evolución de la estructura productiva · {NOM_DEPTO}",
                              legend=dict(orientation="h", y=-0.25, font=dict(size=11)))
            mostrar(estilo_fig(fig, 520), key="eco_area")
        with c2:
            dep = sd[sd["anio"] == anio_s][["sector", "share"]].rename(columns={"share": NOM_DEPTO})
            nac = SECTORES[SECTORES["anio"] == anio_s].groupby("sector", as_index=False)["valor"].sum()
            nac["Colombia"] = nac["valor"] / nac["valor"].sum() * 100
            comp = dep.merge(nac[["sector", "Colombia"]], on="sector", how="outer").fillna(0)
            comp = comp.sort_values(NOM_DEPTO)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(y=comp["sector"], x=comp["Colombia"], orientation="h", name="Colombia",
                                  marker_color="#CBD5E1"))
            fig2.add_trace(go.Bar(y=comp["sector"], x=comp[NOM_DEPTO], orientation="h", name=NOM_DEPTO,
                                  marker_color=AZUL))
            fig2.update_layout(title=f"Especialización vs. Colombia · {anio_s}", barmode="group",
                               xaxis_title="% del valor agregado", legend=dict(orientation="h", y=-0.15))
            mostrar(estilo_fig(fig2, 520), key="eco_comp")
        if not comp.empty and comp["Colombia"].sum() > 0:
            comp["ql"] = np.where(comp["Colombia"] > 0, comp[NOM_DEPTO] / comp["Colombia"], np.nan)
            top = comp.dropna(subset=["ql"]).sort_values("ql", ascending=False).head(3)
            texto = ", ".join(f"<b>{r.sector}</b> (QL = {fmt(r.ql, 2)})" for r in top.itertuples())
            st.markdown(f'<div class="callout"><p>🧭 <b>Especialización relativa:</b> según el cociente de '
                        f'localización (QL = participación del sector en el departamento / participación en '
                        f'Colombia; QL &gt; 1 indica especialización), {NOM_DEPTO} se especializa en {texto}.</p></div>',
                        unsafe_allow_html=True)

    # ---------- Crecimiento real vs. nacional ----------
    pr = PANEL[PANEL["variable"] == "pib_real"]
    if not pr.empty:
        st.markdown("---")
        titulo("📈 Ciclo económico", "Crecimiento real anual del departamento frente al agregado nacional.")
        nac = pr.groupby("anio")["valor"].sum().sort_index().pct_change() * 100
        dep = pr[pr["cod_dpto"] == DEPTO].set_index("anio")["valor"].sort_index().pct_change() * 100
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=dep.index, y=dep.values, name=NOM_DEPTO,
                              marker_color=[VERDE if v >= 0 else ROJO for v in dep.fillna(0).values]))
        fig3.add_trace(go.Scatter(x=nac.index, y=nac.values, name="Colombia (suma departamental)",
                                  mode="lines+markers", line=dict(color=SLATE, width=3)))
        fig3.update_layout(title="Crecimiento real del PIB (%)", yaxis_title="%", xaxis_title="Año",
                           legend=dict(orientation="h", y=-0.2))
        mostrar(estilo_fig(fig3, 420), key="eco_ciclo")
        dd = dep.dropna()
        if len(dd) >= 3:
            c1, c2, c3 = st.columns(3)
            c1.metric("Crecimiento promedio anual", f"{fmt(dd.mean(), 2)}%")
            c2.metric("Volatilidad (desv. estándar)", f"{fmt(dd.std(), 2)} p.p.",
                      help="Mayor volatilidad = economía más expuesta a choques.")
            corr = pd.concat([dd, nac], axis=1).dropna().corr().iloc[0, 1]
            c3.metric("Sincronía con el ciclo nacional (r)", fmt(corr, 2),
                      help="Correlación entre el crecimiento departamental y el nacional.")

    # ---------- Pobreza y protección social ----------
    ps, anio_ps = valor_ref(PANEL, "pct_subsidiado", ANIO)
    if not ps.empty:
        st.markdown("---")
        titulo("🧩 Pobreza e informalidad (proxy de afiliación a salud)",
               "Porcentaje de afiliados en el régimen subsidiado: a mayor valor, más población sin capacidad de "
               "pago y menor empleo formal.")
        ps = ps.sort_values("valor")
        fig4 = go.Figure(go.Bar(x=ps["valor"], y=ps["departamento"], orientation="h",
                                marker_color=[TEAL if c == DEPTO else "#FCA5A5" for c in ps["cod_dpto"]],
                                hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig4.add_vline(x=ps["valor"].mean(), line_dash="dash", line_color=SLATE,
                       annotation_text=f"Promedio {fmt(ps['valor'].mean(), 1)}%", annotation_font_color=SLATE)
        fig4.update_layout(title=f"Afiliados al régimen subsidiado (% del total) · corte {anio_ps}",
                           xaxis_title="%", yaxis_title="")
        mostrar(estilo_fig(fig4, 760), key="eco_pobreza")
        # Relación pobreza–estructura productiva (corte transversal)
        pib_s, a_pib = valor_ref(PANEL, "participacion_pib", ANIO)
        if not pib_s.empty:
            j = ps[["cod_dpto", "departamento", "valor"]].merge(
                pib_s[["cod_dpto", "valor"]], on="cod_dpto", suffixes=("_pob", "_pib"))
            res = ols(np.log(j["valor_pib"].clip(lower=1e-6)), j["valor_pob"])
            if res:
                st.markdown(f'<div class="callout"><p>📐 <b>Gradiente territorial:</b> al regresar el % en régimen '
                            f'subsidiado sobre el logaritmo de la participación en el PIB ({a_pib}), la pendiente es '
                            f'<b>{fmt(res["b"], 2)}</b> (R² = {fmt(res["r2"], 2)}): '
                            f'{"los departamentos con economías más grandes tienden a tener menos población subsidiada" if res["b"] < 0 else "no se observa que las economías más grandes tengan menos población subsidiada"}. '
                            f'Relación descriptiva, no causal.</p></div>', unsafe_allow_html=True)

    # ---------- Comercio exterior y rentas mineras ----------
    c1, c2 = st.columns(2)
    for col, var, color in ((c1, "export_agro", TEAL), (c2, "regalias_mineras", AMBAR)):
        s = PANEL[(PANEL["variable"] == var) & (PANEL["cod_dpto"] == DEPTO)].sort_values("anio")
        with col:
            if s.empty:
                st.caption(f"{nombre_var(var)}: sin registros para {NOM_DEPTO}.")
                continue
            m = METADATA_VARIABLES[var]
            f = go.Figure(go.Bar(x=s["anio"], y=s["valor"], marker_color=color,
                                 hovertemplate="%{x}: %{y:,.0f}<extra></extra>"))
            f.update_layout(title=f"{m['nombre']} · {NOM_DEPTO}", yaxis_title=m["unidad"], xaxis_title="Año")
            mostrar(estilo_fig(f, 360), key=f"eco_{var}")
            st.markdown(badge_fuente(var), unsafe_allow_html=True)


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
                                format_func=nombre_var_mod, key="map_var", help=ayuda_var(VAR))
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
                             format_func=nombre_var_mod, key="ser_var", help=ayuda_var(VAR))
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
                         format_func=nombre_var_mod, key="rk_var", help=ayuda_var(VAR))
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
                          format_func=nombre_var_mod, key="cor_x")
    with c2:
        vy = st.selectbox("Eje Y", opciones_y, format_func=nombre_var_mod, key="cor_y")
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
        dec = 0 if c in ("NY.GDP.PCAP.CD", "SP.POP.TOTL") else 1
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
        "- **PIB departamental**: cuentas departamentales del DANE (base 2015). El total incluye impuestos; "
        "la estructura sectorial y el índice Herfindahl-Hirschman se calculan sobre el valor agregado (sin "
        "impuestos) a precios corrientes; el crecimiento real usa precios constantes de 2015. El último año "
        "suele ser provisional en el DANE.\n"
        "- **Pobreza / informalidad**: el DANE publica la pobreza monetaria y multidimensional departamental en "
        "anexos Excel sin API estable; como indicador comparable y actualizado se usa el % de afiliados al régimen "
        "subsidiado de salud (BDUA, corte vigente), proxy estándar de pobreza e informalidad. Para el contexto "
        "nacional de pobreza monetaria y extrema vea la pestaña 🌐.\n"
        "- **Exportaciones agropecuarias**: miles de US$ FOB según departamento de origen; solo años con los 12 "
        "meses reportados.\n"
        "- **Regalías mineras (ANM)**: regalías por minerales (no hidrocarburos) liquidadas por año, en millones "
        "de pesos corrientes; el año en curso es parcial y se excluye por defecto.\n"
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
    "💼 Economía & Pobreza",
    "🗺️ Mapa Interactivo",
    "📈 Series Históricas",
    "🏆 Rankings",
    "📋 Tabla Consolidada",
    "🌐 Indicadores Nacionales",
    "📚 Fuentes Oficiales",
])
modulos = [tab_bienvenida, tab_kpis, tab_economia, tab_mapa, tab_series, tab_rankings, tab_tabla, tab_nacionales, tab_fuentes]
for tab, modulo in zip(tabs, modulos):
    with tab:
        seguro(modulo)

st.markdown('<div class="footer"><div><div class="b">🇨🇴 Observatorio de Analítica Económica y Social por Departamentos</div>'
            '<div class="s">Datos abiertos oficiales: datos.gov.co · DANE · MinSalud · MEN · MinDefensa · ANM · '
            'MinAgricultura · Banco Mundial</div></div>'
            '<div class="s">Construido con Python · Streamlit · Plotly</div></div>', unsafe_allow_html=True)
