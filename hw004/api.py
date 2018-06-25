import json
import datetime
import logging
import hashlib
import uuid
import re
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler

import scoring

SALT = "Otus"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}
ADMIN_LOGIN = "admin"


# --------------------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------------------
class Field:
    empty_values = ('', [], (), {})

    def __init__(self, required=True, nullable=False):
        self.required, self.nullable = required, nullable

    def validate(self, value):
        if value is None and self.required:
            raise Exception("This field is required.")
        if value in self.empty_values and not self.nullable:
            raise Exception("Empty value is not allowed.")

    def to_python(self, value):
        return value

    def clean(self, value):
        self.validate(value)
        return self.to_python(value)


class CharField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, str):
            raise Exception("This field must be str.")


class ArgumentsField(Field):
    pass


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value is not None and "@" not in value:
            raise Exception("Email field must include @.")


class PhoneField(Field):
    regex = re.compile("^7[0-9]{10}$")

    def validate(self, value):
        super().validate(value)
        if value is not None:
            if self.regex.match(str(value)) is None:
                raise Exception("Phone number is invalid: {0}.".format(value))


class DateField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y").date()
            except ValueError:
                return "Date must have format: DD.MM.YYYY."

    def to_python(self, value):
        return datetime.datetime.strptime(value, "%d.%m.%Y") if value is not None else None


class BirthDayField(DateField):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if (datetime.datetime.now() - self.to_python(value)).days / 365 > 70:
                raise Exception("Birthday must be later than 70 years ago.")


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, int):
                raise Exception("Gender must be a digit.")
            if int(value) not in GENDERS:
                raise Exception("Gender must be equal to {0}".format(list(GENDERS.keys())))


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list):
            raise Exception('Field must be a list.')
        for item in value:
            if not isinstance(item, int):
                raise Exception('Items must be int.')


# --------------------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------------------
class RequestMetaclass(type):
    def __new__(mcs, name, bases, attributes):
        custom_fields = []
        for key, value in list(attributes.items()):
            if isinstance(value, Field):
                custom_fields.append((key, value))
        new_class = type.__new__(mcs, name, bases, attributes)
        new_class.fields = custom_fields
        return new_class


class BaseRequest(metaclass=RequestMetaclass):
    def __init__(self, data=None):
        self.data = {} if data is None else data
        self.cleaned_data = {}
        self.errors = []

    def __getitem__(self, item):
        return self.cleaned_data[item]

    def is_valid(self):
        self.cleaned_data = {}
        self.errors = []
        for name, field in self.fields:
            try:
                value = self.data.get(name, None)
                self.cleaned_data[name] = field.clean(value)
            except Exception as e:
                self.errors.append('Field: {0}. {1}'.format(name, e))
        return True if not len(self.errors) else False


class ClientsInterestsRequest(BaseRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(BaseRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)
    valid_combinations = [
        ["phone", "email"],
        ["first_name", "last_name"],
        ["gender", "birthday"]
    ]

    def is_valid(self):
        is_valid = super().is_valid()
        if not is_valid:
            return is_valid

        for cmb in self.valid_combinations:
            flag = True
            for field_name in cmb:
                if self.cleaned_data.get(field_name) is None:
                    flag = False
            if flag:
                return True

        self.errors.append("Online score request must include at least one not null combination: {0}"
                           .format(self.valid_combinations))
        return False

    def get_not_null_fields(self):
        return [key for key, value in self.cleaned_data.items() if value is not None]


class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self['login'] == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request['account'] + request['login'] + SALT).encode('utf-8')).hexdigest()
    if digest == request['token']:
        return True
    return False


# --------------------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------------------
def method_handler(request, ctx, store):
    # 1 — Error: empty request
    # 2 — Error: request is not empty, method request is valid but auth is bad
    # 3 — Error: request is not empty but data for method request is invalid
    # 4 — Error: request is not empty, method request is valid, auth is valid but client request is invalid
    # 5 — Error: request is not empty, method request is valid, auth is valid but online score request is invalid
    # 6 — Error: invalid method name
    # 7 — OK: client request is valid
    # 8 — OK: online score request is valid

    body = request.get('body', None)

    if len(body) == 0:
        return None, INVALID_REQUEST  # 1

    method_request = MethodRequest(body)
    if method_request.is_valid():
        if not check_auth(method_request):
            return None, FORBIDDEN  # 2

        method = method_request['method']
        if method == 'online_score':

            online_score = OnlineScoreRequest(method_request['arguments'])
            if online_score.is_valid():
                if method_request.is_admin:
                    response = {"score": 42}
                else:
                    response = {"score": scoring.get_score(
                        store,
                        online_score['phone'],
                        online_score['email'],
                        online_score['birthday'],
                        online_score['gender'],
                        online_score['first_name'],
                        online_score['last_name'],
                    )}
                ctx['has'] = online_score.get_not_null_fields()
                return response, OK  # 8
            else:
                return online_score.errors, INVALID_REQUEST  # 5

        elif method == 'clients_interests':

            clients_interests = ClientsInterestsRequest(method_request['arguments'])
            if clients_interests.is_valid():
                response = {str(cid): scoring.get_interests(store, cid) for cid in clients_interests['client_ids']}
                ctx['nclients'] = len(clients_interests['client_ids'])
                return response, OK  # 7
            else:
                return clients_interests.errors, INVALID_REQUEST  # 4

        else:
            return None, NOT_FOUND  # 6
    else:
        return method_request.errors, INVALID_REQUEST  # 3


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except Exception as e:
            code = BAD_REQUEST
            response = str(e)

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
