# investment_scraper
Pulls investment-related data for list of tickers from various websites

---

For info on using:
- ./get_investment_data.py --help
- ./trailing_json2csv.py --help

Example usage:

Get investment data for GOOG and BND.  Will retrieve into local tmp/ directory.
- ./get_investment_data.py --trading-symbols GOOG BND

Get investment data for trading symbols, one per line, in file ./symbols/list_of_holdings.txt.
- ./get_investment_data.py --symbols-filename ./symbols/list_of_holdings.txt

List datasets and then extract the "Total Return" dataset as CSV from investment json data file.
- ./investment_data_json2csv.py --list-datasets --investment-json-filename ./tmp/<YYYYMMDDHHMMSS>_investment_data.json
- ./investement_data_json2csv.py --extract-dataset "Total Return" --investment-json-filename ./tmp/<YYYYMMDDHHMMSS>_investment_data.json

---

Tested with following utilities/version.

Utility    Version
=======    =======
Python     3.8.2
pip        20.0.2
pip        20.0.2
selenium   3.141.0
setuptools 41.2.0
urllib3    1.25.9 

To set up local environment:
- A local venv subdirectory created using python3 -m venv venv
- Activate every time using . ./venv/bin/activate
- pip install pip --upgrade
- pip install selenium
- Ensure referenced chromedriver (or whatever browser webdriver binary) accessible and matches current browser version if you plan on testing XPATH strings using $x() in the browser