import asyncio
import aiofiles
import csv
import os
import logging
import backoff
import chardet


from urllib.parse import urlparse
from typing import List, Dict, Tuple, Set, Union
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


try:
    import enchant
    ENGLISH_DICT = enchant.Dict("en_US")
except ImportError:
    logger.warning("enchant dictionary not found. Some features may not work as expected.")
    ENGLISH_DICT = None


# Constants and Configuration
URL_COUNT_WEIGHT = 0.25
URL_ORDER_WEIGHT = -0.25
URL_LEN_WEIGHT = -0.1


TRIVIAL_WORDS = {
    "company", "inc", "group", "corporation", "co", "corp",
    "university", "college", "&", "llc", "the", "of", "a", "an",
    "LLC", "LLP", "Ltd", "Limited"
}


class CompanyURLFinder:
    def __init__(self, api_key: str = None, cse_id: str = None, max_results: int = 10):
        """
        Initialize CompanyURLFinder with configurable parameters
       
        Args:
            api_key (str, optional): Google Custom Search API key
            cse_id (str, optional): Custom Search Engine ID
            max_results (int, optional): Maximum number of search results to retrieve
        """
        # Environment variable or direct argument handling
        self.api_key = api_key or os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
        self.cse_id = cse_id or os.getenv("CUSTOM_SEARCH_ENGINE_ID")
        self.max_results = max_results
       
        if not self.api_key or not self.cse_id:
            raise ValueError(
                "API Key and Custom Search Engine ID must be provided "
                "either as arguments or in .env file"
            )
       
        # Initialize Google Custom Search service
        self.service = build("customsearch", "v1", developerKey=self.api_key)


    @staticmethod
    def simplify_url(url: str) -> str:
        """Simplify URL to its domain."""
        return urlparse(url).netloc


    @staticmethod
    def get_company_acronyms(company: str) -> Set[str]:
        """Generate acronyms from company name."""
        all_words = ''.join(word[0] for word in company.split()).lower()
        important = ''.join(word[0] for word in company.split()
                             if word.lower() not in TRIVIAL_WORDS).lower()
        return {all_words, important}


    @staticmethod
    def arrange_words_by_importance(company: str) -> Tuple[List[str], List[str]]:
        """Arrange company words by importance."""
        words = sorted(company.lower().split(), key=len, reverse=True)
        nonwords, others = [], []
       
        for word in words:
            if word.lower() in TRIVIAL_WORDS:
                continue
           
            try:
                if ENGLISH_DICT is not None and not ENGLISH_DICT.check(word):
                    nonwords.append(word)
                else:
                    others.append(word)
            except Exception:
                others.append(word)
       
        return nonwords, others


    def _rank_urls(self, urls: List[str]) -> List[Tuple[str, float]]:
        """Rank URLs using weighted linear combination."""
        ranked_urls_dict = {}
        min_rank, max_rank = float('inf'), float('-inf')


        for i, url in enumerate(urls):
            simple_url = self.simplify_url(url)
            domain_parts = simple_url.split(".")
            domain_length = len(domain_parts[1]) if len(domain_parts) > 2 else len(domain_parts[0])


            rank = (URL_COUNT_WEIGHT +
                    URL_ORDER_WEIGHT * (i + 1) +
                    URL_LEN_WEIGHT * domain_length)
           
            ranked_urls_dict[simple_url] = ranked_urls_dict.get(simple_url, 0) + rank


            min_rank = min(min_rank, ranked_urls_dict[simple_url])
            max_rank = max(max_rank, ranked_urls_dict[simple_url])


        divisor = max(max_rank - min_rank, 1)
        return sorted(
            [(url, (rank - min_rank) / divisor) for url, rank in ranked_urls_dict.items()],
            key=lambda x: x[1],
            reverse=True
        )


    @backoff.on_exception(
        backoff.expo,
        (HttpError, ConnectionError),
        max_tries=3
    )
    def fetch_google_results(self, query: str) -> List[str]:
        """
        Fetch Google search results with exponential backoff and retry
       
        Args:
            query (str): Search query for company name
       
        Returns:
            List[str]: List of URLs from search results
        """
        try:
            logger.info(f"Fetching results for query: {query}")
            result = self.service.cse().list(
                q=query,
                cx=self.cse_id,
                num=self.max_results
            ).execute()
           
            urls = [item['link'] for item in result.get('items', [])]
           
            if not urls:
                logger.warning(f"No URLs found for query: {query}")
            return urls
       
        except HttpError as e:
            logger.error(f"HTTP Error for {query}: {e}")
            logger.error(f"Error details: {e.resp.status}, {e.content}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching results for {query}: {e}")
            return []


    def find_best_url(self, company: str, urls: List[str]) -> Tuple[str, float, str]:
        """Advanced URL matching logic."""
        company = ''.join(c for c in company if c not in '.,')
        ranked_urls = self._rank_urls(urls)
        nonwords, others = self.arrange_words_by_importance(company)
        company_acronyms = self.get_company_acronyms(company)
        simplified_name = company.replace(" ", "").lower()


        for domain, rank in ranked_urls:
            domain_parts = domain.split(".")
            normalized_domain = domain_parts[1] if len(domain_parts) >= 3 else domain_parts[0]


            # Multiple matching strategies
            if normalized_domain in simplified_name or simplified_name in normalized_domain:
                return domain, rank, "direct domain match"


            if normalized_domain in company_acronyms:
                return domain, rank, "acronym match"


            if any(nonword in normalized_domain for nonword in nonwords):
                return domain, rank * 0.5, "partial nonword match"


        # If no match found, return the top-ranked URL
        return ranked_urls[0][0] if ranked_urls else "", 0, "no match found"


    def process_companies(self, companies: List[str]) -> Dict[str, Tuple[str, float, str]]:
        """Synchronously process multiple companies"""
        results = {}
        for company in companies:
            urls = self.fetch_google_results(company)
            best_url_info = self.find_best_url(company, urls)
            results[company] = best_url_info
        return results


    @staticmethod
    async def read_companies(file_path: str = "cant_find_urls.txt") -> List[str]:
        """
        Asynchronously read companies from a file with detected encoding
       
        Args:
            file_path (str): Path to the companies file
       
        Returns:
            List[str]: List of company names
        """
        # Detect encoding
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            detected_encoding = chardet.detect(raw_data)['encoding']
       
        # Open with the detected encoding
        async with aiofiles.open(file_path, mode='r', encoding=detected_encoding) as file:
            # Read lines, strip whitespace, and remove empty lines
            return [line.strip() for line in await file.readlines() if line.strip()]


    @staticmethod
    async def save_results_to_csv(
        data: Dict[str, Tuple[str, float, str]],
        output_file: str = "api_results.csv"
    ):
        """Save results to CSV asynchronously."""
        async with aiofiles.open(output_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            await writer.writerow(["Company", "Best URL", "Match Rank", "Match Type"])
            for company, (url, rank, match_type) in data.items():
                await writer.writerow([company, url, f"{rank:.2f}", match_type])


    @staticmethod
    def detect_file_encoding(file_path: str) -> str:
        """
        Detect file encoding
       
        Args:
            file_path (str): Path to the file
       
        Returns:
            str: Detected file encoding
        """
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
        return result['encoding']


async def main():
    try:
        finder = CompanyURLFinder()
       
        # Read companies and process
        companies = await finder.read_companies()
        results = finder.process_companies(companies)
       
        # Save results
        await finder.save_results_to_csv(results)
        logger.info("Results saved to api_results.csv")
        print("Results saved to api_results.csv")
    except Exception as e:
        logger.error(f"Critical error in main process: {e}", exc_info=True)
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())

