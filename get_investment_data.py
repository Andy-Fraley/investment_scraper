#!/usr/bin/env python

import argparse
from util import util
import datetime
import sys
import os
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import json


# Fake class only for purpose of limiting global namespace to the 'g' object
class g:
    args = None
    driver = None
    symbols = None
    debug_html_file = None
    debug_html_filename = None
    current_trading_symbol = None
    current_symbol_type = None
    timestamp = None
    investment_data = {}
    debug_file_incrementor = 1
    trading_symbol_urls = {}
    wait_element = 10
    wait_page = 60


def WaitClick(locator, time_in_secs=None):
    global g

    if time_in_secs is None:
        time_in_secs = g.wait_element
    element = WebDriverWait(g.driver, time_in_secs).until(EC.element_to_be_clickable(locator))
    element.click()
    return element


def WaitFloat(locator, time_in_secs=None, retries=5, wait_time_per_retry=1):
    global g

    if time_in_secs is None:
        time_in_secs = g.wait_element
    element = WebDriverWait(g.driver, time_in_secs).until(EC.visibility_of_element_located(locator))
    while retries > 0:
        element_text = element.get_attribute('textContent').strip()
        if IsFloat(element_text):
            return element_text
        time.sleep(wait_time_per_retry)
        retries -= 1
    raise TimeoutException


def WaitEqual(locator, string, time_in_secs=None, retries=5, wait_time_per_retry=1):
    global g

    if time_in_secs is None:
        time_in_secs = g.wait_element
    element = WebDriverWait(g.driver, time_in_secs).until(EC.visibility_of_element_located(locator))
    while retries > 0:
        element_text = element.get_attribute('textContent').strip()
        if element_text == string:
            return element
        time.sleep(wait_time_per_retry)
        retries -= 1
    raise TimeoutException


# Can raise TimeoutException if no Morningstar page for symbol
def LoadMorningstarSymbolPage(symbol):
    global g

    # Load cached URLs (if cache file exists and not already loaded)
    url_cache_filename = './tmp/url_cache.json'
    if len(g.trading_symbol_urls) == 0:
        if os.path.isfile(url_cache_filename):
            with open(url_cache_filename) as json_file:
                g.trading_symbol_urls = json.load(json_file)
        else:
            g.trading_symbol_urls = {}

    # Retrieve page using autocomplete if no cached URL for symbol. Mark cache to flush to disk if a miss
    url_info = g.trading_symbol_urls.get(symbol, None)
    if url_info is None:
        need_to_rewrite_urls = True
        input_field = WaitClick((By.ID, 'AutoCompleteBox'), g.wait_page)
        input_field.send_keys(symbol)
        WaitEqual((By.XPATH, "//td[@class='ACDropDownStyle']//b"), symbol)
        print('Loading Morningstar page for ' + symbol + '...')
        input_field.send_keys(Keys.RETURN)

    # Retrieve page from URL
    else:
        need_to_rewrite_urls = False
        url_text = url_info['url']
        print('Loading Morningstar page for ' + symbol + '...')
        g.driver.get(url_text)

    # Ensure that retrieved page matches expected trading symbol
    WaitEqual((By.XPATH, "//span[contains(@class, 'symbol')]"), symbol, g.wait_page)

    # Only update and rewrite URL cache if it changed
    if need_to_rewrite_urls:
        url_info = {
            'timestamp': g.timestamp,
            'url': g.driver.current_url
        }
        g.trading_symbol_urls[symbol] = url_info
        with open(url_cache_filename, 'w') as json_file:
            json.dump(g.trading_symbol_urls, json_file)

    # We can determine the type of stat page retrieve (STOCK, MUTUAL, ETF) based on the top horizontal nav
    # number of elements / menu-items
    nav_lis = WebDriverWait(g.driver, g.wait_element).until(EC.presence_of_all_elements_located((By.XPATH,
        "//ul[contains(@class, 'sal-nav-horizontal')]/li")))
    count_nav_lis = len(nav_lis)
    g.current_symbol_type = None
    if count_nav_lis == 12:
        g.current_symbol_type = 'STOCK'
    elif count_nav_lis == 9:
        g.current_symbol_type = 'MUTUAL'
    elif count_nav_lis == 7:
        g.current_symbol_type = 'ETF'
    if g.current_symbol_type is None:
        print('Error: ' + g.current_trading_symbol + " is of type 'None'.")
    return g.current_symbol_type


