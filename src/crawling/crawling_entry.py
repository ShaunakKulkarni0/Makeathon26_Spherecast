from typing import List, Dict
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

def _get_driver() -> webdriver.Chrome:
    """Setup a headless Chrome driver with basic bot detection evasion."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Basic Anti-bot measures
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    
    # Evasion scripts
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def search_capsuline(search_text: str) -> List[Dict[str, str]]:
    """
    Search Capsuline website.
    URL: https://www.capsuline.com/search?q={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://www.capsuline.com/search?q={search_text}"
        driver.get(url)
        time.sleep(3)
        # Attempt to handle pagination if .next exists
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and href not in seen:
                    seen.add(href)
                    results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.next, a[rel='next']")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching Capsuline: {e}")
    finally:
        driver.quit()
    return results

def search_colorcon(search_text: str) -> List[Dict[str, str]]:
    """
    Search Colorcon website.
    URL: https://www.colorcon.com/search?query={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://www.colorcon.com/search?query={search_text}"
        driver.get(url)
        time.sleep(3)
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, "a, h3 a")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and "/products/" in href and href not in seen:
                    if text.lower() != 'read more':
                        seen.add(href)
                        results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching Colorcon: {e}")
    finally:
        driver.quit()
    return results

def search_custom_probiotics(search_text: str) -> List[Dict[str, str]]:
    """
    Search Custom Probiotics.
    URL: https://www.customprobiotics.com/search.php?search_query={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://www.customprobiotics.com/search.php?search_query={search_text}"
        driver.get(url)
        time.sleep(3)
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, ".product a, .card-title a")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and href not in seen:
                    seen.add(href)
                    results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, ".pagination-item--next a")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching Custom Probiotics: {e}")
    finally:
        driver.quit()
    return results

def search_rousselot(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_icelandirect(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_ingredion(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_jost_chemical(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_koster_keunen(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_nutra_food_ingredients(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_purebulk(search_text: str) -> List[Dict[str, str]]:
    """
    Search PureBulk website.
    URL: https://purebulk.com/search?q={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://purebulk.com/search?q={search_text}"
        driver.get(url)
        time.sleep(3)
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and href not in seen:
                    # Ignore product review links or image links by ensuring text is substantial
                    if len(text) > 3:
                        seen.add(href)
                        results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.next, a[rel='next'], a[aria-label='Next']")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching PureBulk: {e}")
    finally:
        driver.quit()
    return results

def search_sensient(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_source_omega(search_text: str) -> List[Dict[str, str]]:
    # NO FUNCTIONAL SEARCH OR ENDPOINT FOUND
    return []

def search_strahl_pitsch(search_text: str) -> List[Dict[str, str]]:
    """
    Search Strahl & Pitsch.
    URL: https://strahlpitsch.com/?s={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://strahlpitsch.com/?s={search_text}"
        driver.get(url)
        time.sleep(3)
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, "article a, h2.entry-title a")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and href not in seen:
                    if len(text) > 2:
                        seen.add(href)
                        results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.next.page-numbers")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching Strahl & Pitsch: {e}")
    finally:
        driver.quit()
    return results

def search_trace_minerals(search_text: str) -> List[Dict[str, str]]:
    """
    Search Trace Minerals.
    URL: https://www.traceminerals.com/search?q={search_text}
    """
    driver = _get_driver()
    results = []
    seen = set()
    try:
        url = f"https://www.traceminerals.com/search?q={search_text}"
        driver.get(url)
        time.sleep(3)
        while True:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
            for link in links:
                href = link.get_attribute('href')
                text = link.text.strip()
                if href and text and href not in seen:
                    seen.add(href)
                    results.append({"product_name": text, "product_url": href})
            
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a[aria-label='Next page'], a.next")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break
    except Exception as e:
        logger.error(f"Error searching Trace Minerals: {e}")
    finally:
        driver.quit()
    return results

SEARCH_ROUTING_MAP = {
    "Capsuline": search_capsuline,
    "Colorcon": search_colorcon,
    "Custom Probiotics": search_custom_probiotics,
    "Darling Ingredients / Rousselot": search_rousselot,
    "Icelandirect": search_icelandirect,
    "Ingredion": search_ingredion,
    "Jost Chemical": search_jost_chemical,
    "Koster Keunen": search_koster_keunen,
    "Nutra Food Ingredients": search_nutra_food_ingredients,
    "PureBulk": search_purebulk,
    "Sensient": search_sensient,
    "Source-Omega LLC": search_source_omega,
    "Strahl & Pitsch": search_strahl_pitsch,
    "Trace Minerals": search_trace_minerals
}
