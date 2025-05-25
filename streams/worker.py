import pandas as pd, time, threading, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .utils    import calc_days_left, render_with_row
from .storage  import update_stream, add_log
from mail_config import get_by_id      # ← берём SMTP-аккаунт

STOP_FLAGS = {}        # sid → True, если поток остановлен вручную

def _smtp_send(acc, subj, body, to_addr):
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = acc["email"], to_addr, subj
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP_SSL(acc["smtp_server"], acc["smtp_port"]) as s:
        s.login(acc["email"], acc["password"])
        s.send_message(msg)

def worker(stream: dict):
    sid = stream["id"]
    df  = pd.read_excel(stream["excel_path"])
    acc = get_by_id(stream["account_id"])

    rows = []
    for _, r in df.iterrows():
        exp = calc_days_left(r["F"])  # int или None
        if stream["filter_days"] is None:
            # без фильтра — берём всё
            rows.append({**{c: r[c] for c in "ABCDEF"}, "expiry_days": exp})
        else:
            # ≤ N дней (и дата не в прошлом)
            if exp is not None and 0 <= exp <= stream["filter_days"]:
                rows.append({**{c: r[c] for c in "ABCDEF"}, "expiry_days": exp})

    update_stream(sid, total=len(rows), sent=0, status="running")

    for i, row in enumerate(rows, 1):
        if STOP_FLAGS.get(sid): break

        subj = render_with_row(stream["subject"], row)
        body = render_with_row(stream["body"],    row)
        try:
            _smtp_send(acc, subj, body, str(row["A"]).strip())
            add_log(sid, row["A"], "ok")
        except Exception as e:
            add_log(sid, row["A"], "error", str(e))

        update_stream(sid, sent=i)
        time.sleep(stream["pause_sec"])

    update_stream(sid, status="stopped" if STOP_FLAGS.pop(sid, None) else "finished")
