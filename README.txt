OBSERVATORIO DE ANALÍTICA ECONÓMICA Y SOCIAL POR DEPARTAMENTOS – COLOMBIA
=========================================================================

ARCHIVOS DEL PROYECTO
---------------------
  app.py            -> Aplicación Streamlit completa
  requirements.txt  -> Dependencias de Python
  README.txt        -> Este instructivo

FUENTES DE DATOS (100% reales, consultadas en vivo, sin datos sintéticos)
------------------------------------------------------------------------
  * MEN - Estadísticas de educación preescolar, básica y media por departamento
        https://www.datos.gov.co/d/ji8i-4anb
  * MinDefensa - Homicidio intencional (Policía Nacional / SIEDCO)
        https://www.datos.gov.co/d/m8fd-ahd9
  * Banco Mundial - World Development Indicators (contexto macro nacional)
        https://data.worldbank.org/country/colombia
  * DANE - Codificación DIVIPOLA de departamentos

EJECUTAR EN SU COMPUTADOR
-------------------------
  1. Instale Python 3.10 o superior.
  2. Abra una terminal en la carpeta del proyecto y ejecute:
        pip install -r requirements.txt
        streamlit run app.py
  3. Se abrirá el navegador en http://localhost:8501

PUBLICAR GRATIS EN STREAMLIT COMMUNITY CLOUD
--------------------------------------------
  1. Cree un repositorio en GitHub (público o privado).
  2. Suba los tres archivos a la RAÍZ del repositorio:
        app.py, requirements.txt, README.txt
  3. Ingrese a https://share.streamlit.io e inicie sesión con GitHub.
  4. Clic en "Create app" -> "Deploy a public app from GitHub".
  5. Seleccione su repositorio, la rama (main) y en "Main file path" escriba: app.py
  6. En "Advanced settings" elija Python 3.11 o 3.12.
  7. Clic en "Deploy". La primera carga tarda 1–3 minutos.

MÓDULOS
-------
  🏠 Bienvenida & Guía        Banner, tarjetas de orientación y panel de control rápido
  📊 KPIs & Benchmarking      Tarjetas con semáforo vs promedio nacional o regional
  🗺️ Mapa Interactivo         Coroplético con respaldo automático (burbujas -> barras)
  📈 Series Históricas        Evolución, comparación y tendencia MCO (pendiente, R², TCAC)
  🏆 Rankings                 Ranking departamental + laboratorio de correlación
  📋 Tabla Consolidada        Tabla filtrable y descarga CSV (formato Excel en español)
  🌐 Indicadores Nacionales   PIB, inflación, desempleo, Gini y pobreza (Banco Mundial)
  📚 Fuentes Oficiales        Estado de conexiones, metodología y glosario

NOTAS
-----
  * Los datos se guardan en caché 6 horas para no saturar las APIs.
  * Si una fuente oficial no responde, el módulo lo informa y el resto sigue funcionando.
  * Homicidios se presenta como conteo de víctimas; el año en curso (parcial) se excluye
    por defecto y puede activarse en la barra lateral.
