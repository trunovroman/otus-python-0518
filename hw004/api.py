import json
import datetime
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
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


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request['account'] + request['login'] + SALT).encode('utf-8')).hexdigest()
    if digest == request['token']:
        return True
    return False


def method_handler(request, ctx, store):
    # 1 — Error: empty request
    # 2 — Error: request is not empty, method request is valid but auth is bad
    # 3 — Error: request is not empty but data for method request is invalid
    # 4 — Error: request is not empty, method request is valid, auth is valid but client request is invalid
    # 5 — Error: request is not empty, method request is valid, auth is valid but online score request is invalid
    # 6 — OK: client request is valid
    # 7 — OK: online score request is valid

    body = request.get('body', None)

    if len(body) == 0:
        return None, INVALID_REQUEST  # 1

    method_request = requests.MethodRequest(body)

    if method_request.is_valid():
        if not check_auth(method_request):
            return None, FORBIDDEN  # 2

        method = method_request['method']
        if method == 'online_score':

            online_score = requests.OnlineScoreRequest(method_request['arguments'])

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
                return response, OK  # 7

            else:
                return online_score.errors, INVALID_REQUEST  # 5

        elif method == 'clients_interests':
            clients_interests = requests.ClientsInterestsRequest(method_request['arguments'])

            if clients_interests.is_valid():
                response = {str(cid): scoring.get_interests(store, cid) for cid in clients_interests['client_ids']}
                ctx['nclients'] = len(clients_interests['client_ids'])
                return response, OK  # 6
            else:
                return clients_interests.errors, INVALID_REQUEST  # 4

        else:
            print('Wrong value')
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
