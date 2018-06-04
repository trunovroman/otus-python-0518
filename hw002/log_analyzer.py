# log_format ui_short '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import os
import argparse
import json
import gzip
import re
import logging
import time
import sys
from collections import namedtuple
import copy
from string import Template
import datetime

CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "PATTERN_FILE_PATH": "./report.html",
    "ERROR_PERCENT": 10,
    "ROUND_PLACES": 3,
    "LOGGING_LEVEL": "INFO",
    "LOG_FILE_MASK": "(nginx-access-ui.log-(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})(\.gz)?$)",
    "LOGGER_FILE_PATH": ""
}

FORMAT_LINE = re.compile(
    r"(\"(GET|POST|HEAD|PUT|OPTIONS) (?P<url>.+) HTTP/\d\.\d\")"
    r"(.*)"
    r"(\" (?P<request_time>\d+\.\d+))",
    re.IGNORECASE
)


def main(default_config):
    # Define command-line arguments
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--config",
        type=str,
        default="./config.json",
        help="Path to external JSON configuration file")

    # Read command-line arguments
    args = parser.parse_args()
    json_file_path = args.config

    # Load and merge configuration
    cfg = load_config(default_config, json_file_path)

    # Configure the root logger
    configure_logger(cfg["LOGGER_FILE_PATH"], cfg["LOGGING_LEVEL"])

    # Start
    logging.info("-------------------------------------------------------")
    logging.info("Started")
    start_time = time.time()

    # Find log file. Return namedtuple("File", "file_path log_date")
    try:
        log_file = get_log_file(cfg["LOG_DIR"], cfg["LOG_FILE_MASK"])
    except FileNotFoundError as ex:
        logging.info(ex)
        return

    # Return report file path
    try:
        report_file_path = get_report_path(log_file.log_date, cfg["REPORT_DIR"])
    except FileExistsError as ex:
        logging.info(ex)
        return

    # Parse logs. Return namedtuple("ParseData", "data error_message")
    parsed_data = parse_log(log_file.file_path, cfg["ERROR_PERCENT"])
    if parsed_data.error_message:
        logging.error(parsed_data.error_message)
        sys.exit(1)

    # Calculate statistics
    statistics = calculate_statistic(parsed_data.data, cfg["ROUND_PLACES"], cfg["REPORT_SIZE"])

    # Generate report
    generate_report(statistics, report_file_path, cfg["PATTERN_FILE_PATH"])

    # End
    logging.info("Finished in {0} seconds".format(round(time.time() - start_time)))


