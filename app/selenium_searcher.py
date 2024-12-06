import os
import csv
import logging
import random
import concurrent.futures
import pandas as pd
from typing import List, Tuple, Dict, Optional


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
    def __init__(self, headless: bool = False, max_workers: int = 5, batch_size: int = 5):
        """
        Initialize Selenium WebDriver with configurable options
       
        Args:
            headless (bool): Run browser in headless mode
            max_workers (int): Maximum number of concurrent searches
            batch_size (int): Number of companies to process in each batch
        """
        # Configuration options
        self.headless = headless
        self.max_workers = max_workers
        self.batch_size = batch_size
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
   
    def _get_last_processed_row(self, state_file='processing_state.txt'):
        """
        Read the last processed row from a state file
       
        Args:
            state_file (str): Path to the state file
       
        Returns:
            int: Last processed row number
        """
        try:
            with open(state_file, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0
   
    def _update_last_processed_row(self, row, state_file='processing_state.txt'):
        """
        Update the last processed row in the state file
       
        Args:
            row (int): Row number to save
            state_file (str): Path to the state file
        """
        with open(state_file, 'w') as f:
            f.write(str(row))
   
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
   
    def process_companies(self,
                     companies_file: str = "companies.xlsx",
                     output_results_file: Optional[str] = None,
                     output_notfound_file: Optional[str] = None) -> Dict[str, int]:
        """
        Process all companies, optionally resuming from a previous state
       
        Args:
            companies_file (str): Path to Excel file with companies
            output_results_file (str, optional): Path to save results CSV
            output_notfound_file (str, optional): Path to save not found companies CSV
       
        Returns:
            Dict with start_row and total_rows
        """
        # Set default output file names if not provided
        if output_results_file is None:
            output_results_file = "google_results.csv"
        if output_notfound_file is None:
            output_notfound_file = "cant_find_urls.csv"
       
        # Read the original dataframe
        df = pd.read_excel(companies_file)
       
        # Validate 'Company Name' column exists
        if 'Company Name' not in df.columns:
            raise ValueError("Excel file must contain a 'Company Name' column")
       
        # Get the last processed row
        start_row = self._get_last_processed_row()
       
        # Check if we've processed all rows
        if start_row >= len(df):
            logger.info("All rows have been processed.")
            return {"start_row": start_row, "total_rows": len(df)}
       
        # Slice the DataFrame from the last processed row to the end
        companies_batch = df.iloc[start_row:]
       
        # Determine the slice of companies to process
        logger.info(f"Processing rows from {start_row} to {len(df)}")
       
        # Prepare output file modes based on whether it's the first batch
        results_mode = 'a' if os.path.exists(output_results_file) else 'w'
        notfound_mode = 'a' if os.path.exists(output_notfound_file) else 'w'
       
        # Parallel processing of companies
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit search tasks for each company
            future_to_company = {
                executor.submit(self.google_search, row['Company Name']): row
                for _, row in companies_batch.iterrows()
            }
           
            # Write results in real-time
            with open(output_results_file, mode=results_mode, newline='', encoding='utf-8') as csvfile, \
                open(output_notfound_file, mode=notfound_mode, newline='', encoding='utf-8') as notfound_file:
               
                # Prepare CSV writers with all columns from original DataFrame
                results_writer = csv.DictWriter(csvfile,
                    fieldnames=list(df.columns) + ["URL"])
                notfound_writer = csv.DictWriter(notfound_file,
                    fieldnames=list(df.columns))
               
                # Write headers only if it's the first batch
                if start_row == 0:
                    results_writer.writeheader()
                    notfound_writer.writeheader()
               
                for future in concurrent.futures.as_completed(future_to_company):
                    company_row = future_to_company[future]
                    try:
                        results = future.result()
                       
                        if results:
                            # Write good results to CSV
                            for result in results:
                                full_result = company_row.to_dict()
                                full_result["URL"] = result['URL']
                                results_writer.writerow(full_result)
                        else:
                            # Log companies with no results
                            notfound_writer.writerow(company_row.to_dict())
                   
                    except Exception as e:
                        logger.error(f"Error processing company '{company_row['Company Name']}': {e}")
       
        # Update the last processed row to the total number of rows
        next_start_row = len(df)
        self._update_last_processed_row(next_start_row)
       
        logger.info(f"Processed all rows from {start_row} to {next_start_row}")
       
        return {"start_row": next_start_row, "total_rows": len(df)}


def main():
    searcher = SeleniumGoogleSearcher(headless=False, max_workers=5, batch_size=500)
   
    companies_file = "companies.xlsx"
    results_file = "google_results.csv"
    notfound_file = "cant_find_urls.csv"
   
    try:
        result = searcher.process_companies(
            companies_file,
            output_results_file=results_file,
            output_notfound_file=notfound_file
        )
       
        start_row = result['start_row']
        total_rows = result['total_rows']
       
        if start_row < total_rows:
            print(f"Processed up to row {start_row} of {total_rows}. More rows remain.")
        else:
            print("All rows have been processed.")
   
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()