def IsFloat(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def Quit():
    global g

    if not g.args.live_window:
        g.driver.quit()
    util.sys_exit(0)


def LoadMorningstarMainPage():
    global g

    g.driver.get('https://elibrary.einetwork.net/new-general-reference/new-consumer-business-resources/')
    element = WebDriverWait(g.driver, g.wait_page).until(EC.visibility_of_element_located((By.XPATH, \
        "//li[contains(@id,'eg-12-post-id-913')]")))
    hover = ActionChains(g.driver).move_to_element(element)
    hover.perform()
    try:
        WaitClick((By.XPATH, "//a[contains(@href, 'https://library.morningstar.com/remote.html')]"))
    except TimeoutException:
        print('Cannot load Morningstar launch page. Timed out. Aborting!')
        Quit()
    print('Loading Morningstar main page...')

    # Switch to right-most tab
    g.driver.switch_to.window(g.driver.window_handles[len(g.driver.window_handles)-1])

    try:
        element = WebDriverWait(g.driver, g.wait_page).until(EC.visibility_of_element_located((By.XPATH, "//body")))
    except TimeoutException:
        print('Cannot load Morningstar main page. Timed out. Aborting!')
        Quit()

    if element.get_attribute('textContent') == 'The page cannot be displayed because an internal server error' \
        ' has occurred.':
        print('Cannot load Morningstar main page. Server error. Aborting!')
        Quit()


def ScrapeMorningstarFundData():
    global g

    header_elems = WebDriverWait(g.driver, g.wait_element).until(EC.presence_of_all_elements_located((By.XPATH,
        "//div[contains(@class, 'performance-annual-table')]/div/table[contains(@class, 'total-table')]/" \
        "tbody/tr[1]/td")))
    perf_elems = WebDriverWait(g.driver, g.wait_element).until(EC.presence_of_all_elements_located((By.XPATH,
        "//div[contains(@class, 'performance-annual-table')]/div/table[contains(@class, 'total-table')]/" \
        "tbody/tr[2]/td/span")))
    StashSeleniumTableData(header_elems, perf_elems)

    expense_ratio_text = g.driver.find_element_by_xpath("//div[contains(@class, 'sal-dp-name') " \
        "and starts-with(., 'Expense Ratio')]/following-sibling::div").get_attribute('textContent').strip()
    StashDataPoint(g.current_trading_symbol, 'Stats', 'Expense Ratio', expense_ratio_text)

    WaitClick((By.XPATH, "//div[@ng-click='vm.toggleExpandedData()']"))
    tax_cost_ratio_text = WaitFloat((By.XPATH, "//div[contains(@class, 'sal-mip-taxes__dp-name') and " \
        "contains(., 'Fund')]/following-sibling::div"))
    StashDataPoint(g.current_trading_symbol, 'Stats', '3-Year Tax Cost Ratio', tax_cost_ratio_text)


def ScrapeMorningstarStockData():
    global g

    header_elems = WebDriverWait(g.driver, g.wait_element).until(EC.presence_of_all_elements_located((By.XPATH,
        "//div[contains(@class, 'fairvalue-annual-table')]/div/table[contains(@class, 'total-table')]/" \
        "tbody/tr[1]/td")))
    perf_elems = WebDriverWait(g.driver, g.wait_element).until(EC.presence_of_all_elements_located((By.XPATH,
        "//div[contains(@class, 'fairvalue-annual-table')]/div/table[contains(@class, 'total-table')]/" \
        "tbody/tr[3]/td/span")))
    StashSeleniumTableData(header_elems, perf_elems)


def StashSeleniumTableData(header_elems, perf_elems):
    index = 0
    for header_elem in header_elems:
        header_val = header_elem.get_attribute('textContent').strip()
        perf_val = perf_elems[index].get_attribute('textContent').strip()
        if IsFloat(perf_val):
            StashDataPoint(g.current_trading_symbol, 'Total Returns', header_val, perf_val, '%')
        index += 1


# Can raise TimeoutException if no Morningstar page for symbol
def GetMorningstarData():
    global g

    for g.current_trading_symbol in g.symbols:

        # If we already retrieved stats data for symbol, don't retrieve again
        if g.current_trading_symbol in g.investment_data:
            print('Already have data for ' + g.current_trading_symbol + '. Skipping...')
            continue

        if g.args.emit_debug_html:
            print('Writing debug HTML')
            emit_debug_html(g.driver.page_source)

        try:
            symbol_type = LoadMorningstarSymbolPage(g.current_trading_symbol)
        except TimeoutException:
            print("No Morningstar page found for " + g.current_trading_symbol + ". Skipping...")
            continue

        if symbol_type == 'STOCK':
            ScrapeMorningstarStockData()
        elif symbol_type == 'ETF' or symbol_type == 'MUTUAL':
            ScrapeMorningstarFundData()


def StashDataSeriesItem(symbol, dataset_name, stat_name, timeframe, datum, suffix=''):
    if IsFloat(datum) and float(datum) != 0.0:
        if symbol not in g.investment_data:
            g.investment_data[symbol] = {}
        if dataset_name not in g.investment_data[symbol]:
            g.investment_data[symbol][dataset_name] = {}
        if stat_name not in g.investment_data[symbol][dataset_name]:
            g.investment_data[symbol][dataset_name][stat_name] = {}
        g.investment_data[symbol][dataset_name][stat_name][timeframe] = datum + suffix


def StashDataPoint(symbol, dataset_name, stat_name, datum, suffix=''):
    if len(datum) > 1 and datum[-1] == '%':
        datum = datum[:-1]
        suffix = '%'
    if IsFloat(datum):
        if symbol not in g.investment_data:
            g.investment_data[symbol] = {}
        if dataset_name not in g.investment_data[symbol]:
            g.investment_data[symbol][dataset_name] = {}
        g.investment_data[symbol][dataset_name][stat_name] = datum + suffix
    else:
        print("datum '" + datum + "'is not a float, unable to stash.")


def StashDataSet(symbol, dataset_name, data):
    if symbol not in g.investment_data:
        g.investment_data[symbol] = {}
    if dataset_name not in g.investment_data[symbol]:
        g.investment_data[symbol][dataset_name] = {}
    g.investment_data[symbol][dataset_name] = data


def StashDataRow(symbol, dataset_name, stat_name, row_data, suffix=''):
    for key in row_data.keys():
        StashDataSeriesItem(symbol, dataset_name, stat_name, key, row_data[key], suffix)


def emit_debug_html(s, standalone=False):
    global g

    if standalone or g.debug_html_file is None:
        if not(os.path.isdir('./tmp')):
            print('Temporary directory ' + os.path.abspath('./tmp') + ' must be present to emit debug HTML file. ' \
                'Aborting!')
            sys.exit(1)
        debug_html_filename = './tmp/' + g.timestamp + '_' + str(g.debug_file_incrementor).zfill(3) + '_DEBUG.html'
        g.debug_file_incrementor += 1
        debug_html_file = open(debug_html_filename, 'w')
        print('Writing page HTML to ' + debug_html_filename + '.')
    else:
        print('Appending page HTML to ' + g.debug_html_filename + '.')
    debug_html_file.write(s)
    if not standalone and g.debug_html_file is None:
        g.debug_html_filename = debug_html_filename
        g.debug_html_file = debug_html_file


def main(argv):

    global g

    parser = argparse.ArgumentParser()
    parser.add_argument('--message-output-filename', required=False, help='Filename of message output file. If ' +
        'unspecified, defaults to stderr')
    parser.add_argument('--trading-symbols', required=False, nargs='+',
        help='Market trading symbols of the holding to gather Morningstar info for. E.g. GOOG IVV IBM, etc.')
    parser.add_argument('--symbols-filename', required=False, help='Input file with trading symbol per line.')
    parser.add_argument('--emit-debug-html', action='store_true', help='If specified, then a ' \
        'debug_yyyymmddhhmmss.html file is created to allow Javascript-retrieved HTML to be available for ' \
        'inspection.')
    parser.add_argument('--live-window', action='store_true', help='If specified, then ' \
        "webdriver runs without '--headless' option and browser window is left open at the end of the run.")
    parser.add_argument('--append-results', required=False, help='Output .json results file from a prior run.')
    g.args = parser.parse_args()

    message_level = 'Info'
    util.set_logger(message_level, g.args.message_output_filename, os.path.basename(__file__))

    if g.args.symbols_filename is None and g.args.trading_symbols is None:
        print('NOTE: --trading-symbols and/or --symbols-filename must be specified\n')
        parser.print_help()
        sys.exit(0)

    g.timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    g.symbols = []
    if g.args.symbols_filename is not None:
        with open(g.args.symbols_filename) as fp:
            line = fp.readline().rstrip()
            while line:
                g.symbols.append(line)
                line = fp.readline().rstrip()
    if g.args.trading_symbols is not None:
        for trading_symbol in g.args.trading_symbols:
            g.symbols.append(trading_symbol)

    if g.args.append_results is not None:
        if os.path.isfile(g.args.append_results):
            with open(g.args.append_results) as json_file:
                g.investment_data = json.load(json_file)

    print('Gathering Morningstar data for these trading symbols: ' + ', '.join(g.symbols))

    # Establish Chrome browser option set
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--incognito")
    if not g.args.live_window:
        chrome_options.add_argument("--headless")

    # Uncommenting one line below determines if running incognito or not
    g.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    #g.driver = webdriver.Chrome('/Users/afraley/Documents/bin/chromedriver', options=chrome_options)
    #g.driver = webdriver.Chrome('/Users/afraley/Documents/bin/chromedriver')
    g.driver.set_window_size(1120, 550)

    LoadMorningstarMainPage()
    GetMorningstarData()

    # Report on any missing symbols
    missing_symbols = []
    for symbol in g.symbols:
        if symbol not in g.investment_data.keys():
            missing_symbols.append(symbol)
    if len(missing_symbols) > 0:
        print('Morningstar data could not be pulled for the following symbols: ' + ', '.join(missing_symbols))

    # If we have collected data to write...
    if len(g.investment_data) > 0:
        print(g.investment_data)
        json_filename = './tmp/' + g.timestamp + '_investment_data.json'
        with open(json_filename, 'w') as json_file:
            json.dump(g.investment_data, json_file)
        print('Results written to ' + json_filename + '\nDone!')
    else:
        print('No data collected. Exiting!')

    # If we have debug HTML page(s) to write
    if g.debug_html_file is not None:
        g.debug_html_file.close()

    # Clean up and exit, flushing error messages
    Quit()


if __name__ == "__main__":
    main(sys.argv[1:])
