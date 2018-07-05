import hashlib
import api


def get_score(store, phone, email, birthday=None, gender=None, first_name=None, last_name=None):
    key_parts = [
        first_name or "",
        last_name or "",
        birthday.strftime("%Y%m%d") if birthday is not None else "",
    ]
    key = "uid:" + hashlib.md5("".join(key_parts).encode("utf-8")).hexdigest()
    # try get from cache,
    # fallback to heavy calculation in case of cache miss
    score = store.cache_get(key) or 0
    if score:
        return score
    if phone:
        score += 1.5
    if email:
        score += 1.5
    if birthday and gender:
        score += 1.5
    if first_name and last_name:
        score += 0.5
    # cache for 60 minutes
    api.logging.info("key: {0}, score: {1}".format(key, score))
    store.cache_set(key, score,  60 * 60)
    return score


def get_interests(store, cid):
    r = store.get("i:%s" % cid)
    api.logging.info("cid: {0}, r: {1}".format(cid, str(r if r else "")))
    return r if r else []
