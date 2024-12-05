import os
import csv
import logging
import random
import concurrent.futures
import pandas as pd
from typing import List, Tuple, Dict


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SeleniumGoogleSearcher:
    def __init__(self, headless: bool = False, max_workers: int = 5):
        """
        Initialize Selenium WebDriver with configurable options
       
        Args:
            headless (bool): Run browser in headless mode
            max_workers (int): Maximum number of concurrent searches
        """
        # Configuration options
        self.headless = headless
        self.max_workers = max_workers
        self.chrome_options = self._setup_chrome_options()
       
    def _setup_chrome_options(self) -> Options:
        """
        Configure Chrome options for efficient web scraping
       
        Returns:
            Configured Chrome Options
        """
        chrome_options = Options()
       
        # User agent rotation
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
       
        # Performance and stealth options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
       
        if self.headless:
            chrome_options.add_argument("--headless")
       
        return chrome_options
   
    def _create_driver(self):
        """
        Create a new WebDriver instance
       
        Returns:
            Configured WebDriver
        """
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.implicitly_wait(10)
        return driver
   
    def google_search(self, query: str, num_results: int = 1) -> List[Dict[str, str]]:
        """
        Perform Google search and extract top URLs with more robust error handling
       
        Args:
            query (str): Search query
            num_results (int): Number of results to extract
       
        Returns:
            List of dictionaries containing search result details
        """
        driver = self._create_driver()
       
        try:
            # Navigate to Google with timeout
            driver.get("https://www.google.com")
           
            # Find search input and perform search
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
           
            # Wait for search results with timeout
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "rso"))
            )
           
            # Extract search results
            results = []
           
            for i in range(1, 6):
                try:
                    url_xpath = f"//*[@id='rso']/div[{i}]//cite"
                    url_elements = driver.find_elements(By.XPATH, url_xpath)
                   
                    if url_elements:
                        result = {
                            "Query": query,
                            "URL": url_elements[0].text
                        }
                        results.append(result)
               
                except NoSuchElementException:
                    logger.warning(f"Could not find URL for result {i}")
                except Exception as e:
                    logger.warning(f"Error extracting result {i}: {e}")
               
                if len(results) == num_results:
                    break
           
            return results
       
        except WebDriverException as e:
            logger.error(f"WebDriver error during search for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during search for '{query}': {e}")
            return []
        finally:
            # Ensure driver is always closed
            driver.quit()
   
    def process_companies(self, companies_file: str = "companies.xlsx") -> Tuple[str, str]:
        """
        Process companies in parallel using concurrent processing
       
        Args:
            companies_file (str): Path to Excel file with companies
       
        Returns:
            Tuple of output file paths
        """
        # Read companies from Excel file
        companies = self._read_companies(companies_file)
       
        # Prepare output files
        google_results_file = "google_results.csv"
        cant_find_urls_file = "cant_find_urls.csv"
       
        # Parallel processing of companies
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit search tasks for each company
            future_to_company = {
                executor.submit(self.google_search, company): company
                for company in companies
            }
           
            # Read the original dataframe to preserve additional columns
            original_df = pd.read_excel(companies_file)
           
            # Write results in real-time
            with open(google_results_file, 'w', newline='', encoding='utf-8') as csvfile, \
                 open(cant_find_urls_file, 'w', newline='', encoding='utf-8') as notfound_file:
               
                # Prepare CSV writers
                results_writer = csv.DictWriter(csvfile,
                    fieldnames=list(original_df.columns) + ["URL"])
                results_writer.writeheader()
               
                notfound_writer = csv.DictWriter(notfound_file,
                    fieldnames=list(original_df.columns))
                notfound_writer.writeheader()
               
                for future in concurrent.futures.as_completed(future_to_company):
                    company = future_to_company[future]
                    try:
                        results = future.result()
                       
                        # Find the original row for this company
                        company_row = original_df[original_df['Company Name'] == company].to_dict('records')[0]
                       
                        if results:
                            # Write good results to CSV
                            for result in results:
                                full_result = company_row.copy()
                                full_result["URL"] = result['URL']
                                results_writer.writerow(full_result)
                        else:
                            # Log companies with no results
                            notfound_writer.writerow(company_row)
                   
                    except Exception as e:
                        logger.error(f"Error processing company '{company}': {e}")
       
        return google_results_file, cant_find_urls_file
   
    def _read_companies(self, companies_file: str) -> List[str]:
        """
        Read companies from Excel file
       
        Args:
            companies_file (str): Path to Excel file
       
        Returns:
            List of company names
        """
        try:
            # Read Excel file
            df = pd.read_excel(companies_file)
           
            # Validate 'Company Name' column exists
            if 'Company Name' not in df.columns:
                raise ValueError("Excel file must contain a 'Company Name' column")
           
            # Remove any duplicate or empty company names
            companies = df['Company Name'].dropna().unique().tolist()
           
            if not companies:
                raise ValueError("No valid company names found in the file")
           
            logger.info(f"Successfully read {len(companies)} companies from {companies_file}")
            return companies
       
        except Exception as e:
            logger.error(f"Error reading companies from Excel file: {e}")
            raise


def main():
    searcher = SeleniumGoogleSearcher(headless=False, max_workers=5)
    results_file, notfound_file = searcher.process_companies()
    print(f"Results saved to {results_file}")
    print(f"Companies without results saved to {notfound_file}")


if __name__ == "__main__":
    main()

