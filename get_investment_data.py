#!/usr/bin/env python

import argparse
from util import util
import datetime
import sys
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import requests
import json


def FixStatName(ticker, stat_name):
    if re.match('^' + ticker.upper() + '(\s+\(PRICE\))?$', stat_name.upper()):
        stat_name = 'Price'
    elif re.match('^' + ticker.upper()  + '\s+\(NAV\)$', stat_name.upper()):
        stat_name = 'NAV'
    return stat_name


def IsFloat(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def LoadMorningstarMain():
    global g

    # Load up symbols to be retrieved
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

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--incognito")

    # Uncommenting one line below determines if running incognito or not
    g.driver = webdriver.Chrome('/Users/afraley/Documents/bin/chromedriver', chrome_options=chrome_options)
#    g.driver = webdriver.Chrome('/Users/afraley/Documents/bin/chromedriver')

    g.driver.set_window_size(1120, 550)

    print('Gathering Morningstar data for these trading symbols: ' + ', '.join(g.symbols))
    print('Navigating to Morningstar website')

    # We've had problems with authentication, so loop until no authentication error
    while True:
        g.driver.get('http://erec.einetwork.net/dba-z/')
        g.driver.find_element_by_xpath("//a[contains(@href,'morningstar')]/following-sibling::a").click()
        time.sleep(3)
        if not g.driver.find_elements_by_xpath("//*[contains(text(), 'Permission denied')]"):
            if not g.driver.find_elements_by_xpath("//*[contains(text(), 'Error')]"):
                break



def GetMorningstarData():
    global g

    tmp_json_filename = './tmp/TEST_DATA.json'
    if os.path.isfile(tmp_json_filename):
        with open(tmp_json_filename) as tmp_json_file:
            g.investment_data = json.load(tmp_json_file)
        print('Loaded JSON investment data from ' + tmp_json_filename)
    else:
        for g.current_trading_symbol in g.symbols:
        
            print('Navigating to Morningstar page for ' + g.current_trading_symbol)
            input_field = g.driver.find_element_by_id('AutoCompleteBox')
            input_field.click()
            input_field.send_keys(g.current_trading_symbol)
            input_field.send_keys(Keys.RETURN)
            time.sleep(2)

            if g.driver.find_elements_by_xpath("//*[contains(text(), 'Having difficulties locating your security?')]"):
                print('Morningstar has no data for trading symbol: ' + g.current_trading_symbol)
                continue

            GetMorningstarTaxTabData()

            # Because for some weird reason, sometimes cannot find '^History' node containing performance data,
            # try 3 times (maybe just increase 'sleep' inside of GetMorningstarPerformanceTabData_Annual()?)
            for retries in range(3):
                try:
                    GetMorningstarPerformanceTabData_Annual()
                    break
                except ValueError:
                    print('Failed to find "^History" node in performance data HTML for ' + g.current_trading_symbol + \
                        ' on try #' + str(retries + 1) + '. Retrying...')
                    continue

            GetMorningstarPerformanceTabData_Trailing()
            GetMorningstarDistributionTabData()

    print(g.investment_data)

    json_filename = './tmp/' + g.timestamp + '_investment_data.json'
    with open(json_filename, 'w') as json_file:
        json.dump(g.investment_data, json_file)

    print('Results written to ' + json_filename + '\nDone!')


def GetMorningstarTaxTabData():
    global g

    print('Retrieving tax data for ' + g.current_trading_symbol)

    try:
        tax_tab = g.driver.find_element_by_link_text('Tax')
    except:
        # Some trading symbols are stocks which don't have a "Tax" tab
        print('No tax data for ' + g.current_trading_symbol)
        return

    tax_tab.click()
    time.sleep(3)
    if g.args.emit_debug_html:
        emit_debug_html(g.driver.page_source)
    g.soup = BeautifulSoup(g.driver.page_source.encode('utf-8'), 'html.parser')
    td_elements = g.soup.find('th', text='Tax Cost Ratio').parent. \
        next_sibling.next_sibling.next_sibling.next_sibling.find_all('td')
    StashDataPoint(g.current_trading_symbol, 'Tax Cost Ratios', '1-Yr Tax Cost Ratio', td_elements[4].text)
    StashDataPoint(g.current_trading_symbol, 'Tax Cost Ratios', '3-Yr Tax Cost Ratio', td_elements[5].text)
    StashDataPoint(g.current_trading_symbol, 'Tax Cost Ratios', '5-Yr Tax Cost Ratio', td_elements[6].text)
    StashDataPoint(g.current_trading_symbol, 'Tax Cost Ratios', '10-Yr Tax Cost Ratio', td_elements[7].text)
    StashDataPoint(g.current_trading_symbol, 'Tax Cost Ratios', '15-Yr Tax Cost Ratio', td_elements[8].text)


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
    if IsFloat(datum) and float(datum) != 0.0:
        if symbol not in g.investment_data:
            g.investment_data[symbol] = {}
        if dataset_name not in g.investment_data[symbol]:
            g.investment_data[symbol][dataset_name] = {}
        g.investment_data[symbol][dataset_name][stat_name] = datum + suffix


def GetMorningstarPerformanceTabData_Annual():
    global g

    print('Retrieving performance data for ' + g.current_trading_symbol)

    try:
        performance_tab = g.driver.find_element_by_link_text('Performance')
    except:
        print('No performance data for ' + g.current_trading_symbol)
        return

    performance_tab.click()
    time.sleep(3)
    if g.args.emit_debug_html:
        emit_debug_html(g.driver.page_source)
    g.soup = BeautifulSoup(g.driver.page_source.encode('utf-8'), 'html.parser')
    elems = g.soup(text=re.compile(r'^History'))
    if len(elems) != 1 or elems[0].parent.name != 'th':
        raise ValueError("Errors finding proper 'History' <th> node")
    tr_node = elems[0].parent.parent
    year_intervals = [x.text for x in tr_node.find_all('th')[1:]]
    tbody_node = tr_node.parent.next_sibling.next_sibling
    year_stat_th_nodes = tbody_node.find_all('th')
    output_data = {}
    for year_stat_th_node in year_stat_th_nodes:
        year_stat_name = FixStatName(g.current_trading_symbol, year_stat_th_node.text)
        year_stat_values = [x.text for x in year_stat_th_node.parent.find_all('td')]
        index = 0
        for year_stat_value in year_stat_values:
            if IsFloat(year_stat_value):
                if not year_stat_name in output_data:
                    output_data[year_stat_name] = {}
                output_data[year_stat_name][year_intervals[index]] = year_stat_value
                if year_intervals[index] != 'YTD':
                    year = int(year_intervals[index])
                    if g.perf_data_year_min > year:
                        g.perf_data_year_min = year
                    if g.perf_data_year_max < year:
                        g.perf_data_year_max = year
            index += 1

    StashDataSet(g.current_trading_symbol, 'Annual Returns', output_data)

    #if g.current_trading_symbol in output_data:
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Total Return %',
    #        output_data[g.current_trading_symbol], '%')
    #else:
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Total Return %',
    #        output_data[g.current_trading_symbol + ' (NAV)'], '%')

    #if 'Dividend Yield %' in output_data:
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Dividend Yield %',
    #        output_data['Dividend Yield %'], '%')
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Taxable Distribution Yield %',
    #        output_data['Dividend Yield %'], '%')

    #if 'Income USD' in output_data:
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Income', output_data['Income USD'])

    #if 'Capital Gains USD' in output_data:
    #    StashDataRow(g.current_trading_symbol, 'Annual Returns', 'Capital Gain', output_data['Capital Gains USD'])


def GetMorningstarPerformanceTabData_Trailing():
    global g

    print('Retrieving trailing performance data for ' + g.current_trading_symbol)

    try:
        monthly_tab = g.driver.find_element_by_link_text('Monthly')
    except:
        print('No monthly data for ' + g.current_trading_symbol)
        return

    monthly_tab.click()
    time.sleep(3)
    if g.args.emit_debug_html:
        emit_debug_html(g.driver.page_source)

    g.soup = BeautifulSoup(g.driver.page_source.encode('utf-8'), 'html.parser')
    trp = g.soup(text=re.compile(r'Total Return %'))
    if len(trp) < 1 or trp[len(trp)-1].parent.name != 'th':
        raise ValueError("Error finding proper 'Total Return %' <th> node")

    parent_text = trp[len(trp)-1].parent.text

    # Get data "as of" date (close of market)
    match = re.search(r'(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<year>[0-9]+)', parent_text)
    if match is not None:
        date_string = 'Trailing Returns As Of ' + match.group('month') + '/' + match.group('day') + '/' + \
            match.group('year')
    else:
        return_as_of = g.soup(text=re.compile(r'return as of'))
        return_as_of_string = return_as_of[len(return_as_of)-1].parent.text
        match = re.search(r'(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<year>[0-9]+)', return_as_of_string)
        if match is not None:
            date_string = 'Trailing returns as of ' + match.group('month') + '/' + match.group('day') + '/' + \
                match.group('year')
        else:
            date_string = 'Trailing returns as of <unknown date...see file timestamp for approximate>'

    tr_node = trp[len(trp)-1].parent.parent
    intervals = [x.text for x in tr_node.find_all('th')[1:]]
    tbody_node = tr_node.parent.next_sibling.next_sibling
    stat_th_nodes = tbody_node.find_all('th')
    output_data = {}
    for stat_th_node in stat_th_nodes:
        stat_name = FixStatName(g.current_trading_symbol, stat_th_node.text)
        stat_values = [x.text for x in stat_th_node.parent.find_all('td')]
        index = 0
        for stat_value in stat_values:
            if IsFloat(stat_value):
                if not stat_name in output_data:
                    output_data[stat_name] = {}
                output_data[stat_name][intervals[index]] = stat_value
            index += 1

    StashDataSet(g.current_trading_symbol, date_string, output_data)


def StashDataSet(symbol, dataset_name, data):
    if symbol not in g.investment_data:
        g.investment_data[symbol] = {}
    if dataset_name not in g.investment_data[symbol]:
        g.investment_data[symbol][dataset_name] = {}
    g.investment_data[symbol][dataset_name] = data


def StashDataRow(symbol, dataset_name, stat_name, row_data, suffix=''):
    for key in row_data.keys():
        StashDataSeriesItem(symbol, dataset_name, stat_name, key, row_data[key], suffix)


def GetMorningstarDistributionTabData():
    global g

    print('Retrieving distribution data for ' + g.current_trading_symbol)

    try:
        distributions_tab = g.driver.find_element_by_link_text('Distributions')
    except:
        print('No distribution data for ' + g.current_trading_symbol)
        return

    close_data = GetCloseData(g.current_trading_symbol)
    distributions_tab.click()
    time.sleep(3)
    if g.args.emit_debug_html:
        emit_debug_html(g.driver.page_source)
    g.soup = BeautifulSoup(g.driver.page_source.encode('utf-8'), 'html.parser')
    tbody = g.soup.find("div", {"id": "latestdisList"}).find("table").find("tbody")
    output_data = {}
    for tr in tbody.findAll("tr"):
        th = tr.find("th")
        if th is None:
            continue
        row_label = th.text.strip()
        if re.search('Year to Date', row_label):
            row_label = 'YTD'
        data_entries = [x.text.strip() for x in tr.findAll("td")]
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Income', row_label, data_entries[0])
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Short-Term Capital Gain', row_label,
            data_entries[1])
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Long-Term Capital Gain', row_label,
            data_entries[2])
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Returned Capital', row_label, data_entries[3])
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Total Distributions', row_label,
            data_entries[4])
        StashDataSeriesItem(g.current_trading_symbol, 'Distributions', 'Closing Price', row_label,
            close_data[row_label])


