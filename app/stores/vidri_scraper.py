import re
from typing import List, Dict, Optional
from urllib.parse import quote, urljoin
from playwright.sync_api import sync_playwright, Page

class VidriScraper:
    BASE = "https://www.vidri.com.sv"
    SEARCH_PATTERNS = [
        "/#464e/fullscreen/m=and&q={q}",
        "/#q={q}"
    ]
    API_PATH = "/api/catalog_system/pub/products/search/?ft={q}"
    PRICE_RE = re.compile(r"\$\s?\d[\d\.,]*")
    OLD_PRICE_RE = re.compile(r"Antes:\s*(\$\s?\d[\d\.,]*)", re.IGNORECASE)
    STOCK_RE = re.compile(r"Queda\(n\)\s+(\d+)", re.IGNORECASE)
    PRODUCT_SELECTORS = [
        ".vtex-search-result-3-x-galleryItem",
        ".producto", ".producto-item", ".product-card",
        "div[class*='product-summary']", "article[class*='product']",
        "li[class*='product']", "div[id*='product']",
        "[data-product-id]", "[data-product]"
    ]
    TITLE_SELECTORS = [
        ".vtex-product-summary-2-x-productBrand",
        ".vtex-product-summary-2-x-productName",
        ".title", ".name", ".nombre", ".product-name",
        "h2", "h3"
    ]
    PRICE_SELECTORS = [
        ".vtex-product-price-1-x-sellingPrice",
        ".vtex-store-components-3-x-sellingPrice",
        ".precio", ".price", ".product-price",
        ".amount", ".sale-price", "[data-price]"
    ]

    EXCLUDE_PREFIXES = (
        "Productos similares",
        "Válido hasta",
        "Antes:",
        "AGREGAR",
        "Modelo #",
        "Queda",
    )

    def __init__(self,
                 headless: bool = True,
                 max_items: int = 20,
                 timeout: int = 30000,
                 include_categories: bool = False,
                 debug_html: bool = False):
        self.headless = headless
        self.max_items = max_items
        self.timeout = timeout
        self.include_categories = include_categories
        self.debug_html = debug_html
        self.last_html: Optional[str] = None

    def _clean(self, t: Optional[str]) -> str:
        return (t or "").strip()

    def _refine_title_block(self, raw: str) -> Dict[str, Optional[str]]:
        lines = [self._clean(l) for l in raw.splitlines() if self._clean(l)]
        model = None
        brand = None
        title = None
        stock = None
        # Detect modelo
        for l in lines:
            if l.lower().startswith("modelo #"):
                model = l.split("#", 1)[-1].strip()
        # Detect stock
        for l in lines:
            m = self.STOCK_RE.search(l)
            if m:
                stock = m.group(1)
        # Marca: línea en mayúsculas (heurística) antes del título
        for l in lines:
            if l.isupper() and len(l.split()) <= 3 and l not in ("AGREGAR",) and not l.startswith("MODELO"):
                brand = l
        filtered = []
        for l in lines:
            if any(l.startswith(pref) for pref in self.EXCLUDE_PREFIXES):
                continue
            if l.isdigit():
                continue
            if self.PRICE_RE.search(l):
                continue
            if self.OLD_PRICE_RE.search(l):
                continue
            if l == brand or (model and model in l):
                continue
            filtered.append(l)
        if filtered:
            # Última línea suele ser el nombre cuando hay muchas
            title = filtered[-1] if len(filtered) > 1 else filtered[0]
        return {
            "title": title,
            "model": model,
            "brand": brand,
            "stock": stock
        }

    def _match_price(self, txt: str) -> Optional[str]:
        m = self.PRICE_RE.search(txt)
        return m.group(0) if m else None

    def _extract_prices(self, raw: str) -> (Optional[str], Optional[str]):
        # Precio actual: primero no precedido por "Antes:"
        prices = self.PRICE_RE.findall(raw)
        old = None
        m_old = self.OLD_PRICE_RE.search(raw)
        if m_old:
            old = m_old.group(1)
        current = None
        if prices:
            # Si hay old, tomar el primer distinto a old
            if old:
                for p in prices:
                    if p != old:
                        current = p
                        break
                if not current:
                    current = prices[0]
            else:
                current = prices[0]
        return current, old

    def _extract_title(self, root) -> Dict[str, Optional[str]]:
        for sel in self.TITLE_SELECTORS:
            el = root.query_selector(sel)
            if el:
                block = self._refine_title_block(el.inner_text())
                if block["title"]:
                    return block
        a = root.query_selector("a[href]")
        if a:
            block = self._refine_title_block(a.inner_text())
            if block["title"]:
                return block
        return self._refine_title_block(root.inner_text())

    def _extract_structured(self, root, query: str) -> Optional[Dict[str, Optional[str]]]:
        block = self._extract_title(root)
        title = block["title"]
        if not title:
            return None
        raw = root.inner_text()
        price, old_price = self._extract_prices(raw)
        href_el = root.query_selector("a[href]") or (root if root.get_attribute("href") else None)
        if not href_el:
            return None
        href = href_el.get_attribute("href") or ""
        if not href:
            return None
        full = urljoin(self.BASE, href)
        if not self._is_product(href, title, price, query):
            return None
        return {
            "title": title,
            "url": full,
            "price": price,
            "old_price": old_price,
            "model": block["model"],
            "brand": block["brand"],
            "stock": block["stock"]
        }

    def _is_product(self, href: str, title: str, price: Optional[str], query: str) -> bool:
        h = href.lower()
        if price:
            return True
        if query.lower() in title.lower():
            return True
        if "/p" in h or "/producto" in h:
            return True
        if self.include_categories and ("/catalogo/" in h or "/promocion/" in h):
            return True
        return False

    def _wait_dom_growth(self, page: Page, attempts: int = 5, delay: int = 600):
        prev = 0
        for _ in range(attempts):
            count = page.evaluate("document.getElementsByTagName('*').length")
            if count > prev:
                prev = count
            page.wait_for_timeout(delay)

    def _scroll(self, page: Page, limit: int = 6000, step: int = 800):
        for y in range(0, limit, step):
            page.evaluate(f"window.scrollTo(0, {y});")
            page.wait_for_timeout(120)

    def _collect_nodes(self, page: Page, query: str) -> List[Dict[str, Optional[str]]]:
        out: List[Dict[str, Optional[str]]] = []
        seen = set()
        nodes = []
        for sel in self.PRODUCT_SELECTORS:
            nodes.extend(page.query_selector_all(sel))
        if not nodes:
            nodes = page.query_selector_all("a[href]")
        for node in nodes:
            if len(out) >= self.max_items:
                break
            item = self._extract_structured(node, query)
            if not item:
                continue
            if item["url"] in seen:
                continue
            out.append(item)
            seen.add(item["url"])
        return out

    def _api_search(self, context, query: str) -> List[Dict[str, Optional[str]]]:
        out: List[Dict[str, Optional[str]]] = []
        url = urljoin(self.BASE, self.API_PATH.format(q=quote(query)))
        try:
            resp = context.request.get(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}, timeout=10000)
            if not resp.ok:
                return out
            data = resp.json()
            if isinstance(data, list):
                for prod in data:
                    if len(out) >= self.max_items:
                        break
                    name = prod.get("productName") or prod.get("productTitle") or ""
                    link_text = prod.get("linkText") or ""
                    rel = f"/{link_text}/p" if link_text else ""
                    full = urljoin(self.BASE, rel)
                    price = None
                    items = prod.get("items") or []
                    if items:
                        sellers = items[0].get("sellers") or []
                        if sellers:
                            offer = sellers[0].get("commertialOffer") or {}
                            val = offer.get("Price")
                            if val:
                                price = f"${val}"
                    if name:
                        out.append({"title": name, "url": full, "price": price})
        except Exception:
            pass
        return out

    def _manual_search(self, page: Page, query: str):
        selectors = [
            "input[type='search']",
            "input[placeholder*='Buscar']",
            ".vtex-store-components-3-x-searchBarInnerContainer input",
            "form input[type='text']"
        ]
        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                try:
                    el.click()
                    el.fill("")
                    el.type(query)
                    el.press("Enter")
                    return
                except Exception:
                    continue

    def scrape(self, query: str) -> List[Dict[str, Optional[str]]]:
        results: List[Dict[str, Optional[str]]] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(extra_http_headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "es-ES,es;q=0.9"
                })
                api = self._api_search(context, query)
                if api:
                    browser.close()
                    return api[:self.max_items]

                page = context.new_page()
                for pattern in self.SEARCH_PATTERNS:
                    try:
                        page.goto(self.BASE + pattern.format(q=quote(query)), timeout=self.timeout)
                        self._wait_dom_growth(page)
                        self._scroll(page)
                        partial = self._collect_nodes(page, query)
                        if partial:
                            results.extend(partial)
                            break
                        if self.debug_html:
                            self.last_html = page.content()
                    except Exception:
                        continue

                if not results:
                    try:
                        page.goto(self.BASE, timeout=self.timeout)
                        self._manual_search(page, query)
                        self._wait_dom_growth(page)
                        self._scroll(page)
                        results = self._collect_nodes(page, query)
                        if self.debug_html and not results:
                            self.last_html = page.content()
                    except Exception:
                        pass

                if not results:
                    links = page.query_selector_all("a[href*='/catalogo/'],a[href*='/promocion/']")
                    for a in links:
                        if len(results) >= self.max_items:
                            break
                        href = a.get_attribute("href") or ""
                        full = urljoin(self.BASE, href)
                        title = self._clean(a.inner_text())
                        if title:
                            results.append({"title": title, "url": full, "price": None})

                browser.close()
        except Exception:
            pass
        return results[:self.max_items]