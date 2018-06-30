import json
import datetime
import logging
import hashlib
import uuid
import re
import abc
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
# Exception
# --------------------------------------------------------------------------------------
class ValidationError(Exception):
    pass


# --------------------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------------------
class Field:
    empty_values = ('', [], (), {})

    def __init__(self, required=True, nullable=False):
        self.required, self.nullable = required, nullable

    def validate(self, value):
        if value is None and self.required:
            raise ValidationError("This field is required.")
        if value in self.empty_values and not self.nullable:
            raise ValidationError("Empty value is not allowed.")

    def to_python(self, value):
        return value

    def clean(self, value):
        value = self.to_python(value)
        self.validate(value)
        return value


class CharField(Field):
    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            return str(value).strip()
        else:
            raise ValidationError("This field must be str.")


class ArgumentsField(Field):
    pass


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value is not None and "@" not in value:
            raise ValidationError("Email field must include @.")


class PhoneField(Field):
    regex = re.compile("^7[0-9]{10}$")

    def validate(self, value):
        super().validate(value)
        if value is not None:
            if self.regex.match(value) is None:
                raise ValidationError("Phone number is invalid: {0}.".format(value))

    def to_python(self, value):
        if value is None:
            return None

        if isinstance(value, str) or isinstance(value, int):
            return str(value).strip()
        else:
            raise ValidationError("Phone field must be str or digit.")


class DateField(Field):
    def to_python(self, value):
        if value is None:
            return None

        try:
            return datetime.datetime.strptime(value, "%d.%m.%Y") if value is not None else None
        except ValueError:
            raise ValidationError("Date must be the following format: DD.MM.YYYY.")


class BirthDayField(DateField):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if (datetime.datetime.now() - value).days / 365 > 70:
                raise ValidationError("Birthday must be later than 70 years ago.")


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if value not in GENDERS:
                raise ValidationError("Gender must be equal to {0}".format(list(GENDERS.keys())))

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return int(value)
        else:
            raise ValidationError("This field must be int.")


class ClientIDsField(Field):
    def to_python(self, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValidationError('Field must be a list.')
        for item in value:
            if not isinstance(item, int):
                raise ValidationError('Items must be int.')
        return value


# --------------------------------------------------------------------------------------
# Requests
# --------------------------------------------------------------------------------------
class RequestMetaclass(type):
    def __new__(mcs, name, bases, attributes):
        custom_fields = {}
        for key, value in list(attributes.items()):
            if isinstance(value, Field):
                custom_fields[key] = value
                attributes.pop(key)
        new_class = super().__new__(mcs, name, bases, attributes)
        new_class.fields = custom_fields
        return new_class


class BaseRequest(metaclass=RequestMetaclass):
    def __init__(self, data=None):
        self.data = {} if data is None else data
        self._errors = []

    def clean_fields(self):
        for name, field in self.fields.items():
            try:
                setattr(self, name, field.clean(self.data.get(name, None)))
            except ValidationError as e:
                setattr(self, name, None)
                self._errors.append(e)

    def is_valid(self):
        self._errors = []
        self.clean_fields()

        return True if not len(self._errors) else False

    @property
    def errors(self):
        return str(self._errors)


class ScoringResultRequest(BaseRequest):
    def get_result(self, ctx, store, is_admin):
        if not self.is_valid():
            return self.errors, INVALID_REQUEST

        return self.get_scoring(ctx, store, is_admin)

    @abc.abstractmethod
    def get_scoring(self, ctx, store, is_admin):
        """Return scoring in derivative classes"""


class ClientsInterestsRequest(ScoringResultRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

    def get_scoring(self, ctx, store, is_admin):
        response = {str(cid): scoring.get_interests(store, cid) for cid in self.client_ids}
        ctx['nclients'] = len(self.client_ids)
        return response, OK


class OnlineScoreRequest(ScoringResultRequest):
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

    def check_combinations(self):
        for cmb in self.valid_combinations:
            flag = True
            for field_name in cmb:
                if getattr(self, field_name, None) is None:
                    flag = False
            if flag:
                return True

        raise ValidationError("Online score request must include at least one not null combination: {0}".
                              format(self.valid_combinations))

    def clean_fields(self):
        super().clean_fields()

        try:
            self.check_combinations()
        except ValidationError as e:
            self._errors.append(e)

    def get_not_null_fields(self):
        return [key for key in self.fields if getattr(self, key, None) is not None]

    def get_scoring(self, ctx, store, is_admin):
        if is_admin:
            response = {"score": 42}
        else:
            response = {"score": scoring.get_score(
                store,
                self.phone,
                self.email,
                self.birthday,
                self.gender,
                self.first_name,
                self.last_name,
            )}
        ctx['has'] = self.get_not_null_fields()
        return response, OK


class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT).encode('utf-8')).hexdigest()
    if digest == request.token:
        return True
    return False


# --------------------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------------------
def method_handler(request, ctx, store):
    request_handlers = {
        "online_score": OnlineScoreRequest,
        "clients_interests": ClientsInterestsRequest
    }

    body = request.get("body", None)

    if len(body) == 0:
        return None, INVALID_REQUEST

    method_request = MethodRequest(body)
    if method_request.is_valid():

        if not check_auth(method_request):
            return None, FORBIDDEN

        handler = request_handlers.get(method_request.method, None)
        if handler:
            return handler(method_request.arguments).get_result(ctx, store, method_request.is_admin)
        else:
            return None, NOT_FOUND

    else:
        return method_request.errors, INVALID_REQUEST


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
