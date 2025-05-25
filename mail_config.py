import json, uuid
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

PROVIDERS = {
    "mail.ru": ("smtp.mail.ru",   465),
    "yandex":  ("smtp.yandex.ru", 465),
    "gmail":   ("smtp.gmail.com", 465),
}

def _read_cfg():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {}

def _write_cfg(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")

# ------------------------------------------------------------------ ACCOUNTS
def all_accounts() -> list[dict]:
    """
    Возвращает список учёток. Если в файле лежал один-единственный объект —
    мигрируем в список.
    """
    cfg = _read_cfg()

    # формат V1: целый файл = один объект
    if cfg and "accounts" not in cfg:
        acc = cfg.copy()
        acc.setdefault("id", str(uuid.uuid4()))
        acc.setdefault("smtp_server", PROVIDERS[acc["provider"]][0])
        acc.setdefault("smtp_port",   PROVIDERS[acc["provider"]][1])
        cfg = {"active": acc, "accounts": [acc]}
        _write_cfg(cfg)
    return cfg.get("accounts", [])

def get_by_id(acc_id):
    return next((a for a in all_accounts() if a["id"] == acc_id), None)

def add_account(provider, email, password):
    smtp, port = PROVIDERS[provider]
    new_acc = {
        "id": str(uuid.uuid4()),
        "provider": provider,
        "email": email,
        "password": password,
        "smtp_server": smtp,
        "smtp_port": port,
    }
    cfg = _read_cfg()
    lst = cfg.get("accounts", [])
    lst.append(new_acc)
    cfg["accounts"] = lst
    # если ещё нет active — делаем только что созданный ящик активным
    cfg.setdefault("active", new_acc)
    _write_cfg(cfg)
    return new_acc

def delete_account(acc_id):
    cfg = _read_cfg()
    cfg["accounts"] = [a for a in cfg.get("accounts", []) if a["id"] != acc_id]
    if cfg.get("active", {}).get("id") == acc_id:
        cfg["active"] = cfg["accounts"][0] if cfg["accounts"] else {}
    _write_cfg(cfg)

def active_account():
    """То, что использует СТАРАЯ «быстрая» рассылка."""
    return _read_cfg().get("active", {})