def GetCloseData(s):
    close_data = {}
    curr_year = datetime.datetime.now().year
    retry_num = 1
    while True:
        json_close_data_raw = requests.get('https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&' +
            'symbol=' + s + '&apikey=2QWVG0O8YL2AGWIM').json()
        if not 'Monthly Adjusted Time Series' in json_close_data_raw:
            if re.search('API call volume', str(json_close_data_raw)):
                print('Error!  Exceeded AlphaVantage API call rate. Retrying in 10 secs...')
                time.sleep(10)
            else:
                print('Error!  Unknown AlphaVantage API error.')
                print(str(json_close_data_raw))
                sys.exit(1)
        else:
            json_close_data = json_close_data_raw['Monthly Adjusted Time Series']
            latest_close_date = next(iter(json_close_data))
            close_data['YTD'] = json_close_data[latest_close_date]['4. close']
            for year in range(curr_year - 6, curr_year):
                december_key = GetDecemberKey(json_close_data.keys(), year)
                if december_key is not None:
                    close_data[str(year)] = json_close_data[december_key]['4. close']
            return close_data


def GetDecemberKey(keys, year):
    match_string = '^' + str(year) + '-12'
    for s in keys:
        if re.match(match_string, s):
            return s
    return None


def emit_debug_html(s):
    global g

    if g.debug_html_file is None:
        if not(os.path.isdir('./tmp')):
            print('Temporary directory ' + os.path.abspath('./tmp') + ' must be present to emit debug HTML file. ' \
                'Aborting!')
            sys.exit(1)
        debug_html_filename = './tmp/' + g.timestamp + '_DEBUG.html'
        g.debug_html_file = open(debug_html_filename, 'w')
    g.debug_html_file.write(s)


