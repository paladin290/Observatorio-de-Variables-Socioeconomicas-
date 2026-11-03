# Observatorio de Analítica Económica y Social (Colombia)

Streamlit con **datos oficiales reales** (sin series sintéticas).

## Indicadores cargados

| Variable | Fuente | Cobertura |
|----------|--------|-----------|
| PIB departamental | datos.gov.co `kgyi-qc7j` | Suma de actividades a precios corrientes |
| Homicidios (conteo) | MinDefensa `m8fd-ahd9` | Víctimas por depto-año |
| Cobertura neta media | MEN `sras-4t5p` | ETC departamentales |
| **IPM %** | Anexo DANE `anex-PMultidimensional-Departamental-2025.xlsx` | 33 entidades, 2018–2025 (Total) |
| **Tasa de desocupación** | Anexo DANE `anex-GEIHDepartamentos-2025.xls` | 23 departamentos, serie anual |
| Inversión DNP agregada | — | No hay serie anual departamental estandarizada en API abierta usable |

## Instalación

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requiere internet en la primera carga (caché de Streamlit después).

## Principios

1. Si no hay fuente abierta confiable → `NaN` / “No disponible”.
2. Cada KPI muestra su fuente oficial.
3. Promedio nacional solo con departamentos que tienen dato.
