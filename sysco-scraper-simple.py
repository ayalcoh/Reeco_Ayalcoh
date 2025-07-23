#!/usr/bin/env python3

import csv
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sysco_scraper.log')
    ]
)

class FinalSyscoScraper:
    def __init__(self, zip_code="97205", fetch_descriptions=False):
        self.zip_code = zip_code
        self.base_url = "https://shop.sysco.com"
        self.products = []
        self.processed_skus = set()
        self.fetch_descriptions = fetch_descriptions  # Control whether to fetch descriptions
        
    def setup_driver(self):
        """Chrome driver setup"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        return webdriver.Chrome(options=options)
    
    def set_location(self, driver):
        """Set Oregon zip code"""
        try:
            wait = WebDriverWait(driver, 3)
            guest_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Guest')]")))
            guest_btn.click()
            time.sleep(1)
        except:
            pass
            
        try:
            zip_input = driver.find_element(By.CSS_SELECTOR, "input[data-id='initial_zipcode_modal_input']")
            zip_input.clear()
            zip_input.send_keys(self.zip_code)
            zip_input.send_keys('\n')
            time.sleep(2)
            logging.info(f"Set location to {self.zip_code}")
        except:
            logging.warning("Could not set location")
    
    def extract_from_listing(self, driver, category_name, category_id):
        """Extract products from listing pages"""
        category_products = []
        consecutive_empty_pages = 0
        max_pages = 100
        
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/app/catalog?BUSINESS_CENTER_ID={category_id}&page={page}"
            driver.get(url)
            
            wait = WebDriverWait(driver, 5)
            time.sleep(1)
            
            page_products = []
            
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/product/"]')))
            except:
                pass
            
            all_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/opco/"][href*="/product/"]')
            
            if not all_links:
                all_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/product/"]')
            
            link_data = []
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    if href:
                        link_data.append((link, href))
                except:
                    continue
            
            for link, href in link_data:
                try:
                    sku = self.extract_sku_from_url(href)
                    if not sku or sku in self.processed_skus:
                        continue
                    
                    product_container = self.find_product_container(link)
                    
                    product = {
                        'category': category_name,
                        'product_name': self.safe_extract_text(product_container, link),
                        'brand_name': self.safe_extract_brand(product_container),
                        'sku': sku,
                        'packaging_info': self.safe_extract_packaging(product_container),
                        'picture_url': self.safe_extract_image_for_product(link, product_container, sku),
                        'description': '',
                        'product_url': href
                    }
                    
                    if product['sku']:
                        self.processed_skus.add(sku)
                        page_products.append(product)
                        
                except Exception as e:
                    continue
            
            if page_products:
                if self.fetch_descriptions and page_products:
                    logging.info(f"{category_name} - Page {page}: Fetching descriptions for up to 3 products...")
                    self.fetch_product_descriptions(driver, page_products)
                    
                    desc_count = sum(1 for p in page_products if p.get('description'))
                    if desc_count > 0:
                        logging.info(f"{category_name} - Page {page}: Got {desc_count} descriptions")
                else:
                    for product in page_products:
                        product.pop('product_url', None)
                
                category_products.extend(page_products)
                consecutive_empty_pages = 0
                logging.info(f"{category_name} - Page {page}: Found {len(page_products)} products (Total: {len(category_products)})")
            else:
                consecutive_empty_pages += 1
                logging.info(f"{category_name} - Page {page}: No products found (empty pages: {consecutive_empty_pages})")
                
                if consecutive_empty_pages >= 3:
                    logging.info(f"{category_name}: Stopping after {consecutive_empty_pages} empty pages")
                    break
                
        return category_products
    
    def find_product_container(self, link):
        """Find the most specific container for a product"""
        try:
            container = link
            for _ in range(5):
                try:
                    parent = container.find_element(By.XPATH, '..')
                    if any(keyword in parent.get_attribute('class').lower() 
                           for keyword in ['product', 'item', 'card', 'tile'] 
                           if parent.get_attribute('class')):
                        return parent
                    container = parent
                except:
                    break
            return container
        except:
            return link
    
    def safe_extract_image_for_product(self, link, container, sku):
        """Extract image URL specific to this product"""
        for search_area in [link, container]:
            try:
                img_selectors = [
                    'img',
                    'img[data-testid*="product"]',
                    'img[class*="product-image"]', 
                    'img[src*="mediacdn"]',
                    'img[data-src*="mediacdn"]'
                ]
                for selector in img_selectors:
                    try:
                        img = search_area.find_element(By.CSS_SELECTOR, selector)
                        src = img.get_attribute('data-src') or img.get_attribute('src')
                        if src and self.is_valid_product_image(src):
                            return src
                    except:
                        continue
            except:
                continue
        return ""
    
    def fetch_product_descriptions(self, driver, products):
        """Fetch descriptions from product detail pages"""
        products_to_fetch = products[:3]
        
        for i, product in enumerate(products_to_fetch):
            try:
                driver.get(product['product_url'])
                
                if "product-details" not in driver.current_url:
                    logging.warning(f"Not on product details page: {driver.current_url}")
                    continue
                
                wait = WebDriverWait(driver, 5)
                time.sleep(2)
                
                description_found = False
                try:
                    desc_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-id='product_description_text']")))
                    time.sleep(1)
                    desc_text = desc_elem.text.strip()
                    if desc_text and desc_text != "Product description is not available" and len(desc_text) > 10:
                        product['description'] = desc_text[:500]
                        description_found = True
                        logging.info(f"✓ Found description for SKU {product['sku']}: {desc_text[:50]}...")
                except Exception as e:
                    pass
                
                if not description_found:
                    fallback_selectors = [
                        "div[class*='product-description']",
                        "[class*='description-text']",
                        "div[class*='description'] p",
                        ".product-details-description",
                        "[data-testid*='description']"
                    ]
                    for selector in fallback_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for elem in elements:
                                text = elem.text.strip()
                                if text and len(text) > 30 and not any(skip in text.lower() for skip in ['sign in', 'add to cart', 'quantity']):
                                    product['description'] = text[:500]
                                    description_found = True
                                    logging.info(f"✓ Found description with {selector} for SKU {product['sku']}: {text[:50]}...")
                                    break
                            if description_found:
                                break
                        except:
                            continue
                
                if not description_found:
                    logging.warning(f"No description found for SKU {product['sku']}")
                
                if not product['brand_name']:
                    try:
                        brand_elem = driver.find_element(By.CSS_SELECTOR, "button[data-id='product_brand_link']")
                        product['brand_name'] = brand_elem.text.strip()
                    except:
                        pass
                
                if not product['packaging_info']:
                    try:
                        pack_elem = driver.find_element(By.CSS_SELECTOR, "div[data-id='pack_size']")
                        product['packaging_info'] = pack_elem.text.strip()
                    except:
                        pass
                
                try:
                    img_elem = driver.find_element(By.CSS_SELECTOR, "img[data-id='main-product-img-v2']")
                    img_src = img_elem.get_attribute('src')
                    if img_src and self.is_valid_product_image(img_src):
                        product['picture_url'] = img_src
                except:
                    try:
                        img_selectors = [
                            "img.product-image", "img[class*='main-image']", "img[alt*='product']",
                            ".product-image-container img", ".image-gallery img", "img[src*='mediacdn']",
                            "img[data-src*='mediacdn']"
                        ]
                        for selector in img_selectors:
                            try:
                                img = driver.find_element(By.CSS_SELECTOR, selector)
                                src = img.get_attribute('data-src') or img.get_attribute('src')
                                if src and self.is_valid_product_image(src):
                                    product['picture_url'] = src
                                    break
                            except:
                                continue
                    except:
                        pass
                        
            except Exception as e:
                logging.warning(f"Error fetching details for {product['sku']}: {e}")
                continue
        
        for product in products:
            product.pop('product_url', None)
    
    def safe_extract_text(self, container, link_element):
        """Extract product name"""
        text = link_element.text.strip()
        if text and len(text) > 5:
            return text
        
        common_selectors = ['h3', 'h4', '[class*="title"]', '[class*="name"]']
        
        for selector in common_selectors:
            try:
                element = container.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text and 5 < len(text) < 200:
                    return text
            except:
                continue
        return "Product Name Not Found"
    
    def safe_extract_brand(self, container):
        """Extract brand name"""
        selectors = ['[class*="brand"]', '[class*="manufacturer"]', 'button[data-id="product_brand_link"]']
        for selector in selectors:
            try:
                element = container.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text and len(text) < 50:
                    return text
            except:
                continue
        return ""
    
    def safe_extract_packaging(self, container):
        """Extract packaging info"""
        packaging_selectors = [
            '[class*="pack"]', '[class*="size"]', '[data-id*="pack"]',
            '[data-testid*="pack"]', '.product-size', '.pack-size'
        ]
        
        for selector in packaging_selectors:
            try:
                element = container.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text and len(text) < 50:
                    if re.search(r'\d+.*(?:CT|CS|EA|LB|OZ|GAL|QT|PT)', text, re.IGNORECASE):
                        return text
            except:
                continue
        
        try:
            text = container.text
            patterns = [
                r'\b\d+[-/\d]*\s*(CT|CS|EA|LB|OZ|GAL|QT|PT)\b',
                r'\b\d+\s*[xX]\s*\d+\s*(CT|CS|EA|LB|OZ)\b',
                r'\b\d+\.\d+\s*(LB|OZ|GAL)\b',
                r'\b\d+/\d+\s*(CT|CS|EA|LB|OZ)\b'
            ]
            
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                all_matches.extend(matches)
            
            if all_matches:
                text_lines = text.split('\n')
                for line in reversed(text_lines[-3:]):
                    for pattern in patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            return match.group(0)
                
                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        return match.group(0)
        except:
            pass
        return ""
    
    def is_valid_product_image(self, src):
        """Check if image URL is valid for a product"""
        if not src or len(src) < 10:
            return False
        
        invalid_keywords = ['placeholder', 'default', 'blank', 'loading', 'error', 'missing']
        if any(keyword in src.lower() for keyword in invalid_keywords):
            return False
        
        valid_indicators = ['mediacdn', 'sysco', '/product/', '/item/', '/sku/', 'rendition']
        if any(indicator in src.lower() for indicator in valid_indicators):
            return True
        
        return src.startswith('https://') and any(ext in src.lower() for ext in ['jpg', 'png', 'jpeg', 'webp'])
    
    def extract_sku_from_url(self, url):
        """Extract SKU from product URL"""
        try:
            match = re.search(r'/product/(\d+)', url)
            if match:
                return match.group(1)
        except:
            pass
        return ""
    
    def scrape(self, category_limit=None):
        """Main scraping method"""
        driver = self.setup_driver()
        
        try:
            driver.get(self.base_url)
            time.sleep(2)
            self.set_location(driver)
            
            categories = [
                ("Produce", "syy_cust_tax_produce"),
                ("Dairy & Eggs", "syy_cust_tax_dairyeggs"),
                ("Meat & Seafood", "syy_cust_tax_meatseafood"),
                ("Bakery & Bread", "syy_cust_tax_bakerybread"),
                ("Beverages", "syy_cust_tax_beverages"),
                ("Canned & Dry", "syy_cust_tax_canneddry"),
                ("Frozen Foods", "syy_cust_tax_frozenfoods"),
                ("Chemicals", "syy_cust_tax_chemicals"),
                ("Disposables", "syy_cust_tax_disposables"),
                ("Equipment & Supplies", "syy_cust_tax_equipmentsupplies"),
                ("Fruit & Vegetables", "syy_cust_tax_fruitvegetables"),
            ]
            
            if category_limit:
                categories = categories[:category_limit]
                logging.info(f"Limited to first {category_limit} categories for testing")
            
            for cat_name, cat_id in categories:
                logging.info(f"\n{'='*50}\nScraping category: {cat_name}\n{'='*50}")
                products = self.extract_from_listing(driver, cat_name, cat_id)
                self.products.extend(products)
                logging.info(f"Category complete. Total products so far: {len(self.products)}")
                self.save_to_csv(f"sysco_products_oregon_temp.csv")
                    
        finally:
            driver.quit()
        return self.products
    
    def save_to_csv(self, filename="sysco_products_oregon.csv"):
        """Save products to CSV"""
        if not self.products:
            logging.error("No products to save")
            return
            
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['category', 'brand_name', 'product_name', 'packaging_info', 
                         'sku', 'picture_url', 'description']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
            
        logging.info(f"Saved {len(self.products)} products to {filename}")
        
        print(f"\n{'='*50}\nSUMMARY: {len(self.products)} products scraped\n{'='*50}")
        
        category_counts = {}
        for p in self.products:
            cat = p['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        for cat, count in sorted(category_counts.items()):
            print(f"{cat}: {count} products")

def main():
    fetch_descriptions = input("Fetch product descriptions? (y/n, default=n): ").lower() == 'y'
    category_limit = None
    
    if fetch_descriptions:
        test_mode = input("Test with just 1 category first? (y/n, default=n): ").lower() == 'y'
        if test_mode:
            category_limit = 1
    
    scraper = FinalSyscoScraper(zip_code="97205", fetch_descriptions=fetch_descriptions)
    
    print("\nSysco Scraper - Final Version")
    print("=============================")
    print(f"Oregon Zip Code: {scraper.zip_code}")
    print(f"Fetch Descriptions: {fetch_descriptions}")
    if category_limit:
        print(f"TEST MODE: Limited to {category_limit} category")
    print("Starting scrape...\n")
    
    start_time = time.time()
    products = scraper.scrape(category_limit=category_limit)
    end_time = time.time()
    
    scraper.save_to_csv()
    
    print(f"\nCompleted in {(end_time - start_time) / 60:.1f} minutes")
    print(f"Total products scraped: {len(products)}")
    
    if products:
        with_desc = sum(1 for p in products if p.get('description'))
        print(f"Products with descriptions: {with_desc} ({with_desc/len(products)*100:.1f}%)")

if __name__ == "__main__":
    main()