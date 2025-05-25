import json, uuid, datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)
STREAMS_JSON = DATA / "streams.json"
LOG_DIR      = DATA / "logs"
LOG_DIR.mkdir(exist_ok=True)

def _now():
    return datetime.datetime.utcnow().isoformat(timespec="seconds")

def _read():
    if STREAMS_JSON.exists():
        return json.loads(STREAMS_JSON.read_text("utf-8"))
    return {}

def _write(d):
    STREAMS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")

# --------------------------- streams ---------------------------
def create_stream(**kw):
    d = _read()
    sid = str(uuid.uuid4())
    d[sid] = {"id": sid, "status": "idle", "total": 0, "sent": 0,
              "created": _now(), **kw}
    _write(d)
    return d[sid]

def update_stream(sid, **patch):
    d = _read()
    if sid in d:
        d[sid].update(patch)
        _write(d)
    return d.get(sid)

def get_stream(sid):  return _read().get(sid)
def all_streams():     return list(_read().values())

# --------------------------- logs ------------------------------
def add_log(sid, recipient, status, msg=""):
    fn = LOG_DIR / f"{sid}.log"
    with fn.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now(), "recipient": recipient,
                            "status": status, "msg": msg},
                           ensure_ascii=False) + "\n")

def read_logs(sid, limit=800):
    fn = LOG_DIR / f"{sid}.log"
    if not fn.exists():
        return []
    with fn.open(encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    return [json.loads(l) for l in reversed(lines)]
