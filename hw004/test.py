import hashlib
import pytest
from unittest import mock
import redis
import docker
import datetime
import time
import redis.connection

import scoring
import store
import api

docker_config = {
    "host_name": "localhost",
    "inside_port": 6379,
    "host_port": 6379,
    "container_name": "redis",
    "image_name": "redis:latest",
}

redis_config = {
    "host_name": "localhost",
    "port": 6379,
    "db": 0,
    "connect_timeout": 1,
    "reconnect_attempts": 5,
    "reconnect_delay": 0
}


def setup_module():
    run_docker_container()
    check_redis_connection()


def teardown_module():
    stop_docker_container()


def check_redis_connection():
    rd = get_redis()
    rd.info()


def get_redis():
    return redis.StrictRedis(
        host=redis_config["host_name"],
        port=redis_config["port"],
        db=redis_config["db"],
        decode_responses=True)


def stop_docker_container():
    client = docker.from_env()
    try:
        running_container = client.containers.get(docker_config["container_name"])
        running_container.remove(force=True)
    except docker.errors.NotFound:
        pass


def run_docker_container():
    stop_docker_container()

    client = docker.from_env()
    client.containers.run(
        hostname=docker_config["host_name"],
        ports={"{0}/tcp".format(docker_config["inside_port"]): docker_config["host_port"]},
        name=docker_config["container_name"],
        image=docker_config["image_name"],
        detach=True)


# ----------------
# Scoring
# ----------------
class TestScoring:
    def get_store(self):
        return store.Store(
            redis_config["host_name"],
            redis_config["port"],
            redis_config["db"],
            redis_config["connect_timeout"],
            redis_config["reconnect_attempts"],
            redis_config["reconnect_delay"]
        )

    @pytest.mark.parametrize("error", [redis.TimeoutError, redis.ConnectionError])
    @pytest.mark.parametrize("kwargs", [
        ({"phone": 79104823345, "email": "test@test.ru", "birthday": datetime.datetime(1981, 10, 10), "gender": 1,
          "first_name": "Иван", "last_name": "Петров"})
    ])
    def test_exception_get_score(self, error, kwargs):
        """scoring.get_score не падает при недоступности хранилища"""

        st = self.get_store()
        st.redis.execute_command = mock.PropertyMock(side_effect=error)  # mock execute_command to raise exception

        try:
            scoring.get_score(st, **kwargs)
        except error as e:
            pytest.fail("Unexpected error {0}".format(type(e)))

    @pytest.mark.parametrize("kwargs, score", [
        ({"phone": 79104823345, "email": None}, 1.5),
        # ({"phone": 79104823345, "email": "bill.gates@microsoft.com"}, 3), потому что баг лютейший!!!
        ({"phone": "783977266345", "email": "steve.wozniak@apple.com", "birthday": datetime.datetime(1950, 8, 11),
          "gender": 1}, 4.5),
        ({"phone": "783977266345", "email": "elon.musk@tesla.com", "birthday": datetime.datetime(1971, 6, 28),
          "gender": 1, "first_name": "Elon", "last_name": "Musk"}, 5),
    ])
    def test_ok_get_score(self, kwargs, score):
        """Проверка вычислений scoring.get_score"""

        st = self.get_store()
        assert scoring.get_score(st, **kwargs) == score

    @pytest.mark.parametrize("error", [redis.TimeoutError, redis.ConnectionError])
    @pytest.mark.parametrize("cid", [1])
    def test_exception_get_interest(self, error, cid):
        """scoring.get_interests падает при недоступности хранилища"""

        st = self.get_store()
        st.redis.execute_command = mock.PropertyMock(side_effect=error)  # mock execute_command to raise exception

        try:
            scoring.get_interests(st, cid)
            pytest.fail("Exception expected")
        except error as e:
            assert True

    @pytest.mark.parametrize("key, values", [
        ("43", ["cars", "pets", "travel"]),
        ("1", ["котики", "собачки", "zombie"]),
    ])
    def test_ok_get(self, key, values):
        st = self.get_store()

        st.redis.delete(key)
        st.redis.rpush("i:{0}".format(key), *values)

        assert scoring.get_interests(st, key) == values


