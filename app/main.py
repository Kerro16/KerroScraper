from fastapi import FastAPI, Depends, Query
from app.auth import verify_token

from app.stores.siman_scraper import SimanScraper
from app.stores.curacao_scraper import CuracaoScraper
from app.stores.walmart_scraper import WalmartScraper
from app.stores.prismamoda_scraper import PrismaModaScraper
from app.stores.superselectos_scraper import SelectosScraper



app = FastAPI()

@app.get("/scrape/siman")
def scrape_siman(query: str = Query(...), username: str = Depends(verify_token)):
    scraper = SimanScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}

@app.get("/scrape/curacao")
def scrape_curacao(query: str = Query(...), username: str = Depends(verify_token)):
    scraper = CuracaoScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}

@app.get("/scrape/walmart")
def scrape_walmart(query: str = Query(...), username: str = Depends(verify_token)):
    scraper = WalmartScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}

@app.get("/scrape/prismamoda")
def scrape_prismamoda(query: str = Query(...), username: str = Depends(verify_token)):
    scraper = PrismaModaScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}

@app.get("/scrape/selectos")
def scrape_selectos(query: str = Query(...), username: str = Depends(verify_token)):
    scraper = SelectosScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}

@app.get("/scrape/vidri")
def scrape_vidri(query: str = Query(...), username: str = Depends(verify_token)):
    from app.stores.vidri_scraper import VidriScraper
    scraper = VidriScraper()
    results = scraper.scrape(query)
    return {"user": username, "results": results}