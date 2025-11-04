from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import quote, urljoin
import re

class SelectosScraper:
    BASE = "https://www.superselectos.com"
    SEARCH_URL = BASE + "/products?keyword="
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
                    page.wait_for_timeout(5000)
                except TimeoutError:
                    pass

                products = page.locator("li.item-producto")
                count = products.count()
                print("Productos encontrados:", count)

                for i in range(min(count, self.max_items)):
                    product = products.nth(i)
                    print(f"Procesando producto {i+1}/{count}")
                    try:
                        name = ""
                        name_locator = product.locator("h5.prod-nombre a")
                        if name_locator.count() > 0:
                            name = name_locator.first.inner_text().strip()
                        print("Nombre extraído:", name)

                        a = product.locator("a[href]")
                        href = a.first.get_attribute("href") if a.count() > 0 else ""
                        if href and not href.startswith("http"):
                            href = urljoin(self.BASE, href)

                        img = product.locator("img")
                        img_src = img.first.get_attribute("src") if img.count() > 0 else ""

                        price_el = product.locator("[class*='price']")
                        price = price_el.first.inner_text().strip() if price_el.count() > 0 else ""
                        if not price:
                            text = product.inner_text()
                            m = self.PRICE_RE.search(text)
                            price = m.group(0).strip() if m else ""

                        if not self.is_relevant(name, query):
                            print("Producto descartado por irrelevancia")
                            continue

                        prices_clean = self.extract_prices(price)
                        results.append({
                            "store": "Super Selectos",
                            "name": self.clean_name(name),
                            "price_original": prices_clean["original"],
                            "price_discount": prices_clean["discount"],
                            "url": href or "",
                            "image": img_src or ""
                        })
                        print("Producto agregado:", name)
                    except Exception as e:
                        print("Error en producto:", str(e))
                        results.append({"store": "Super Selectos", "error": str(e)})
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
        matches = sum(1 for word in query_words if word in name_lower)
        return matches >= max(1, len(query_words) // 2)