# ----------------
# Score
# ----------------
class TestScore:
    def get_store(self, reconnect_attempts=None, reconnect_delay=None):
        return store.Store(
            redis_config["host_name"],
            redis_config["port"],
            redis_config["db"],
            redis_config["connect_timeout"],
            reconnect_attempts or redis_config["reconnect_attempts"],
            reconnect_delay or redis_config["reconnect_delay"]
        )

    def test_ok_cache_set_get(self):
        """Кэш в Store.cache_set и Store.cache_get работает"""

        key = "1"
        value = 123
        expire = 100

        st = self.get_store()
        st.cache_set(key, value, expire)

        assert st.cache_get(key) == value

    def test_ok_cache_expire(self):
        """Проверяем, что кэш очищается по истечению времени expire"""

        key = "1"
        value = 123
        expire = 1

        st = self.get_store()
        st.cache_set(key, value, expire)

        time.sleep(0.1)  # Знаю, что это плохой тон, но тут надо проверить expire
        assert st.cache_get(key) == value
        time.sleep(1.1)
        assert st.cache_get(key) is None

    @pytest.mark.parametrize("error", [redis.TimeoutError, redis.ConnectionError])
    @pytest.mark.parametrize("cid", [1])
    def test_ok_reconnect(self, error, cid):
        """Проверяем, что при соответствующей настройке таймаутов попытки реконнекта продолжаются какое-то время"""

        attempts = 2
        delay = 0.6

        st = self.get_store(reconnect_attempts=attempts, reconnect_delay=delay)
        st.redis.execute_command = mock.PropertyMock(side_effect=error)  # mock execute_command to raise exception

        start = datetime.datetime.now()
        try:
            scoring.get_interests(st, cid)
            pytest.fail("Exception expected")
        except error:
            end = datetime.datetime.now()
            assert (end - start).total_seconds() >= attempts * delay


