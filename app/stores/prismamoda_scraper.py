from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import quote, urljoin
import re

class PrismaModaScraper:
    BASE = "https://www.prismamoda.com"
    PRICE_RE = re.compile(r"\$\s?\d[\d,\.]*")

    def __init__(self, headless: bool = True, max_items: int = 20):
        self.headless = headless
        self.max_items = max_items

    def scrape(self, query: str) -> list:
        results = []
        seen_urls = set()
        search_url = f"{self.BASE}/{quote(query)}"

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
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                    page.wait_for_timeout(4000)
                    for i in range(6):
                        page.evaluate(f"window.scrollTo(0, {i * 600})")
                        page.wait_for_timeout(400)
                except TimeoutError:
                    pass

                try:
                    page.wait_for_selector("a:has(img)", timeout=8000)
                except TimeoutError:
                    pass

                vtex_selectors = [
                    ".vtex-product-summary-2-x-clearLink",
                    "[class*='vtex-product-summary']",
                    ".vtex-search-result-3-x-galleryItem",
                    "[class*='galleryItem']"
                ]

                products = []
                for sel in vtex_selectors:
                    found = page.query_selector_all(sel)
                    if found and len(found) >= 3:
                        products = found
                        break

                if not products:
                    all_links = page.query_selector_all("a[href]")
                    products = [
                        link for link in all_links
                        if link.query_selector("img") and link.get_attribute("href") and (
                            "/producto/" in link.get_attribute("href") or
                            "/product/" in link.get_attribute("href") or
                            "-p-" in link.get_attribute("href"))
                    ]

                if not products:
                    all_links = page.query_selector_all("a[href]")
                    tmp = []
                    for link in all_links:
                        img = link.query_selector("img")
                        href = link.get_attribute("href")
                        if img and href and len(href) > 15 and href.startswith("/"):
                            tmp.append(link)
                    products = tmp

                for product in products[:self.max_items * 2]:
                    try:
                        href = product.get_attribute("href")
                        if not href or href == "#" or len(href) < 5:
                            continue
                        if not href.startswith("http"):
                            href = urljoin(self.BASE, href)
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)

                        name = ""
                        try:
                            raw = product.inner_text().strip()
                            if raw:
                                lines = [l.strip() for l in raw.split("\n") if len(l.strip()) > 5]
                                if lines:
                                    name = lines[0]
                        except:
                            pass
                        if not name or len(name) < 5:
                            name = product.get_attribute("title") or ""
                        if (not name or len(name) < 5):
                            img = product.query_selector("img")
                            if img:
                                name = img.get_attribute("alt") or ""
                        if (not name or len(name) < 5):
                            name = product.get_attribute("aria-label") or ""
                        if not name or len(name) < 3:
                            continue
                        if not self.is_relevant(name, query):
                            continue

                        img_src = ""
                        img = product.query_selector("img")
                        if img:
                            img_src = (img.get_attribute("src") or
                                       img.get_attribute("data-src") or
                                       img.get_attribute("data-lazy-src") or "")

                        price = ""
                        try:
                            parent_text = page.evaluate("""(link) => {
                                let parent = link.parentElement;
                                for (let i = 0; i < 3 && parent; i++) {
                                    if (parent.innerText) return parent.innerText;
                                    parent = parent.parentElement;
                                }
                                return '';
                            }""", product)
                            m = self.PRICE_RE.search(parent_text or "")
                            if m:
                                price = m.group(0)
                        except:
                            pass

                        prices_clean = self.extract_prices(price)
                        results.append({
                            "store": "PrismaModa",
                            "name": self.clean_name(name),
                            "price_original": prices_clean["original"],
                            "price_discount": prices_clean["discount"],
                            "url": href,
                            "image": img_src
                        })

                        if len(results) >= self.max_items:
                            break
                    except:
                        continue
            finally:
                try:
                    browser.close()
                except:
                    pass

        return results

    def clean_name(self, raw: str) -> str:
        lines = raw.split("\n")
        filtered = [l.strip() for l in lines if l.strip() and not re.search(r"Agregar|\$\d|Comprar|Ver|Añadir", l, re.IGNORECASE)]
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
        return any(word in name_lower or name_lower in word for word in query_words)