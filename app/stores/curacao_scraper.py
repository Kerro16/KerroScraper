from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import quote, urljoin
import re

class CuracaoScraper:
    BASE = "https://www.lacuracaonline.com"
    PRICE_RE = re.compile(r"\$\s?\d[\d,\.]*")

    def __init__(self, headless: bool = True, max_items: int = 20):
        self.headless = headless
        self.max_items = max_items

    def scrape(self, query: str) -> list:
        results = []
        seen_urls = set()  # Para evitar duplicados
        search_url = f"{self.BASE}/elsalvador/{quote(query)}"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            try:
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='es-ES',
                    extra_http_headers={'Accept-Language': 'es-ES,es;q=0.9'}
                )

                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)

                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(5000)

                    # Scroll progresivo
                    for i in range(5):
                        page.evaluate(f"window.scrollTo(0, {i * 400})")
                        page.wait_for_timeout(400)

                except TimeoutError:
                    pass

                # Esperar galería VTEX
                try:
                    page.wait_for_selector(".vtex-search-result-3-x-gallery", timeout=10000)
                except TimeoutError:
                    pass

                # Buscar productos con selector heurístico mejorado
                all_divs = page.query_selector_all("div")
                products = [
                    div for div in all_divs
                    if div.query_selector("a[href*='/p']") and div.query_selector("img")
                ][:50]

                print(f"Productos encontrados: {len(products)}")

                for idx, product in enumerate(products[:self.max_items * 2]):  # Procesar más para compensar filtrado
                    try:
                        full_text = ""
                        try:
                            full_text = product.inner_text()
                        except Exception:
                            pass

                        # Filtrar elementos de navegación/UI
                        if any(x in full_text.lower() for x in ["resultados de búsqueda", "filtrar por", "ordenar por"]):
                            continue

                        # URL - debe contener /p/ para ser producto
                        a = product.query_selector("a[href*='/p']")
                        if not a:
                            continue

                        href = a.get_attribute("href")
                        if not href:
                            continue

                        if not href.startswith("http"):
                            href = urljoin(self.BASE, href)

                        # Evitar duplicados por URL
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        # Nombre
                        name = ""
                        name_selectors = [
                            ".vtex-product-summary-2-x-nameContainer",
                            "[class*='nameContainer']",
                            "h3", "h2", "a[href*='/p']"
                        ]
                        for name_sel in name_selectors:
                            name_el = product.query_selector(name_sel)
                            if name_el:
                                try:
                                    name = name_el.inner_text().strip()
                                    if len(name) > 5:
                                        break
                                except Exception:
                                    continue

                        if not name:
                            continue

                        # Validar relevancia
                        if not self.is_relevant(name, query):
                            continue

                        # Imagen
                        img = product.query_selector("img")
                        img_src = ""
                        if img:
                            img_src = img.get_attribute("src") or img.get_attribute("data-src") or ""

                        # Precio
                        price = ""
                        price_selectors = [
                            ".vtex-product-price-1-x-sellingPrice",
                            "[class*='sellingPrice']",
                            "[class*='price']"
                        ]
                        for price_sel in price_selectors:
                            price_el = product.query_selector(price_sel)
                            if price_el:
                                try:
                                    price = price_el.inner_text().strip()
                                    if "$" in price:
                                        break
                                except Exception:
                                    continue

                        if not price:
                            m = self.PRICE_RE.search(full_text)
                            price = m.group(0) if m else ""

                        prices_clean = self.extract_prices(price)
                        results.append({
                            "store": "La Curacao",
                            "name": self.clean_name(name),
                            "price_original": prices_clean["original"],
                            "price_discount": prices_clean["discount"],
                            "url": href,
                            "image": img_src
                        })

                        if len(results) >= self.max_items:
                            break

                    except Exception:
                        continue
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        print(f"Total resultados válidos: {len(results)}")
        return results

    def clean_name(self, raw: str) -> str:
        lines = raw.split("\n")
        filtered = [l.strip() for l in lines if l.strip() and not re.search(r"Vendido por|Agregar|\$\d|Añadir", l)]
        return " ".join(filtered)[:200]

    def extract_prices(self, raw: str) -> dict:
        matches = re.findall(r"\$\s?\d[\d,\.]*", raw)
        return {
            "original": matches[0] if matches else "",
            "discount": matches[1] if len(matches) > 1 else ""
        }

    def is_relevant(self, name: str, query: str) -> bool:
        query_words = query.lower().split()
        name_lower = name.lower()
        return any(word in name_lower for word in query_words)