from datetime import date
import re

_PLACEH = re.compile(r"\{([A-Z]|expiry_days)\}")

def calc_days_left(date_cell):
    """Принимает то, что лежит в столбце F (строка/дата/None)."""
    try:
        d = date.fromisoformat(str(date_cell).split()[0])
        return (d - date.today()).days
    except Exception:
        return None

def render_with_row(tmpl: str, row: dict):
    return _PLACEH.sub(lambda m: str(row.get(m.group(1), "")), tmpl)
