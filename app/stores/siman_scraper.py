# app/stores/siman_scraper.py
from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import quote, urljoin
import re

class SimanScraper:
    BASE = "https://sv.siman.com"
    SELECTORS = [".ais-Hits-list .ais-Hits-item"]
    PRICE_RE = re.compile(r"(?:\$|USD|C\$)?\s?\d[\d.,]*")

    def __init__(self, headless: bool = True, max_items: int = 20):
        self.headless = headless
        self.max_items = max_items

    def scrape(self, query: str) -> list:
        results = []
        search_url = f"{self.BASE}/search?_q={quote(query)}"

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

                products = []
                used_selector = None
                for sel in self.SELECTORS:
                    found = page.query_selector_all(sel)
                    if found and len(found) > 0:
                        products = found
                        used_selector = sel
                        break

                if not products:
                    products = page.query_selector_all(".ais-Hits-item, .vtex-search-result-3-x-resultItem") or []
                    used_selector = used_selector or "(fallback)"

                for product in products[:self.max_items]:
                    try:
                        a = product.query_selector("a[href]")
                        img = product.query_selector("img")
                        href = a.get_attribute("href") if a else None
                        if href and not href.startswith("http"):
                            href = urljoin(self.BASE, href)
                        img_src = img.get_attribute("src") if img else None

                        name_el = product.query_selector("[class*='Name'], [class*='name'], [class*='searchProductsItemName'], h2, h3, a")
                        name = None
                        if name_el:
                            try:
                                name = name_el.inner_text().strip()
                            except Exception:
                                name = None
                        if not name and a:
                            try:
                                name = a.inner_text().strip()
                            except Exception:
                                name = None
                        if not name:
                            try:
                                tmp = product.inner_text().strip()
                                name = " ".join(tmp.split())[:200]
                            except Exception:
                                name = ""

                        price_el = product.query_selector("[class*='Price'], [class*='price'], [class*='searchProductsItemPrice']")
                        price = None
                        if price_el:
                            try:
                                price = price_el.inner_text().strip()
                            except Exception:
                                price = None
                        if not price:
                            try:
                                text = product.inner_text()
                                m = self.PRICE_RE.search(text)
                                price = m.group(0).strip() if m else ""
                            except Exception:
                                price = ""

                        if not self.is_relevant(name, query):
                            continue

                        prices_clean = self.extract_prices(price or "")
                        results.append({
                            "store": "Simán",
                            "name": self.clean_name(name),
                            "price_original": prices_clean["original"],
                            "price_discount": prices_clean["discount"],
                            "url": href or "",
                            "image": img_src or ""
                        })
                    except Exception as e:
                        results.append({"store": "Simán", "error": str(e)})
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        print("Selector usado:", used_selector, "items:", len(results))
        return results

    def clean_name(self, raw: str) -> str:
        lines = raw.split("\n")
        filtered = [line.strip() for line in lines if not re.search(r"Vendido por|Agregar al carrito|\$\d", line)]
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