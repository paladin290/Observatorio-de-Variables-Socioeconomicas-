# Observatorio de Analítica Económica y Social por Departamentos en Colombia

Aplicación Streamlit de nivel **Think Tank internacional** para el análisis socioeconómico territorial de Colombia (32 departamentos + Bogotá D.C.).

## Características principales

- **Dataset sintético maestro** (2010-2024): 33 entidades territoriales × 15 años = 495 observaciones.
- **6 indicadores clave** con ficha técnica completa (definición, impacto y fuente oficial):
  - PIB Departamental
  - Tasa de Homicidios
  - Inversión Pública DNP (TerriData)
  - Índice de Pobreza Multidimensional (IPM)
  - Tasa de Desempleo
  - Cobertura Neta Educación Media
- **Imputación automática** de ~3 % de valores nulos mediante interpolación lineal intragrupo.
- **Benchmarking en tiempo real** vs. promedio nacional con semaforización (▲/▼/≈).
- **Mapa coroplético**, series temporales, ranking departamental y descarga CSV.
- **Glosario metodológico** integrado.
- Diseño UI/UX con paleta Think Tank (`#0F172A`, `#2563EB`, `#0D9488`).

## Requisitos

- Python 3.9+
- Dependencias listadas en `requirements.txt`

## Instalación rápida

```bash
# Clonar o descargar el repositorio
cd observatorio-colombia

# Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en `http://localhost:8501`.

## Estructura del proyecto

```
.
├── app.py              # Aplicación principal (todo el código modular)
├── requirements.txt    # Dependencias
└── README.md           # Este archivo
```

## Metodología de datos

| Aspecto                    | Descripción                                                                 |
|---------------------------|-----------------------------------------------------------------------------|
| Periodo                   | 2010 – 2024                                                                 |
| Entidades                 | 32 departamentos + Bogotá D.C.                                              |
| Nulos introducidos        | ~3 % aleatorios                                                             |
| Imputación                | `groupby('departamento').interpolate('linear').bfill().ffill()`             |
| Semilla                   | 42 (reproducible)                                                           |
| Benchmarking              | Diferencia porcentual vs. promedio nacional del mismo año                   |
| Semaforización            | Según orientación de la variable (`mejor_cuando`: alto / bajo)              |

## Notas importantes

- Los datos son **sintéticos** pero diseñados para reflejar heterogeneidad estructural realista entre departamentos colombianos.
- El GeoJSON se descarga de fuentes públicas; si falla la red se utiliza un fallback local de polígonos aproximados.
- Todo el metadato de variables vive en el diccionario `METADATA_VARIABLES` y se reutiliza en tooltips, glosario y formatos.

## Licencia

Uso libre para fines académicos, de investigación y demostración.
```