# Fake class only for purpose of limiting global namespace to the 'g' object
class g:
    args = None
    header_written = False
    driver = None
    symbols = None
    debug_html_file = None
    tax_data_file = None
    performance_data_file = None
    current_trading_symbol = None
    perf_data = {}
    perf_data_year_min = 99999
    perf_data_year_max = 0
    timestamp = None
    soup = None
    dividend_data = {}
    dividend_data_file = None
    investment_data = {}


def main(argv):

    global g

    parser = argparse.ArgumentParser()
    parser.add_argument('--tax-cost-filename', required=False, type=argparse.FileType('w'), 
        help='Output tax cost ratio data TSV filename. Defaults to ./[datetime_stamp]_morningstar_tax_cost_data.tsv')
    parser.add_argument('--performance-filename', required=False, type=argparse.FileType('w'), 
        help='Output tax cost ratio data TSV filename. Defaults to ' \
            './[datetime_stamp]_morningstar_performance_data.tsv')
    parser.add_argument('--dividend-filename', required=False, type=argparse.FileType('w'), 
        help='Output dividend data TSV filename. Defaults to ' \
            './[datetime_stamp]_morningstar_dividend_data.tsv')
    parser.add_argument('--message-output-filename', required=False, help='Filename of message output file. If ' +
        'unspecified, defaults to stderr')
    parser.add_argument('--trading-symbols', required=False, nargs='+',
        help='Market trading symbols of the holding to gather Morningstar info for. E.g. GOOG IVV IBM, etc.')
    parser.add_argument('--symbols-filename', required=False, help='Input file with trading symbol per line.')
    parser.add_argument('--emit-debug-html', action='store_true', help='If specified, then a ' \
        'debug_yyyymmddhhmmss.html file is created to allow Javascript-retrieved HTML to be available for ' \
        'inspection.')
    g.args = parser.parse_args()

    message_level = 'Info'
    util.set_logger(message_level, g.args.message_output_filename, os.path.basename(__file__))

    if g.args.symbols_filename is None and g.args.trading_symbols is None:
        print('NOTE: --trading-symbols and/or --symbols-filename must be specified\n')
        parser.print_help()
        sys.exit(0)

    g.timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    LoadMorningstarMain()
    time.sleep(3)
    GetMorningstarData()

    if g.debug_html_file is not None:
        g.debug_html_file.close()

    g.driver.quit()
    util.sys_exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
