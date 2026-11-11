# 🇨🇴 Observatorio de Analítica Económica y Social por Departamentos – Colombia

Plataforma interactiva en **Streamlit** con indicadores oficiales de economía, pobreza y protección social, educación, demografía y seguridad para los 32 departamentos y Bogotá D.C. Incluye benchmarking regional, mapas, series históricas y herramientas econométricas.

## 📁 Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `app.py` | Aplicación Streamlit completa |
| `requirements.txt` | Dependencias de Python |
| `README.md` | Este instructivo |

## 🏛️ Fuentes de datos

Todos los datos son **reales y se consultan en vivo**, sin datos sintéticos.

### Economía
- **DANE** – PIB departamental por actividad económica, 2005–2023 (base 2015) · [kgyi-qc7j](https://www.datos.gov.co/d/kgyi-qc7j)
- **ANM** – Regalías mineras pagadas por departamento · [r85m-vv6c](https://www.datos.gov.co/d/r85m-vv6c)
- **MinAgricultura** – Exportaciones agropecuarias (miles US$ FOB) · [5fct-ib9u](https://www.datos.gov.co/d/5fct-ib9u)

### Pobreza y protección social
- **MinSalud** – BDUA: afiliados a los regímenes subsidiado y contributivo · [d7a5-cnra](https://www.datos.gov.co/d/d7a5-cnra) y [tq4m-hmg2](https://www.datos.gov.co/d/tq4m-hmg2)

### Educación
- **MEN** – Estadísticas de educación preescolar, básica y media por departamento · [ji8i-4anb](https://www.datos.gov.co/d/ji8i-4anb)

### Seguridad
- **MinDefensa** – Homicidio intencional (Policía Nacional / SIEDCO) · [m8fd-ahd9](https://www.datos.gov.co/d/m8fd-ahd9)

### Contexto nacional
- **Banco Mundial** – World Development Indicators (PIB, inflación, desempleo, pobreza, Gini, IED…) · [data.worldbank.org](https://data.worldbank.org/country/colombia)
- **DANE** – Codificación DIVIPOLA de departamentos

## 💻 Ejecutar en su computador

1. Instale Python 3.10 o superior.
2. Abra una terminal en la carpeta del proyecto y ejecute:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Se abrirá el navegador en `http://localhost:8501`.

## 🚀 Publicar gratis en Streamlit Community Cloud

1. Cree un repositorio en GitHub (público o privado).
2. Suba los tres archivos a la **raíz** del repositorio: `app.py`, `requirements.txt`, `README.md`.
3. Ingrese a [share.streamlit.io](https://share.streamlit.io) e inicie sesión con GitHub.
4. Clic en **Create app** → **Deploy a public app from GitHub**.
5. Seleccione su repositorio, la rama (`main`) y en **Main file path** escriba `app.py`.
6. En **Advanced settings** elija Python 3.11 o 3.12.
7. Clic en **Deploy**. La primera carga tarda 1–3 minutos.

## 🧭 Módulos

| Pestaña | Contenido |
|---|---|
| 🏠 Bienvenida & Guía | Banner, tarjetas de orientación y panel de control rápido |
| 📊 KPIs & Benchmarking | Tarjetas con semáforo vs. promedio nacional o regional |
| 💼 Economía & Pobreza | Estructura productiva, especialización (QL), ciclo económico, pobreza/informalidad, exportaciones agro y regalías |
| 🗺️ Mapa Interactivo | Coroplético con respaldo automático (burbujas → barras) |
| 📈 Series Históricas | Evolución, comparación y tendencia MCO (pendiente, R², TCAC) |
| 🏆 Rankings | Ranking departamental + laboratorio de correlación |
| 📋 Tabla Consolidada | Tabla filtrable y descarga CSV (formato Excel en español) |
| 🌐 Indicadores Nacionales | PIB, inflación, desempleo, pobreza, Gini, IED, exportaciones (Banco Mundial) |
| 📚 Fuentes Oficiales | Estado de conexiones, metodología y glosario |

## 📝 Notas

- Los datos se guardan en caché 6 horas para no saturar las APIs.
- Si una fuente oficial no responde, el módulo lo informa y el resto sigue funcionando.
- La pobreza monetaria y multidimensional departamental del DANE solo se publica en anexos Excel sin API estable; por eso se usa como proxy el **% de afiliados al régimen subsidiado de salud (BDUA)**. La pobreza nacional sí viene del Banco Mundial.
- Homicidios se presenta como conteo de víctimas; el año en curso (parcial) se excluye por defecto y puede activarse en la barra lateral.
