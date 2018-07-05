import redis
import json


class Store:
    def __init__(self, host, port, db, connect_timeout, reconnect_attempts):
        self.reconnect_attempts = reconnect_attempts
        self.redis = redis.StrictRedis(host=host, port=port, db=db, socket_connect_timeout=connect_timeout,
                                       decode_responses=True)

    # Можно сделать декораторами, но так, в данном конеретном случае, проще и короче
    def execute_with_reconnect(self, method, *args):
        i = 1
        while i <= self.reconnect_attempts:
            try:
                return method(*args)
            except (redis.ConnectionError, redis.TimeoutError):
                if i == self.reconnect_attempts:
                    raise
            i += 1

    def cache_set(self, key, value, expire):
        try:
            return self.execute_with_reconnect(self.redis.set, key, value, expire)
        except (redis.ConnectionError, redis.TimeoutError):
            return None

    def cache_get(self, key):
        try:
            value = self.execute_with_reconnect(self.redis.get, key)
            if value is not None:
                return json.loads(value)
            return value
        except (redis.ConnectionError, redis.TimeoutError):
            return None

    def get(self, cid):
        return self.execute_with_reconnect(self.redis.lrange, cid, 0, -1)
