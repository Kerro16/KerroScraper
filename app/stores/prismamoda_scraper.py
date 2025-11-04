from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import quote, urljoin
import re

class PrismaModaScraper:
    BASE = "https://www.prismamoda.com"
    SEARCH_URL = BASE + "/"
    PRICE_RE = re.compile(r"\$\s?\d[\d,\.]*")

    def __init__(self, headless: bool = True, max_items: int = 20):
        self.headless = headless
        self.max_items = max_items

    def scrape(self, query: str) -> list:
        results = []
        search_url = f"{self.SEARCH_URL}{quote(query)}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                page = browser.new_page()
                page.set_extra_http_headers({"Accept-Language": "es-ES"})
                try:
                    page.goto(search_url, timeout=30000)
                    page.wait_for_load_state("networkidle", timeout=20000)
                except TimeoutError:
                    pass

                products = page.query_selector_all("div[class*='product'], article[class*='product']")

                for product in products[:self.max_items]:
                    try:
                        a = product.query_selector("a[href]")
                        img = product.query_selector("img")
                        href = a.get_attribute("href") if a else None
                        if href and not href.startswith("http"):
                            href = urljoin(self.BASE, href)
                        img_src = img.get_attribute("src") if img else None

                        name_el = product.query_selector("h2, h3, [class*='name']")
                        name = name_el.inner_text().strip() if name_el else ""

                        price_el = product.query_selector("[class*='price']")
                        price = price_el.inner_text().strip() if price_el else ""
                        if not price:
                            text = product.inner_text()
                            m = self.PRICE_RE.search(text)
                            price = m.group(0).strip() if m else ""

                        if not self.is_relevant(name, query):
                            continue

                        prices_clean = self.extract_prices(price)
                        results.append({
                            "store": "PrismaModa",
                            "name": self.clean_name(name),
                            "price_original": prices_clean["original"],
                            "price_discount": prices_clean["discount"],
                            "url": href or "",
                            "image": img_src or ""
                        })
                    except Exception as e:
                        results.append({"store": "PrismaModa", "error": str(e)})
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        return results

    def clean_name(self, raw: str) -> str:
        lines = raw.split("\n")
        filtered = [line.strip() for line in lines if not re.search(r"Agregar al carrito|\$\d", line)]
        return " ".join(filtered)

    def extract_prices(self, raw: str) -> dict:
        matches = re.findall(r"\$\s?\d[\d,\.]*", raw)
        return {
            "original": matches[0] if matches else "",
            "discount": matches[1] if len(matches) > 1 else ""
        }

    def is_relevant(self, name: str, query: str) -> bool:
        query_words = query.lower().split()
        name_lower = name.lower()
        return all(word in name_lower for word in query_words)