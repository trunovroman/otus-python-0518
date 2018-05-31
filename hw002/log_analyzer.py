# log_format ui_short '$remote_addr $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

import os
import argparse
import json
import gzip
import re
import inspect
import logging
import time
import sys

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "PATTERN_FILE_PATH": "./report.html",
    "ERROR_PERCENT": 10,
    "ROUND_PLACES": 3,
    "LOG_LEVEL": "INFO",
    "LOG_FILE_MASK": "(nginx-access-ui.log-(?P<date>\d{8}))",
    "LOGGER_FILE_PATH": ""
}

format_line = re.compile(
    r"(\"(GET|POST|HEAD|PUT|OPTIONS) (?P<url>.+) HTTP/\d\.\d\")"
    r"(.*)"
    r"(\" (?P<request_time>\d+\.\d+))",
    re.IGNORECASE
)


def main(json_config):
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
    cfg = Configuration()
    cfg.load_from_object(json_config)
    if json_file_path:
        cfg.load_from_file(json_file_path)

    # Configure root logger
    if cfg.logger_file_path is not None:
        os.makedirs(os.path.dirname(cfg.logger_file_path), exist_ok=True)  # Создаем папку для логов, если ее нет
    logging.basicConfig(
        filename=cfg.logger_file_path,
        level=cfg.log_level,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S")

    # Start
    logging.info("-------------------------------------------------------")
    logging.info("Started")
    start_time = time.time()

    # Find log path
    log_file_path = get_log_path(cfg.log_dir, cfg.log_file_mask)
    if not log_file_path:
        logging.info('There are no files with mask "{0}" in the folder "{1}"'.format(cfg.log_file_mask, cfg.log_dir))
        return

    # Check and return report file path for log
    report_file_path = get_report_path(log_file_path, cfg.report_dir, cfg.log_file_mask)
    if not report_file_path:
        logging.info("Report for log {0} already exists".format(log_file_path))
        return

    # Parse logs
    json_str = parse_log(log_file_path, cfg.report_size, cfg.error_percent, cfg.round_places)

    # Generate report
    generate_report(json_str, report_file_path, cfg.pattern_file_path)

    # End
    logging.info("Finished in {0} seconds".format(round(time.time() - start_time)))


def get_report_path(log_file_path, report_dir, log_file_mask):
    # Extract date from log file
    d = re.search(log_file_mask, log_file_path)
    if d is None:
        logging.error("Date marker for file {0} has invalid format".format(log_file_path))
        sys.exit(1)

    date = d["date"]

    # Construct report file name
    report_file_path = os.path.join(report_dir, "report-{0}.html".format(date))

    # Check if exists
    if os.path.isfile(report_file_path):
        return None
    else:
        return report_file_path


def generate_report(json_str, report_file_path, pattern_path):
    with open(pattern_path, "rt") as file_in:
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, "w") as file_out:
            for line in file_in:
                file_out.write(line.replace('$table_json', json_str))

    logging.info("Report {0} created".format(report_file_path))


def parse_log(log_file_path, report_size, error_percent, round_places):
    if log_file_path.endswith(".gz"):
        logfile = gzip.open(log_file_path, 'rt')
    else:
        logfile = open(log_file_path)

    # Размер файла нам нужен, чтобы ниже определить относительное количество возникших ошибок парсинга
    file_size = os.path.getsize(log_file_path)

    # Парсим файл, собираем статистику
    error_size = 0
    statistic = URLStatistic(round_places)
    for l in logfile:
        search_result = re.search(format_line, l)
        if search_result:
            url = search_result["url"]
            request_time = float(search_result["request_time"])
            statistic.add_url(url, request_time)
        else:
            # Количество ошибочно пропарсенных байт
            error_size = error_size + len(str.encode(l))
            # Вычисляем процент ошибок парсинга
            if error_size / file_size * 100 > error_percent:
                logging.error("The number of parsing errors exceeded {0}% limit".format(error_percent))
                sys.exit(1)

    logfile.close()
    statistic.clear_cache()

    return json.dumps(statistic.get_items(report_size), cls=PropertyEncoder)


def get_log_path(log_dir, log_file_mask):
    log_files = sorted(
        [f for f in os.listdir(log_dir)
         if os.path.isfile(os.path.join(log_dir, f)) and re.match(log_file_mask, f)],
        reverse=True
    )
    if len(log_files) == 0:
        return None
    else:
        return os.path.join(log_dir, log_files[0])


class cached_property(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, cls=None):
        result = instance.__dict__[self.func.__name__] = self.func(instance)
        return result


class URLStatistic:
    def __init__(self, round_places):
        self._round_places = round_places
        self._container = {}

    def add_url(self, url, request_time):
        # Добавляем URL в контейнер
        if url in self._container:
            self._container[url].add_time(request_time)
        else:
            data = URLData(url, self, self._round_places)
            data.add_time(request_time)
            self._container[url] = data

    @cached_property
    def total_count(self):
        return sum([value.count for key, value in self._container.items()])

    @cached_property
    def total_time_sum(self):
        return sum([value.time_sum for key, value in self._container.items()])

    def get_items(self, count):
        values = self._container.values()
        return sorted(values, key=lambda x: x.time_sum, reverse=True)[:count]

    def clear_cache(self):
        if hasattr(self, "total_count"):
            delattr(self, "total_count")
        if hasattr(self, "total_time_sum"):
            delattr(self, "total_time_sum")


