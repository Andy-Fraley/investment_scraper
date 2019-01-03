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
import csv


def ListDatasets(investment_json_filename):
    investment_data = json.load(investment_json_filename)
    dataset_names = []
    for trading_symbol in investment_data:
        for dataset_name in investment_data[trading_symbol]:
            if dataset_name not in dataset_names:
                dataset_names.append(dataset_name)
    if len(dataset_names) > 0:
        dataset_names.sort()
        print('Datasets:')
        for dataset_name in dataset_names:
            print(dataset_name)
    else:
        print('Strange. Data has no datasets')
    return


def DictionaryDepth(d, level=1):
    if not isinstance(d, dict) or not d:
        return level
    return max(DictionaryDepth(d[k], level + 1) for k in d)


def Dataset2StringName(dataset):
    s = dataset.replace('%', 'perc')
    s = s.replace(' ', '_')
    s = s.replace('/', '_')
    return s.lower()


def ExtractTimestampPrefix(s):
    m = re.search('([0-9]{14})_', s)
    if m:
        return m.group(0)
    else:
        return ''


def ExtractDataset2CsvFile(investment_json_filename, extract_dataset):
    dataset_stringname = Dataset2StringName(extract_dataset)
    timestamp_prefix = ExtractTimestampPrefix(investment_json_filename.name)
    investment_data = json.load(investment_json_filename)
    found_data = False
    output_csv_file = csv.writer(open('./tmp/' + timestamp_prefix + dataset_stringname + '.csv', 'w'))
    for trading_symbol in investment_data:
        for dataset_name in investment_data[trading_symbol]:
            if dataset_name == extract_dataset:
                found_data = True
                dataset_stringname = Dataset2StringName(dataset_name)
                dataset_depth = DictionaryDepth(investment_data[trading_symbol][dataset_name])
                if dataset_depth == 3:
                    for stat_name in investment_data[trading_symbol][dataset_name]:
                        for timeperiod in investment_data[trading_symbol][dataset_name][stat_name]:
                            output_csv_file.writerow([str(trading_symbol), str(stat_name), str(timeperiod),
                                str(investment_data[trading_symbol][dataset_name][stat_name][timeperiod])])
                elif dataset_depth == 2:
                    for stat_name in investment_data[trading_symbol][dataset_name]:
                            output_csv_file.writerow([str(trading_symbol), str(stat_name),
                                str(investment_data[trading_symbol][dataset_name][stat_name])])
    return


# Fake class only for purpose of limiting global namespace to the 'g' object
class g:
    args = None


def main(argv):

    global g

    parser = argparse.ArgumentParser()
    parser.add_argument('--extract-dataset', required=False, help='Name of dataset in the input JSON file to ' \
        'extract into output CSV file.  NOTE: Output file will be timestamped derivative of input JSON file and ' \
        'dataset name.')
    parser.add_argument('--list-datasets', action='store_true', help='If specified, overrides all other flags and ' \
        'opens input JSON file and dumps list of datasets found in the file.')
    parser.add_argument('--investment-json-filename', required=False, type=argparse.FileType('r'), 
        help='Name of input JSON file containing investment data retrieved using get_investment_data.py')
    parser.add_argument('--message-output-filename', required=False, help='Filename of message output file. If ' +
        'unspecified, defaults to stderr')
    g.args = parser.parse_args()

    message_level = 'Info'
    util.set_logger(message_level, g.args.message_output_filename, os.path.basename(__file__))

    if not ( g.args.list_datasets and g.args.investment_json_filename is not None) and \
       (g.args.investment_json_filename is None or g.args.extract_dataset is None):
        print('NOTE: Must specify either (--investment-json-filename and --list-datasets) or '\
            '(--investment-json-filename and --extract-dataset)')
        parser.print_help()
        util.sys_exit(0)

    if g.args.list_datasets:
        ListDatasets(g.args.investment_json_filename)
    else:
        ExtractDataset2CsvFile(g.args.investment_json_filename, g.args.extract_dataset)

    util.sys_exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
