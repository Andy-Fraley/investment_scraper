#!/usr/bin/env python

import logging
import os
#import ConfigParser
import configparser
import string
import sys
import re
import tempfile


def sys_exit(level=0):
    logging.shutdown()
    sys.exit(level)


def set_logger(message_level='Warning', message_output_filename=None, program_filename=None):
    # Set logging level
    if message_level is not None:
        if message_level not in ['Info', 'Warning', 'Error']:
            logging.error("Specified message level '" + str(message_level) +
                "' must be 'Info', 'Warning', or 'Error'")
            sys.exit(1)
    else:
        message_level = 'Warning'
    logging_map = {
        'Info': logging.INFO,
        'Warning': logging.WARNING,
        'Error': logging.ERROR
    }
    logging.getLogger().setLevel(logging_map[message_level])

    # Set output filename (or leave as stderr) and format
    if message_output_filename is not None:
        if program_filename is not None:
            if program_filename[-3:] == '.py':
                program_filename = program_filename[:-3]
            logging.basicConfig(filename=message_output_filename, format='%(asctime)s:%(levelname)s:' +
                program_filename + ':%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        else:
            logging.basicConfig(filename=message_output_filename, format='%(asctime)s:%(levelname)s:%(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
