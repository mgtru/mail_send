from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import threading, time, pandas as pd

from .storage import create_stream, get_stream, all_streams, update_stream, read_logs
from .worker  import worker, STOP_FLAGS
from mail_config import all_accounts
from .utils   import calc_days_left

bp = Blueprint("streams", __name__, template_folder="../templates/streams")
UPLOAD = Path(__file__).resolve().parent / "uploads";  UPLOAD.mkdir(exist_ok=True)

# ----------------------------- list / create -----------------------------
@bp.route("/")
def list_():
    accs = {a["id"]: a for a in all_accounts()}
    return render_template("streams/list.html", streams=all_streams(), accounts=accs)

@bp.route("/new", methods=["GET", "POST"])
def new():
    accounts = all_accounts()
    if request.method == "POST":
        f = request.files["excel"]
        path = UPLOAD / f"{int(time.time())}_{secure_filename(f.filename)}"
        f.save(path)

        filt = request.form["filter"]
        filter_days = None if filt == "all" else int(filt)

        stream = create_stream(
            title      = request.form["title"],
            excel_path = str(path),
            account_id = request.form["account"],
            filter_days= filter_days,
            pause_sec  = int(request.form.get("pause", 10)),
            subject    = request.form["subject"],
            body       = request.form["body"]
        )
        return redirect(url_for(".view", sid=stream["id"]))
    return render_template("streams/form.html", accounts=accounts)

# ----------------------------- card / actions ----------------------------
@bp.route("/<sid>")
def view(sid):
    st = get_stream(sid) or abort(404)
    df = pd.read_excel(st["excel_path"])
    preview = []
    for _, r in df.iterrows():
        d = calc_days_left(r["F"])
        if st["filter_days"] is None or d == st["filter_days"]:
            preview.append(r.tolist()[:6])
    return render_template("streams/view.html", stream=st, rows=preview[:200])

@bp.route("/<sid>/start")
def start(sid):
    st = get_stream(sid) or abort(404)
    if st["status"] != "running":
        threading.Thread(target=worker, args=(st,), daemon=True).start()
        update_stream(sid, status="running")
    return redirect(url_for(".view", sid=sid))

@bp.route("/<sid>/stop")
def stop(sid):
    STOP_FLAGS[sid] = True
    return redirect(url_for(".view", sid=sid))

@bp.route("/<sid>/progress")
def progress(sid):
    st = get_stream(sid) or abort(404)
    return jsonify({"total": st["total"], "sent": st["sent"], "status": st["status"]})

@bp.route("/<sid>/logs")
def logs(sid):
    st = get_stream(sid) or abort(404)
    return render_template("streams/logs.html", stream=st, logs=read_logs(sid))
