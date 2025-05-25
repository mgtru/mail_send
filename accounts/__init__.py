from flask import Blueprint, render_template, redirect, url_for, request
import mail_config as mc

bp = Blueprint("accounts", __name__, template_folder="../templates/accounts")

@bp.route("/")
def list_accounts():
    return render_template("accounts/list.html", accounts=mc.all_accounts())

@bp.route("/new", methods=["GET", "POST"])
def new_account():
    if request.method == "POST":
        mc.add_account(
            provider=request.form["provider"],
            email=request.form["email"],
            password=request.form["password"]
        )
        return redirect(url_for("accounts.list_accounts"))
    return render_template("accounts/form.html", providers=mc.PROVIDERS)

@bp.route("/<acc_id>/delete")
def del_account(acc_id):
    mc.delete_account(acc_id)
    return redirect(url_for("accounts.list_accounts"))
