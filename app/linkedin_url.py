import os
import csv
import logging
import random
import threading
import concurrent.futures
import pandas as pd
import tldextract
import time
from typing import List, Dict, Optional, Union

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException

class SeleniumLinkedInSearcher:
    def __init__(self, headless: bool = False, max_workers: int = 5, proxies_file: str = 'free_ip_list.csv'):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('linkedin_search.log'), logging.StreamHandler()]
        )

        self.headless = headless
        self.max_workers = max_workers
        self.proxies_file = proxies_file
        self.proxies = self._load_proxies()

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]

    def _load_proxies(self) -> List[Dict[str, str]]:
        try:
            proxies = []
            with open(self.proxies_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['protocols'].lower() in ['socks4', 'socks5', 'http', 'https']:
                        proxy_type = row['protocols'].lower()
                        proxy_str = f"{proxy_type}://{row['ip']}:{row['port']}"
                        proxies.append({
                            'proxy_str': proxy_str,
                            'type': proxy_type,
                            'ip': row['ip'],
                            'port': row['port'],
                            'country': row['country']
                        })
            logging.info(f"Loaded {len(proxies)} proxies")
            return proxies
        except Exception as e:
            logging.error(f"Error loading proxies: {e}")
            return []

    def _setup_chrome_options(self, proxy: Optional[Dict[str, str]] = None) -> Options:
        chrome_options = Options()
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy["proxy_str"]}')

        if self.headless:
            chrome_options.add_argument("--headless")

        return chrome_options

    def _create_driver(self, proxy: Optional[Dict[str, str]] = None):
        driver = webdriver.Chrome(options=self._setup_chrome_options(proxy))
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            """
        })
        driver.implicitly_wait(10)
        return driver

    def _simulate_human_behavior(self, driver):
        scroll_amount = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.5, 2.0))
        time.sleep(random.uniform(1.0, 3.0))

    def linkedin_search(self, website: str, csv_writer: RealTimeCSVWriter, processed_count: ThreadSafeCounter, total_websites: int):
        random.shuffle(self.proxies)
        current_count = processed_count.increment()
        logging.info(f"Processed {current_count}/{total_websites}: {website}")

        proxy_attempts = [None] + self.proxies[:3]

        for proxy in proxy_attempts:
            driver = None
            try:
                driver = self._create_driver(proxy)
                search_query = f'site:linkedin.com "{website}"'
                driver.get("https://www.google.com")
                self._simulate_human_behavior(driver)

                search_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
                search_box.clear()
                for char in search_query:
                    search_box.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.2))

                time.sleep(random.uniform(0.5, 1.5))
                search_box.send_keys(Keys.RETURN)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "rso")))

                self._simulate_human_behavior(driver)

                validated_url = None
                max_attempts = 5

                for attempt in range(max_attempts):
                    try:
                        search_results = driver.find_elements(By.XPATH, "//*[@id='rso']/div")

                        if attempt < len(search_results):
                            result_xpath = f"//*[@id='rso']/div[{attempt + 1}]/div/div/div/div[1]/div/div/span/a"
                            url_element = driver.find_element(By.XPATH, result_xpath)
                            raw_linkedin_url = url_element.get_attribute('href')
                            validated_url = self._validate_linkedin_url(website, raw_linkedin_url)
                            if validated_url:
                                break
                        else:
                            logging.warning(f"No search results found for {website}")
                            break

                    except NoSuchElementException:
                        break
                    except Exception as e:
                        logging.warning(f"Error checking search result {attempt + 1}: {e}")

                result = {
                    "Website": website,
                    "LinkedIn URL": validated_url or "Not Found",
                    "Proxy Used": proxy['proxy_str'] if proxy else "Direct"
                }
                csv_writer.write_row(result)
                return

            except WebDriverException as e:
                logging.warning(f"WebDriver error for '{website}' with proxy {proxy}: {e}")
                continue
            except Exception as e:
                logging.error(f"Unexpected error for '{website}' with proxy {proxy}: {e}")
                continue
            finally:
                if driver:
                    driver.quit()

        result = {
            "Website": website,
            "LinkedIn URL": "Error",
            "Proxy Used": "None"
        }
        csv_writer.write_row(result)

    def _validate_linkedin_url(self, website: str, linkedin_url: str) -> Union[str, None]:
        try:
            ext = tldextract.extract(website)
            linkedin_url = linkedin_url.split('://')[1].split('/')[0]

            if 'linkedin.com' not in linkedin_url:
                return None

            return linkedin_url
        except Exception as e:
            logging.error(f"Error validating LinkedIn URL for {website}: {e}")
            return None

    def process_websites(self, websites_file: str = "Sample_test.xlsx", output_file: str = "linkedin_urls.csv") -> Dict[str, int]:
        df = pd.read_excel(websites_file)

        if 'Website' not in df.columns:
            raise ValueError("Excel file must contain a 'Website' column")

        fieldnames = ['Website', 'LinkedIn URL', 'Proxy Used']
        csv_writer = RealTimeCSVWriter(output_file, fieldnames)

        processed_count = ThreadSafeCounter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.linkedin_search, str(row['Website']), csv_writer, processed_count, len(df))
                for _, row in df.iterrows()
            ]
            concurrent.futures.wait(futures)

        logging.info(f"LinkedIn URL search complete. Results saved to {output_file}")

        return {
            "total_websites": len(df),
            "output_file": output_file
        }

def main():
    searcher = SeleniumLinkedInSearcher(
        headless=False,
        max_workers=5,
        proxies_file='free_ip_list.csv'
    )

    websites_file = "Sample_test.xlsx"
    output_file = "linkedin_urls.csv"

    try:
        result = searcher.process_websites(websites_file, output_file=output_file)

        print(f"Processed {result['total_websites']} websites.")
        print(f"LinkedIn URLs saved to {result['output_file']}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
