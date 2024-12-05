# Company URL Finder

## Overview

Company URL Finder is a robust Python application designed to help you efficiently search and extract company website URLs using multiple strategies. The project provides two main search approaches:

1. **Selenium Web Scraping**: Uses Selenium WebDriver to perform direct Google searches
2. **Google Custom Search API**: Leverages Google's official search API for precise URL retrieval

### Key Features

- Parallel processing of company searches
- Multiple search strategies
- Adaptive URL ranking algorithm
- Error handling and logging
- Flexible configuration options

## Prerequisites

### System Requirements

- Python 3.8+
- Chrome Browser (for Selenium)
- ChromeDriver

### Dependencies

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

### Environment Setup

1. Create a `.env` file in the project root
2. Add the following environment variables:
   ```
   GOOGLE_CUSTOM_SEARCH_API_KEY=your_google_api_key
   CUSTOM_SEARCH_ENGINE_ID=your_custom_search_engine_id
   ```

## Installation

1. Clone the repository:
   ```bash
   https://github.com/XenosWarlocks/company-url-finder.git
   cd company-url-finder
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install ChromeDriver:
   - Download compatible with your Chrome browser version
   - Add to system PATH or specify in script

## Usage

### Input File Preparation

Prepare an Excel file (`companies.xlsx`) with a column named "Company Name" containing the list of companies you want to search.

### Running the Application

```bash
python main.py
```

### Search Strategy Options

1. **Selenium Google Search (Option 1)**: 
   - Faster, web-scraping approach
   - Parallel processing
   - Suitable for smaller lists

2. **Google Custom Search API (Option 2)**: 
   - More precise results
   - Limited by API quota
   - Better for comprehensive searches

3. **Combined Strategy (Option 3)**: 
   - First uses Selenium
   - Then validates/processes with API
   - Most thorough but slower

## Output Files

- `google_results.csv`: Successful company URL matches
- `cant_find_urls.csv`: Companies without URL matches
- `api_results.csv`: Custom Search API results

## Advanced Configuration

### Selenium Searcher

Customize in `selenium_searcher.py`:
- `headless`: Run browser invisibly
- `max_workers`: Control parallel search threads

### URL Ranking Parameters

Adjust in `google_algo.py`:
- `URL_COUNT_WEIGHT`
- `URL_ORDER_WEIGHT`
- `URL_LEN_WEIGHT`

## Extending the Project

### Module Extensions

You can extend functionality by:
1. Creating custom URL matching algorithms
2. Adding more web scraping strategies
3. Implementing additional ranking methods

Example extension structure:
```python
class CustomURLFinder:
    def __init__(self, parent_finder):
        self.parent = parent_finder
    
    def custom_url_matching_method(self, company, urls):
        # Implement custom logic
        pass
```

## Troubleshooting

- Ensure ChromeDriver matches your Chrome version
- Check API key and Search Engine ID
- Verify input file format
- Monitor API usage quotas

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
