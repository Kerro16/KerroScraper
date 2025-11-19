from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import re
from typing import List, Dict


class WalmartScraper:
    BASE = "https://www.walmart.com.sv"

    # Mapeo completo de sucursales
    STORES = {
        "vm_rural": "walmartsvwm99991",
        "constitucion": "walmartsvwm4132",
        "bulevard_ejercito": "walmartsvwm539",
        "escalon": "walmartsvwm4382",
        "santa_ana": "walmartsvwm825",
        "santa_elena": "walmartsvwm775",
        "san_miguel": "walmartsvwm4411"
    }

    def __init__(self, headless: bool = True, max_items: int = 20):
        self.headless = headless
        self.max_items = max_items

    def scrape(self, query: str) -> List[Dict]:
        """
        Busca en TODAS las sucursales y consolida resultados únicos
        con información de disponibilidad por tienda.
        """
        all_products = {}  # {product_key: product_data}

        for store_name, store_id in self.STORES.items():
            print(f"\n{'='*60}")
            print(f"🏪 Buscando en: {store_name.replace('_', ' ').title()}")
            print(f"{'='*60}")

            results = self._scrape_single_store(query, store_id, store_name)

            for product in results:
                # Crear clave única basada en nombre normalizado
                product_key = self._normalize_product_name(product["name"])

                if product_key in all_products:
                    # Producto ya existe, agregar sucursal a la lista
                    all_products[product_key]["available_stores"].append(store_name)

                    # Actualizar precio si es mejor en esta sucursal
                    if product["price_discount"]:
                        existing_discount = all_products[product_key]["price_discount"]
                        if not existing_discount or self._compare_prices(product["price_discount"], existing_discount) < 0:
                            all_products[product_key]["price_discount"] = product["price_discount"]
                            all_products[product_key]["best_price_store"] = store_name.replace("_", " ").title()
                else:
                    # Nuevo producto
                    product["available_stores"] = [store_name]
                    product["best_price_store"] = store_name.replace("_", " ").title()
                    all_products[product_key] = product

        # Convertir a lista y formatear nombres de sucursales
        final_results = []
        for product in all_products.values():
            # Formatear nombres de sucursales
            stores_formatted = [s.replace("_", " ").title() for s in product["available_stores"]]
            product["available_stores"] = stores_formatted
            product["stores_count"] = len(stores_formatted)
            final_results.append(product)

        # Ordenar por disponibilidad (más sucursales primero)
        final_results.sort(key=lambda x: x["stores_count"], reverse=True)

        print(f"\n{'='*60}")
        print(f"📊 RESUMEN FINAL")
        print(f"{'='*60}")
        print(f"✅ Total productos únicos: {len(final_results)}")
        print(f"🏪 Sucursales consultadas: {len(self.STORES)}")

        return final_results

    def _scrape_single_store(self, query: str, store_id: str, store_name: str) -> List[Dict]:
        """Método interno: scraping de una sola sucursal"""
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                page = browser.new_page()
                page.set_viewport_size({"width": 1920, "height": 1080})
                page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "es-SV,es;q=0.9"
                })

                print(f"⚙️ Configurando sucursal: {store_id}")
                page.goto(self.BASE, wait_until="domcontentloaded", timeout=30000)

                page.evaluate(f"""
                    localStorage.setItem('verifySelectedSeller', '{store_id}');
                """)

                time.sleep(2)

                search_url = f"{self.BASE}/{query}"
                print(f"🔍 Navegando a búsqueda...")

                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except PlaywrightTimeoutError:
                        pass

                    time.sleep(5)

                    for i in range(5):
                        page.evaluate("window.scrollBy(0, 800)")
                        time.sleep(1.5)

                except PlaywrightTimeoutError:
                    return []

                try:
                    page.wait_for_selector(
                        ".vtex-search-result-3-x-galleryItem section",
                        timeout=15000,
                        state="visible"
                    )
                except PlaywrightTimeoutError:
                    pass

                products = page.query_selector_all(".vtex-search-result-3-x-galleryItem section")
                print(f"📦 Productos encontrados: {len(products)}")

                if len(products) == 0:
                    return []

                for idx, product in enumerate(products[:self.max_items]):
                    try:
                        all_buttons = product.query_selector_all("button")
                        is_out_of_stock = False

                        for btn in all_buttons:
                            text = btn.inner_text().strip().lower()
                            if text and any(word in text for word in ["agregar", "agotado", "out of stock", "sin stock", "añadir", "comprar"]):
                                if any(word in text for word in ["agotado", "out of stock", "sin stock", "no disponible"]):
                                    is_out_of_stock = True
                                break

                        if is_out_of_stock:
                            continue

                        href = None
                        link_elem = product.query_selector("a")
                        if link_elem:
                            href = link_elem.get_attribute("href")
                            if href and not href.startswith("http"):
                                href = self.BASE + href

                        if not href:
                            continue

                        img_src = None
                        img_elem = product.query_selector("img")
                        if img_elem:
                            img_src = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")

                        name = None
                        if link_elem:
                            name = link_elem.get_attribute("aria-label")

                        if name:
                            prefixes = ["View product details for ", "Ver detalles del producto "]
                            for prefix in prefixes:
                                if name.startswith(prefix):
                                    name = name[len(prefix):]
                                    break

                        if not name or len(name) < 5:
                            for sel in ["span.vtex-product-summary-2-x-productBrand", "span[class*='productName']", "h3", "h2"]:
                                elem = product.query_selector(sel)
                                if elem:
                                    text = elem.inner_text().strip()
                                    if text and len(text) > 5 and "$" not in text:
                                        name = text
                                        break

                        if not name:
                            continue

                        price_text = product.inner_text()
                        prices = re.findall(r'\$[\d,]+\.?\d*', price_text)

                        unique_prices = []
                        for p in prices:
                            if p not in unique_prices:
                                unique_prices.append(p)

                        original_price = ""
                        discount_price = ""

                        if len(unique_prices) >= 2:
                            original_price = unique_prices[0]
                            discount_price = unique_prices[1]
                        elif len(unique_prices) == 1:
                            original_price = unique_prices[0]

                        if not original_price and not discount_price:
                            continue

                        if not self.is_relevant(name, query):
                            continue

                        results.append({
                            "store": "Walmart",
                            "name": name,
                            "price_original": original_price,
                            "price_discount": discount_price,
                            "url": href,
                            "image": img_src or ""
                        })

                    except Exception as e:
                        print(f"❌ Error en producto {idx}: {str(e)}")
                        continue

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        print(f"✅ Productos válidos: {len(results)}")
        return results

    def _normalize_product_name(self, name: str) -> str:
        """
        Normaliza nombre de producto para consolidación.
        Elimina variaciones menores que no cambian el producto real.
        """
        # Convertir a minúsculas
        normalized = name.lower()

        # Eliminar caracteres especiales excepto números y letras
        normalized = re.sub(r'[^\w\s]', '', normalized)

        # Eliminar espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized)

        # Eliminar espacios al inicio/final
        normalized = normalized.strip()

        return normalized

    def _compare_prices(self, price1: str, price2: str) -> int:
        """
        Compara dos precios en formato $X,XXX.XX
        Retorna: -1 si price1 < price2, 0 si iguales, 1 si price1 > price2
        """
        try:
            # Eliminar $ y comas, convertir a float
            val1 = float(price1.replace('$', '').replace(',', ''))
            val2 = float(price2.replace('$', '').replace(',', ''))

            if val1 < val2:
                return -1
            elif val1 > val2:
                return 1
            else:
                return 0
        except:
            return 0

    def is_relevant(self, name: str, query: str) -> bool:
        query_words = query.lower().split()
        name_lower = name.lower()
        matches = sum(1 for word in query_words if word in name_lower)
        return matches >= len(query_words) * 0.5