# ----------------
# Fields
# ----------------
@pytest.mark.parametrize("value", [(), "", {}, [], None])
def test_invalid_field(value):
    field = api.Field(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("value", [(), "", {}, [], None])
def test_ok_field(value):
    field = api.Field(required=False, nullable=True)
    try:
        field.clean(value)
        assert True
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", [1, ("1", "2"), ["1"], {"key": 123}])
def test_invalid_char_field(value):
    field = api.CharField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("value", ["1", "привет"])
def test_ok_char_field(value):
    field = api.CharField(required=True, nullable=False)
    try:
        assert field.clean(value) == value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", ["gmail.com", "mail.ru"])
def test_invalid_email_field(value):
    field = api.EmailField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("value", ["trunovroman@gmail.com", "pickwick@mail.ru"])
def test_ok_email_field(value):
    field = api.EmailField(required=True, nullable=False)
    try:
        assert field.clean(value) == value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", ["7910777336f", "89108887766", 89106665544])
def test_invalid_phone_field(value):
    field = api.PhoneField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("input_value, output_value", [
    ("79107775599", "79107775599"),
    (79163332211, "79163332211")
])
def test_ok_phone_field(input_value, output_value):
    field = api.PhoneField(required=True, nullable=False)
    try:
        assert field.clean(input_value) == output_value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", ["31.06.2018", "wegwqegwg"])
def test_invalid_date_field(value):
    field = api.DateField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("str_value, date_value", [
    ("20.01.2018", datetime.datetime(2018, 1, 20)),
    ("29.02.2016", datetime.datetime(2016, 2, 29))
])
def test_ok_date_field(str_value, date_value):
    field = api.DateField(required=True, nullable=False)
    try:
        assert field.clean(str_value) == date_value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", ["01.01.1911"])
def test_invalid_birthday_field(value):
    field = api.BirthDayField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("str_value, date_value", [("01.01.1990", datetime.datetime(1990, 1, 1))])
def test_ok_date_field(str_value, date_value):
    field = api.DateField(required=True, nullable=False)
    try:
        assert field.clean(str_value) == date_value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", [-1, 3, "0", "1", "2"])
def test_invalid_gender_field(value):
    field = api.GenderField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("input_value, output_value", [
    (0, api.UNKNOWN),
    (1, api.MALE),
    (2, api.FEMALE),
])
def test_ok_date_field(input_value, output_value):
    field = api.GenderField(required=True, nullable=False)
    try:
        assert field.clean(input_value) == output_value
    except api.ValidationError:
        pytest.fail("Unexpected error")


@pytest.mark.parametrize("value", [{1, 2, 3}, [1., 23.4], ["1", 1], 1, "sadfas", "2", (1, 2)])
def test_invalid_clients_id_field(value):
    field = api.ClientIDsField(required=True, nullable=False)
    try:
        field.clean(value)
        pytest.fail("ValidationError expected")
    except api.ValidationError:
        assert True


@pytest.mark.parametrize("value", [[1, 2, 3, 4, 5]])
def test_ok_client_id_field(value):
    field = api.ClientIDsField(required=True, nullable=False)
    try:
        assert field.clean(value) == value
    except api.ValidationError:
        pytest.fail("Unexpected error")


# ----------------
# Get Response — то, что осталось из прошлой домашки
# ----------------
class TestSuiteGetResponse:
    def setup(self):
        self.context = {}
        self.headers = {}
        self.settings = {}

    def get_response(self, request):
        return api.method_handler({"body": request, "headers": self.headers}, self.context, self.settings)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode('utf-8')).hexdigest()

    def test_empty_request(self):
        _, code = self.get_response({})
        assert api.INVALID_REQUEST == code

    @pytest.mark.parametrize(
        "request",
        [
            {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "", "arguments": {}},
            {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "sdd", "arguments": {}},
            {"account": "horns&hoofs", "login": "admin", "method": "online_score", "token": "", "arguments": {}},
        ])
    def test_bad_auth(self, request):
        _, code = self.get_response(request)
        assert api.FORBIDDEN == code

    @pytest.mark.parametrize(
        "request",
        [
            {"account": "horns&hoofs", "login": "h&f", "method": "online_score"},
            {"account": "horns&hoofs", "login": "h&f", "arguments": {}},
            {"account": "horns&hoofs", "method": "online_score", "arguments": {}},
        ])
    def test_invalid_method_request(self, request):
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        assert api.INVALID_REQUEST == code
        assert len(response)

    @pytest.mark.parametrize(
        "arguments",
        [
            {},
            {"phone": "79175002040"},
            {"phone": "89175002040", "email": "stupnikov@otus.ru"},
            {"phone": "79175002040", "email": "stupnikovotus.ru"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": -1},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": "1"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.1890"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "XXX"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000", "first_name": 1},
            {"phone": "79175002040", "email": "stupnikov@otus.ru", "gender": 1, "birthday": "01.01.2000",
             "first_name": "s", "last_name": 2},
            {"phone": "79175002040", "birthday": "01.01.2000", "first_name": "s"},
            {"email": "stupnikov@otus.ru", "gender": 1, "last_name": 2},
        ])
    def test_invalid_score_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        assert api.INVALID_REQUEST == code, arguments
        assert len(response)

    def test_ok_score_admin_request(self):
        arguments = {"phone": "79175002040", "email": "stupnikov@otus.ru"}
        request = {"account": "horns&hoofs", "login": "admin", "method": "online_score", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        assert api.OK == code
        score = response.get("score")
        assert score == 42

    @pytest.mark.parametrize(
        "arguments",
        [
            {},
            {"date": "20.07.2017"},
            {"client_ids": [], "date": "20.07.2017"},
            {"client_ids": {1: 2}, "date": "20.07.2017"},
            {"client_ids": ["1", "2"], "date": "20.07.2017"},
            {"client_ids": [1, 2], "date": "XXX"},
        ]
    )
    def test_invalid_interests_request(self, arguments):
        request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        assert api.INVALID_REQUEST == code, arguments
        assert len(response)
