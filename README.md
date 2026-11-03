# Observatorio de Analítica Económica y Social por Departamentos en Colombia

Aplicación Streamlit con **datos oficiales reales** (sin series sintéticas).

## Indicadores territoriales

| Variable | Fuente | Cobertura |
|----------|--------|-----------|
| PIB departamental | DANE `anex-PIBDep-TotalDep-2025pr.xlsx` | 2005–2025pr, precios corrientes |
| Homicidios (conteo) | MinDefensa · datos.gov.co `m8fd-ahd9` | Víctimas por depto-año |
| Cobertura neta media | MEN · `sras-4t5p` + archivo Cobertura 2025 | ETC departamentales hasta 2025 |
| IPM % | DANE `anex-PMultidimensional-Departamental-2025.xlsx` | 33 entidades, 2018–2025 |
| Tasa de desocupación | DANE `anex-GEIHDepartamentos-2025.xls` | 23 departamentos, serie anual |
| Inversión DNP | — | Sin serie anual departamental estandarizada abierta |

## Indicadores nacionales (pestaña 🌐 Nacional)

| Variable | Fuente |
|----------|--------|
| Inflación anual IPC | DANE anexo índices IPC (nacional; no hay IPC departamental oficial) |
| TRM promedio anual | Superfinanciera · datos.gov.co `32sa-8pi3` |
| Tasa de interés real | Banco Mundial `FR.INR.RINR` (compilación BanRep/FMI) |
| Balanza cuenta corriente | Banco Mundial `BN.CAB.XOKA.CD` |

> **2026 anual departamental** de PIB, IPM, desempleo y cobertura aún no está publicado por DANE/MEN. No se inventan cifras.

## UI / UX

- Paleta ejecutiva con variables CSS (`--slate-*`, `--blue-600`, `--teal-600`)
- Hero con gradiente radial + chips
- KPI cards con hover y semáforo
- Sidebar oscura / main claro con contraste AA en selectores y sliders
- Tabs, métricas y charts con bordes suaves y sombra ligera

## UI / UX

- Paleta ejecutiva (slate / azul institucional / teal)
- Bienvenida con guía interactiva
- KPIs con semaforización vs promedio
- Mapa coroplético con **fallback automático a barras** si el GeoJSON falla
- Controles sidebar con contraste legible

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requiere internet en la primera carga (caché de Streamlit después). La primera descarga del archivo MEN de cobertura (~15 MB) puede tardar.

## Principios

1. Si no hay fuente abierta confiable → `NaN` / “No disponible”.
2. Cada KPI muestra su fuente oficial.
3. Promedios solo con departamentos que tienen dato.