class URLData:
    def __init__(self, url, parent, round_places):
        self._time_list = []
        self._url = url
        self._parent = parent
        self._round_places = round_places

    def add_time(self, request_time):
        self._time_list.append(request_time)

    @property
    def url(self):
        return self._url

    @property
    def count(self):
        return len(self._time_list)

    @property
    def count_percent(self):
        total_count = self._parent.total_count
        return round((self.count / total_count) * 100, self._round_places) if total_count != 0 else 0

    @property
    def time_sum(self):
        return round(sum(self._time_list), self._round_places)

    @property
    def time_percent(self):
        total_time_sum = self._parent.total_time_sum
        return round((self.time_sum / total_time_sum) * 100, self._round_places) if total_time_sum != 0 else 0

    @property
    def time_avg(self):
        c = self.count
        return round(self.time_sum / c, self._round_places) if c != 0 else 0

    @property
    def time_max(self):
        return round(max(self._time_list), self._round_places)

    @property
    def time_median(self):
        count = self.count
        if count % 2 == 0:
            # Для четного количества элементов медиана равна половине суммы двух чисел, которые стоят по середине
            return round(sum(sorted(self._time_list)[(count // 2) - 1:(count // 2) + 1]) / 2, self._round_places)
        else:
            # Для нечетного количества элементов медиана равна элементу в середине списка
            return round(sorted(self._time_list)[count // 2], self._round_places)


class PropertyEncoder(json.JSONEncoder):
    def default(self, obj):
        properties = inspect.getmembers(type(obj), lambda o: isinstance(o, property))
        result = {}
        for prop in properties:
            result[prop[0]] = getattr(obj, prop[0])
        return result


class Configuration:
    def __init__(self):
        self._config = {}

    def __getitem__(self, key):
        if key not in self._config.keys():
            raise KeyError("Config attribute {0} is not defined".format(key))
        return self._config[key]

    def load_from_object(self, json_config):
        for prm in json_config:
            self._config[prm] = json_config[prm]

    def load_from_file(self, json_file_path):
        if not os.path.isfile(json_file_path):
            logging.error("Config file {0} is not found".format(json_file_path))
            sys.exit(1)

        with open(json_file_path, "rt") as f:
            try:
                json_config = json.load(f)
                for prm in json_config:
                    self._config[prm] = json_config[prm]
            except ValueError as ex:
                logging.error("Failed to parse config file {0}. Error type: {1}, System message: {2}".format(
                        json_file_path,
                        type(ex).__name__,
                        ex))
                sys.exit(1)

    def get_attr_value(self, attr, attr_type):
        value = self[attr]
        if not isinstance(value, attr_type):
            raise TypeError("Config attribute {0} must be {1} type".format(attr, value))
        else:
            return value

    @property
    def log_dir(self):
        return self.get_attr_value("LOG_DIR", str)

    @property
    def report_size(self):
        return self.get_attr_value("REPORT_SIZE", int)

    @property
    def report_dir(self):
        return self.get_attr_value("REPORT_DIR", str)

    @property
    def pattern_file_path(self):
        return self.get_attr_value("PATTERN_FILE_PATH", str)

    @property
    def logger_file_path(self):
        value = self.get_attr_value("LOGGER_FILE_PATH", str)
        if len(value) == 0:
            return None
        else:
            return value

    @property
    def error_percent(self):
        attr = "ERROR_PERCENT"
        value = self.get_attr_value(attr, int)
        if value > 100 or value < 0:
            raise ValueError(
                "Config attribute {0} must be greater than 0 and less then 100, but it is {1}".format(
                    attr, value))
        return value

    @property
    def round_places(self):
        attr = "ROUND_PLACES"
        value = self.get_attr_value(attr, int)
        if value < 0:
            raise ValueError(
                "Config attribute {0} must be greater than 0, but it is {1}".format(
                    attr, value))
        return value

    @property
    def log_file_mask(self):
        attr = "LOG_FILE_MASK"
        value = self.get_attr_value(attr, str)
        try:
            re.compile(value)
        except re.error:
            raise TypeError("Config attribute {0} is incorrect regular expression: {1}".format(attr, value))
        return value

    @property
    def log_level(self):
        attr = "LOG_LEVEL"
        value = self.get_attr_value(attr, str)
        allowed_values = {"INFO": logging.INFO, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL}
        if value not in allowed_values.keys():
            raise ValueError("Allowed values for attribute {0} are: {1}, but it value is: {2}".format(
                attr, allowed_values.keys(), value))

        return allowed_values[value]


if __name__ == "__main__":
    try:
        main(config)
    except (Exception, KeyboardInterrupt) as e:
        logging.exception(e)
        sys.exit(1)
