# Observatorio de Analítica Económica y Social (Colombia)

Aplicación Streamlit con **datos reales** del Portal Nacional de Datos Abiertos (`datos.gov.co`).  
**No utiliza series sintéticas ni cifras inventadas.**

## Indicadores con fuente abierta cargada

| Variable | Dataset | ID |
|----------|---------|-----|
| PIB departamental (suma de actividades, precios corrientes) | PIB Departamental con proyección | `kgyi-qc7j` |
| Homicidios (conteo de víctimas por año y departamento) | HOMICIDIO (MinDefensa) | `m8fd-ahd9` |
| Cobertura neta educación media (%) | Estadísticas MEN por ETC | `sras-4t5p` |

## Indicadores **no** inventados (aparecen como “No disponible”)

- **IPM**: anexos departamentales DANE (XLS), sin API SODA histórica completa.
- **Tasa de desempleo**: GEIH / boletines departamentales DANE (cobertura parcial; anexos XLS).
- **Inversión pública DNP agregada**: TerriData / Mapa Inversiones a nivel proyecto (BPIN), sin serie anual departamental estandarizada en la API usada aquí.

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requiere conexión a internet la primera vez (descarga desde datos.gov.co; resultados en caché de Streamlit).

## Principios

1. Si no hay fuente abierta confiable → `NaN` / “No disponible”.
2. Cada KPI muestra su fuente.
3. El promedio nacional se calcula solo con departamentos que tienen dato (no se imputa).
