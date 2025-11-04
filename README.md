 # KerroScraper
 
 Breve descripción
 \- Scraper en Python para tiendas (ej. Simán) que usa Playwright y BeautifulSoup. Contiene un servicio ejecutable vía `uvicorn`.
 
 Requisitos
 \- `Python 3.9+`  
 \- `docker` \+ `docker-compose` (opcional para contenedores)  
 \- Paquetes listados en `requirements.txt`
 
 Instalación local
 \- Crear y activar un entorno virtual:
     python -m venv .venv
     .venv\Scripts\activate
 \- Instalar dependencias:
     pip install -r requirements.txt
 \- Instalar navegadores de Playwright (si no usa la imagen Docker que ya los incluye):
     python -m playwright install
 
 Ejecución local
 \- Levantar la API (modo desarrollo):
     uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
 \- Ejecutar un script de prueba:
     python app/test_siman_scrapper.py
 
 Ejecución con Docker
 \- Construir y levantar con `docker-compose`:
     docker-compose build
     docker-compose up --build
 \- El servicio expone el puerto `8000` (configurable en `docker-compose.yml`). La imagen base recomendada incluye Playwright y navegadores, por lo que no se requieren pasos adicionales dentro del contenedor.
 
 Archivos relevantes
 \- `Dockerfile` \- imagen para despliegue con Playwright.  
 \- `docker-compose.yml` \- orquesta el servicio `web`.  
 \- `requirements.txt` \- dependencias Python.

 Notas
 \- En desarrollo se monta el volumen en el contenedor para hot-reload; en producción quitar el volumen.  
 \- Asegurarse de no incluir archivos sensibles en `.env` ni en la imagen final.
