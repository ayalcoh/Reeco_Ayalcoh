# Sysco Product Scraper

A Python web scraper designed to collect product data from Sysco's website for Oregon locations. Optimized for performance with strategic sampling and smart pagination.

## Oregon Location
- **Zip Code Used**: 97205 (Portland, OR)

## Features

- Scrapes 8,000+ products from 11 categories
- Two operation modes: fast extraction vs detailed descriptions
- Strategic sampling for extended product information
- Smart pagination with empty page detection
- Robust error handling with multiple fallback selectors
- Comprehensive logging (console + file)
- Interactive configuration prompts

## Data Collected

For each product:
- Brand Name
- Product Name  
- Packaging Information
- SKU (Product ID)
- Picture URL
- Description


## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install ChromeDriver for Selenium:
   - Download from: https://chromedriver.chromium.org/
   - Add to PATH or place in project directory

## Usage

Run the scraper:
```bash
python3 sysco-scraper-simple.py
```

### Interactive Configuration
The scraper will prompt you for:
1. **Description fetching**: Choose whether to collect detailed descriptions (slower but more comprehensive)
2. **Test mode**: Option to test with just 1 category first

### Operation Modes

**Fast Mode (descriptions=no)**:
- ~8,000+ products from 11 categories
- Output: `sysco_products_oregon_full.csv`

**Extended Mode (descriptions=yes)**:
- Includes detailed descriptions for strategic sample (3 products per page)
- Visits individual product detail pages
- Runtime: Longer due to individual page visits
- Output: `sysco_products_oregon.csv` (with description column populated)

## Performance Notes

**Why description fetching takes longer:**
- Must visit individual product detail pages (vs just listing pages)
- Each product page visit adds 2-3 seconds + network latency
- Strategic sampling limits to 3 products per page to balance thoroughness with time


## Sample Output

The CSV will contain columns:
- brand_name
- product_name
- packaging_info
- sku
- picture_url
- description

## Output Files

Depending on your configuration, you may see:
- `sysco_products_oregon.csv` - Final output with all scraped products
- `sysco_products_oregon_temp.csv` - Progress backup (created during scraping)
- `sysco_scraper.log` - Detailed debug logging

## Architecture Highlights

- **Strategic Sampling**: Collects extended info for representative products rather than all
- **Smart Pagination**: Automatically stops after 3 consecutive empty pages
- **Robust Extraction**: Multiple fallback selectors for reliable data extraction
- **Modular Design**: Clean separation of concerns for easy maintenance and explanation