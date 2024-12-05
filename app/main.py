import os
import sys
from dotenv import load_dotenv


# Import search strategies
from selenium_searcher import SeleniumGoogleSearcher
from api_algo import CompanyURLFinder


def main():
    # Load environment variables
    load_dotenv()
   
    print("Company URL Finder")
    print("1. Selenium Google Search (Fast)")
    print("2. Google Custom Search API")
    print("3. Combine Both Strategies")
   
    choice = input("Select your search strategy (1/2/3): ").strip()
   
    try:
        if choice == '1':
            # Selenium Search with parallel processing
            searcher = SeleniumGoogleSearcher(headless=False, max_workers=5)
            results_file, notfound_file = searcher.process_companies()
            print(f"Selenium search complete. Results in {results_file}")
       
        elif choice == '2':
            # Google Custom Search API
            finder = CompanyURLFinder()
            companies = finder.read_companies()
            results = finder.process_companies(companies)
            finder.save_results_to_csv(results)
            print("API search complete. Results saved to results.csv")
       
        elif choice == '3':
            # Combined Strategy
            # First run Selenium search
            selenium_searcher = SeleniumGoogleSearcher(headless=True, max_workers=3)
            selenium_results_file, _ = selenium_searcher.process_companies()
           
            # Then use API for additional validation/processing
            api_finder = CompanyURLFinder()
            companies = api_finder.read_companies()
            api_results = api_finder.process_companies(companies)
            api_finder.save_results_to_csv(api_results)
           
            print("Combined search complete.")
           
        else:
            print("Invalid choice. Please select 1, 2, or 3.")
            sys.exit(1)
   
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
       
if __name__ == "__main__":
    main()

