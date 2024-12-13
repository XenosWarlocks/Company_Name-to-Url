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

class ThreadSafeCounter:
    def __init__(self, initial_value=0):
        self._value = initial_value
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value
    
    @property
    def value(self):
        with self._lock:
            return self._value

# Thread-safe logging and file writing
class ThreadSafeLogger:
    _lock = threading.Lock()
    
    @classmethod
    def log(cls, level, message):
        with cls._lock:
            if level == 'info':
                logging.info(message)
            elif level == 'warning':
                logging.warning(message)
            elif level == 'error':
                logging.error(message)

class RealTimeCSVWriter:
    def __init__(self, filename, fieldnames):
        """
        Initialize a thread-safe CSV writer that saves results in real-time
        
        Args:
            filename (str): Path to the output CSV file
            fieldnames (list): Column names for the CSV
        """
        self._lock = threading.Lock()
        self._filename = filename
        self._fieldnames = fieldnames
        
        # Ensure file is created with headers
        with open(self._filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    
    def write_row(self, row):
        """
        Thread-safe method to write a row to the CSV file
        
        Args:
            row (dict): Dictionary of values to write
        """
        with self._lock:
            try:
                with open(self._filename, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self._fieldnames)
                    writer.writerow(row)
            except Exception as e:
                ThreadSafeLogger.log('error', f"Error writing to CSV: {e}")

class SeleniumLinkedInSearcher:
    def __init__(self, 
                 headless: bool = False, 
                 max_workers: int = 5, 
                 proxies_file: str = 'free_ip_list.csv'):
        """
        Initialize Selenium WebDriver with configurable options
        
        Args:
            headless (bool): Run browser in headless mode
            max_workers (int): Maximum number of concurrent searches
            proxies_file (str): Path to CSV file with proxy list
        """
        # Configure logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('linkedin_search.log'),
                logging.StreamHandler()
            ]
        )
        
        # Configuration options
        self.headless = headless
        self.max_workers = max_workers
        self.proxies_file = proxies_file
        self.proxies = self._load_proxies()
        
        # User agents for rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
    def _load_proxies(self) -> List[Dict[str, str]]:
        """
        Load proxies from CSV file
        
        Returns:
            List of proxy dictionaries
        """
        try:
            proxies = []
            with open(self.proxies_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Construct proxy string based on protocol
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
        """
        Configure Chrome options with optional proxy
        
        Args:
            proxy (dict): Proxy configuration dictionary
        
        Returns:
            Configured Chrome Options
        """
        chrome_options = Options()
        
        # User agent rotation
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        
        # Performance and stealth options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Additional stealth mechanisms
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Proxy configuration
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy["proxy_str"]}')
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        return chrome_options
    
    def _create_driver(self, proxy: Optional[Dict[str, str]] = None):
        """
        Create a new WebDriver instance with optional proxy
        
        Args:
            proxy (dict): Proxy configuration dictionary
        
        Returns:
            Configured WebDriver
        """
        driver = webdriver.Chrome(options=self._setup_chrome_options(proxy))
        
        # Additional anti-detection
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
        """
        Simulate human-like browsing behavior
        
        Args:
            driver: Selenium WebDriver instance
        """
        # Random scroll
        scroll_amount = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.5, 2.0))
        
        # Random pause between actions
        time.sleep(random.uniform(1.0, 3.0))
    
    def linkedin_search(self, 
                        website: str, 
                        csv_writer: RealTimeCSVWriter, 
                        processed_count: ThreadSafeCounter,
                        total_websites: int) -> None:
        """
        Perform Google search for LinkedIn page with real-time result saving
        
        Args:
            website (str): Company's website 
            csv_writer (RealTimeCSVWriter): Thread-safe CSV writer
            processed_count (threading.Value): Shared counter for processed websites
            total_websites (int): Total number of websites to process
        """
        # Shuffle proxies to distribute load
        random.shuffle(self.proxies)
        
        # Update and log progress
        current_count = processed_count.increment()
        logging.info(f"Processed {current_count}/{total_websites}: {website}")
        
        # Try with and without proxy
        proxy_attempts = [None] + self.proxies[:3]  # Try direct and first 3 proxies
        
        for proxy in proxy_attempts:
            driver = None
            try:
                # Create driver with or without proxy
                driver = self._create_driver(proxy)
                
                # Construct search query
                search_query = f'site:linkedin.com "{website}"'
                
                # Navigate to Google
                driver.get("https://www.google.com")
                
                # Simulate human behavior
                self._simulate_human_behavior(driver)
                
                # Find search input and perform search
                search_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "q"))
                )
                search_box.clear()
                
                # Simulate typing
                for char in search_query:
                    search_box.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.2))  # Human-like typing
                
                # Random pause before submitting
                time.sleep(random.uniform(0.5, 1.5))
                search_box.send_keys(Keys.RETURN)
                
                # Wait for search results with timeout
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "rso"))
                )
                
                # Simulate human behavior after search
                self._simulate_human_behavior(driver)
                
                # Try multiple search results
                validated_url = None
                max_attempts = 5
                
                for attempt in range(max_attempts):
                    try:
                        # Find search result elements
                        search_results = driver.find_elements(By.XPATH, "//*[@id='rso']/div")
                        
                        if attempt < len(search_results):
                            # Navigate to the specific search result
                            result_xpath = f"//*[@id='rso']/div[{attempt + 1}]/div/div/div/div[1]/div/div/span/a"
                            url_element = driver.find_element(By.XPATH, result_xpath)
                            raw_linkedin_url = url_element.get_attribute('href')
                            
                            # Validate the LinkedIn URL
                            validated_url = self._validate_linkedin_url(website, raw_linkedin_url)
                            if validated_url:
                                break  # Exit the loop if a valid URL is found
                        
                        else:
                            logging.warning(f"No search results found for {website}")
                            break
                    
                    except NoSuchElementException:
                        break
                    
                    except Exception as e:
                        logging.warning(f"Error checking search result {attempt + 1}: {e}")
                
                # Prepare result for writing
                result = {
                    "Website": website,
                    "LinkedIn URL": validated_url or "Not Found",
                    "Proxy Used": proxy['proxy_str'] if proxy else "Direct"
                }
                
                # Write result to CSV in real-time
                csv_writer.write_row(result)
                
                # Update and log progress
                with processed_count:
                    processed_count.value += 1
                    logging.info(f"Processed {processed_count.value}/{total_websites}: {website}")
                
                return
            
            except WebDriverException as e:
                logging.warning(f"WebDriver error for '{website}' with proxy {proxy}: {e}")
                # Continue to next proxy or direct connection
                continue
            
            except Exception as e:
                logging.error(f"Unexpected error for '{website}' with proxy {proxy}: {e}")
                continue
            
            finally:
                # Ensure driver is always closed
                if driver:
                    driver.quit()
        
        # If all attempts fail
        result = {
            "Website": website,
            "LinkedIn URL": "Error",
            "Proxy Used": "None"
        }
        
        # Write failed result to CSV
        csv_writer.write_row(result)
        
        # Update and log progress for failed attempt
        with processed_count:
            processed_count.value += 1
            logging.info(f"Processed {processed_count.value}/{total_websites}: {website}")
    
    def _validate_linkedin_url(self, website: str, linkedin_url: str) -> Union[str, None]:
        """
        Validate LinkedIn URL based on the company's website domain
        
        Args:
            website (str): Company's website
            linkedin_url (str): Extracted LinkedIn URL
        
        Returns:
            Validated LinkedIn URL or None
        """
        try:
            # Extract domain details
            ext = tldextract.extract(website)
            
            # Remove protocol and path from LinkedIn URL
            linkedin_url = linkedin_url.split('://')[1].split('/')[0]
            
            # Check if URL starts with linkedin.com or contains /company/
            if 'linkedin.com' not in linkedin_url:
                return None
            
            # Additional checks for specific country-level domains
            country_specific_domains = [
                # Previous list of domains (omitted for brevity)
            ]
            
            # Check domain and url validity
            for domain in country_specific_domains:
                if domain in website and domain not in linkedin_url:
                    continue
                
            # Ensure the URL contains a valid LinkedIn company page
            if '/company/' not in linkedin_url:
                return None
            
            return linkedin_url
        
        except Exception as e:
            logging.error(f"Error validating LinkedIn URL for {website}: {e}")
            return None
    
    def process_websites(self, 
                     websites_file: str = "Sample_test.xlsx", 
                     output_file: str = "linkedin_urls.csv") -> Dict[str, int]:
        """
        Process websites to find LinkedIn URLs with real-time saving
        
        Args:
            websites_file (str): Path to Excel file with websites
            output_file (str): Path to save LinkedIn URLs CSV
        
        Returns:
            Dict with processing statistics
        """
        # Read the original dataframe
        df = pd.read_excel(websites_file)
        
        # Validate 'Website' column exists
        if 'Website' not in df.columns:
            raise ValueError("Excel file must contain a 'Website' column")
        
        # Prepare CSV writer
        fieldnames = ['Website', 'LinkedIn URL', 'Proxy Used']
        csv_writer = RealTimeCSVWriter(output_file, fieldnames)
        
        # Shared counter for processed websites
        processed_count = ThreadSafeCounter()
        
        # Parallel processing of websites
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit search tasks for each website
            futures = [
                executor.submit(
                    self.linkedin_search, 
                    str(row['Website']), 
                    csv_writer, 
                    processed_count,
                    len(df)
                ) for _, row in df.iterrows()
            ]
            
            # Wait for all futures to complete
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
        result = searcher.process_websites(
            websites_file, 
            output_file=output_file
        )
        
        print(f"Processed {result['total_websites']} websites.")
        print(f"LinkedIn URLs saved to {result['output_file']}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