def load_config(default_config, json_file_path):
    with open(json_file_path, "rt") as f:
        config_from_file = json.load(f)

    result = copy.deepcopy(default_config)

    # Copy values from file with type-checking
    for prm, value in config_from_file.items():
        result[prm] = type(result[prm])(value)

    # Do some data modifications
    # 1. Log level
    logging_level_attr = "LOGGING_LEVEL"
    allowed_log_level_values = {"INFO": logging.INFO, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
    result[logging_level_attr] = allowed_log_level_values[result[logging_level_attr]]

    # 2. Logger file path
    result["LOGGER_FILE_PATH"] = result["LOGGER_FILE_PATH"] or None

    return result


def configure_logger(logger_file_path, logging_level):
    if logger_file_path is not None:
        os.makedirs(os.path.dirname(logger_file_path), exist_ok=True)  # Создаем папку для логов, если ее нет
    logging.basicConfig(
        filename=logger_file_path,
        level=logging_level,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S")


def get_report_path(log_date, report_dir):
    # Construct report file name
    date_string = log_date.strftime("%Y%m%d")
    report_file_path = os.path.join(report_dir, "report-{0}.html".format(date_string))

    # Check if exists
    if os.path.isfile(report_file_path):
        raise FileExistsError("Report file {0} already exists".format(report_file_path))
    else:
        return report_file_path


def generate_report(statistics, report_file_path, pattern_path):
    json_str = json.dumps(statistics)

    with open(pattern_path, "rt") as file_in:
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, "w") as file_out:
            template = Template(file_in.read())
            file_out.write(template.safe_substitute(table_json=json_str))

    logging.info("Report {0} created".format(report_file_path))


def parse_log(log_file_path, error_percent):
    ParseData = namedtuple("ParseData", "data error_message")

    # Variables to calculate parsing error percent
    total_lines = 0
    error_lines = 0

    # 1. Parse file and load data into dict of the following structure:
    # {
    #     "http://any_url.com/test": [0.013, 0.21, 1.1, 18.002],
    #     "http://another_url.com": [0.1, 0.102]
    # }
    data = {}
    for parsed_line in parser_reader(log_file_path):
        total_lines += 1
        if parsed_line:
            data.setdefault(parsed_line["url"], []).append(float(parsed_line["request_time"]))
        else:
            error_lines += 1

    # Calculate the percent of parsing errors
    if error_lines / total_lines * 100 > error_percent:
        return ParseData(data, "The percent of parsing errors exceeded {0}% limit".format(error_percent))
    else:
        return ParseData(data, None)


def parser_reader(log_file_path):
    with gzip.open(log_file_path, 'rt') if log_file_path.endswith(".gz") else open(log_file_path) as file:
        for l in file:
            yield re.search(FORMAT_LINE, l)


def calculate_statistic(data, round_places, report_size):
    # 1. Calculate statistics and save it into following structure:
    # [
    #     {
    #         "url": "http://any_url.com/test",
    #         "count": 1023,
    #         "count_percent": 0.12,
    #         "time_sum": 123.23,
    #         "time_percent": 10.2,
    #         "time_avg": 10,
    #         "time_max": 102,
    #         "time_median": 5
    #     },
    #     {
    #         "url": "http://another_url.com/test",
    #         ...
    #     }
    # ]
    #
    # 1.1. Calculate count, time_sum, time_avg, time_max, time_median for each URL and total_count, total_time_sum
    statistics = []
    total_count = 0
    total_time_sum = 0
    for url, time_percent_list in data.items():
        count = len(time_percent_list)
        time_sum = sum(time_percent_list)
        total_count += count
        total_time_sum += time_sum
        if count % 2 == 0:
            time_median = sum(sorted(time_percent_list)[(count // 2) - 1:(count // 2) + 1]) / 2
        else:
            time_median = sorted(time_percent_list)[count // 2]
        statistics.append({
            "url": url,
            "count": count,
            "time_sum": time_sum,
            "time_avg": time_sum / count,
            "time_max": max(time_percent_list),
            "time_median": time_median
        })

    # 1.2. Calculate count_percent, time_percent and round all float values
    for value in statistics:
        value["count_percent"] = round(value["count"] / total_count * 100, round_places)
        value["time_percent"] = round(value["time_sum"] / total_time_sum * 100, round_places)
        value["time_sum"] = round(value["time_sum"], round_places)
        value["time_avg"] = round(value["time_avg"], round_places)
        value["time_max"] = round(value["time_max"], round_places)
        value["time_median"] = round(value["time_median"], round_places)

    # Return report_size values sorted by time_sum on descending order
    return sorted(statistics, key=lambda x: x["time_sum"], reverse=True)[:report_size]


def get_log_file(log_dir, log_file_mask):
    File = namedtuple("File", "file_path log_date")

    top_file = None
    for f in os.listdir(log_dir):
        parsed = re.match(log_file_mask, f)
        if os.path.isfile(os.path.join(log_dir, f)) and parsed:
            dt = datetime.datetime(year=int(parsed["year"]), month=int(parsed["month"]), day=int(parsed["day"]))
            current_file = File(file_path=os.path.join(log_dir, f), log_date=dt)
            top_file = max([top_file, current_file], key=lambda x: x.log_date) if top_file else current_file

    if top_file:
        return top_file
    else:
        raise FileNotFoundError('There are no files with mask "{0}" in the folder {1}'.format(log_file_mask, log_dir))


if __name__ == "__main__":
    try:
        main(CONFIG)
    except (Exception, KeyboardInterrupt) as e:
        logging.exception(e)
        sys.exit(1)
