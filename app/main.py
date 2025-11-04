from fastapi import FastAPI, Query
from app.stores.siman_scraper import SimanScraper
from app.stores.curacao_scraper import CuracaoScraper
from app.stores.walmart_scraper import WalmartScraper
from app.stores.prismamoda_scraper import PrismaModaScraper
from app.stores.superselectos_scraper import SelectosScraper


app = FastAPI()

@app.get("/scrape/siman")
def scrape_siman(query: str = Query(..., description="Texto de búsqueda")):
    scraper = SimanScraper()
    results = scraper.scrape(query)
    return {"results": results}


@app.get("/scrape/curacao")
def scrape_curacao(query: str = Query(..., description="Texto de búsqueda")):
    scraper = CuracaoScraper()
    results = scraper.scrape(query)
    return {"results": results}

@app.get("/scrape/walmart")
def scrape_walmart(query: str = Query(..., description="Texto de búsqueda")):
    scraper = WalmartScraper()
    results = scraper.scrape(query)
    return {"results": results}

@app.get("/scrape/prismamoda")
def scrape_prismamoda(query: str = Query(..., description="Texto de búsqueda")):
    scraper = PrismaModaScraper()
    results = scraper.scrape(query)
    return {"results": results}

@app.get("/scrape/selectos")
def scrape_selectos(query: str = Query(..., description="Texto de búsqueda")):
    scraper = SelectosScraper()
    results = scraper.scrape(query)
    return {"results": results}



