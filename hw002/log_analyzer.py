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

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "PATTERN_FILE_PATH": "./report.html",
    "ERROR_PERCENT": 10,
    "ROUND_PLACES": 3,
    "LOGGING_LEVEL": "INFO",
    "LOG_FILE_MASK": "(nginx-access-ui.log-(?P<date>\d{8})(\.gz)?$)",
    "LOGGER_FILE_PATH": ""
}

format_line = re.compile(
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
    log_file = get_log_file(cfg["LOG_DIR"], cfg["LOG_FILE_MASK"])

    # Return report file path
    report_file_path = get_report_path(log_file.log_date, cfg["REPORT_DIR"])

    # Parse logs
    data = parse_log(log_file.file_path, cfg["ERROR_PERCENT"])

    # Calculate statistics
    statistics = calculate_statistic(data, cfg["ROUND_PLACES"], cfg["REPORT_SIZE"])

    # Generate report
    generate_report(statistics, report_file_path, cfg["PATTERN_FILE_PATH"])

    # End
    logging.info("Finished in {0} seconds".format(round(time.time() - start_time)))


def load_config(default_config, json_file_path):
    # Copy config from json object
    result = dict(default_config)

    # Merge config with file
    # 1. Check if file exists
    if not os.path.isfile(json_file_path):
        logging.error("Config file {0} is not found".format(json_file_path))
        sys.exit(1)

    # 2. Try to parse it
    with open(json_file_path, "rt") as f:
        try:
            json_config = json.load(f)
        except ValueError as ex:
            logging.error("Failed to parse config file {0}. Error type: {1}, System message: {2}".format(
                    json_file_path,
                    type(ex).__name__,
                    ex))
            sys.exit(1)

    # 3. Load parameters with type-checking
    for prm in json_config:
        if prm in result:
            if isinstance(json_config[prm], type(result[prm])):
                result[prm] = json_config[prm]
            else:
                # Parameters from object and from file must have the same type
                raise TypeError("Configuration parameter {0} must has type {1}, but it has {2}".format(
                    prm, type(result[prm]), type(json_config[prm])))
        else:
            raise ValueError("Unknown configuration parameter {0}".format(prm))

    # 4. Some data modifications
    # 4.1. Log level
    logging_level_attr = "LOGGING_LEVEL"
    allowed_log_level_values = {"INFO": logging.INFO, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
    if result[logging_level_attr] not in allowed_log_level_values:
        raise ValueError("Allowed values for attribute {0} are: {1}, but it is: {2}".format(
            logging_level_attr, allowed_log_level_values.keys(), result[logging_level_attr]))
    result[logging_level_attr] = allowed_log_level_values[result[logging_level_attr]]

    # 4.2. Logger file path
    if len(result["LOGGER_FILE_PATH"]) == 0:
        result["LOGGER_FILE_PATH"] = None

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
    report_file_path = os.path.join(report_dir, "report-{0}.html".format(log_date))

    # Check if exists
    if os.path.isfile(report_file_path):
        logging.info("Report file {0} already exists".format(report_file_path))
        sys.exit(0)
    else:
        return report_file_path


def generate_report(statistics, report_file_path, pattern_path):
    json_str = json.dumps(statistics)

    with open(pattern_path, "rt") as file_in:
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, "w") as file_out:
            for line in file_in:
                file_out.write(line.replace('$table_json', json_str))

    logging.info("Report {0} created".format(report_file_path))


def parse_log(log_file_path, error_percent):
    if log_file_path.endswith(".gz"):
        logfile = gzip.open(log_file_path, 'rt')
    else:
        logfile = open(log_file_path)

    # Variables to calculate parsing error percent
    total_lines = 0
    error_lines = 0

    # 1. Parse file and load data into dict of the following structure:
    # {
    #     "http://any_url.com/test": [0.013, 0.21, 1.1, 18.002],
    #     "http://another_url.com": [0.1, 0.102]
    # }
    data = {}
    for l in logfile:
        total_lines += 1
        parsed_line = re.search(format_line, l)
        if parsed_line:
            url = parsed_line["url"]
            request_time = float(parsed_line["request_time"])
            if url in data:
                data[url].append(request_time)
            else:
                data[url] = [request_time]
        else:
            error_lines += 1

    logfile.close()

    # Calculate the percent of parsing errors
    if error_lines / total_lines * 100 > error_percent:
        logging.error("The pencent of parsing errors exceeded {0}% limit".format(error_percent))
        sys.exit(1)

    return data


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
    log_files = []
    File = namedtuple("File", "file_path log_date")

    for f in os.listdir(log_dir):
        log_date = re.match(log_file_mask, f)
        if os.path.isfile(os.path.join(log_dir, f)) and log_date:
            log_files.append(File(file_path=os.path.join(log_dir, f), log_date=log_date["date"]))

    if len(log_files) == 0:
        logging.info('There are no files with mask "{0}" in the folder {1}'.format(log_file_mask, log_dir))
        sys.exit(0)
    else:
        top_first_file = sorted(log_files, key=lambda x: x.log_date, reverse=True)[0]
        return top_first_file


if __name__ == "__main__":
    try:
        main(config)
    except (Exception, KeyboardInterrupt) as e:
        logging.exception(e)
        sys.exit(1)
