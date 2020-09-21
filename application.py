import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    stocks = db.execute("SELECT * FROM stocks WHERE user = :i", i = session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :i", i = session["user_id"])
    cash = cash[0]["cash"]
    cash = float("{:.2f}".format(cash))
    total = 0
    for stock in stocks:
        val = lookup(stock["symbol"])
        stock["curr_price"] = val["price"]
        stock["net_val"] = val["price"] * float(stock["quantity"])
        stock["net_val"] = float("{:.2f}".format(stock["net_val"]))
        total += stock["net_val"]
    total = float("{:.2f}".format(total))
    worth = cash + total
    worth = float("{:.2f}".format(worth))
    return render_template("index.html", stocks=stocks, total=total, cash=cash, worth=worth)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    else:
        sym = request.form.get("symbol").upper()
        share = int(request.form.get("shares"))
        if not sym:
            return apology("must provide symbol", 403)

        if not share or share == 0:
            return apology("must provide shares", 403)

        val = lookup(sym)

        if not val:
            return apology("symbol not found", 403)

        cash = db.execute("SELECT cash FROM users WHERE id = :i", i=session["user_id"])
        cash = cash[0]["cash"]

        value = val["price"] * share
        if value > cash:
            return apology("not enough cash", 403)
        cash = cash - value

        stock = db.execute("SELECT symbol, quantity FROM stocks WHERE user = :i", i=session["user_id"])
        quantities = [int(d["quantity"]) for d in stock]
        stock = [d["symbol"] for d in stock]
        for i in range(0, len(stock)):
            if sym == stock[i]:
                s = share + quantities[i]
                db.execute("UPDATE stocks SET quantity = :q", q=s)
                db.execute("UPDATE users SET cash = :c WHERE id = :i", c=cash, i=session["user_id"])
                db.execute("INSERT INTO HISTORY (user_id, action, symbol, price, shares, date, time) VALUES (?, ?, ?, ?, ?, date('now'), time('now'))", session["user_id"], "BUY", sym, val["price"], share)
                return redirect("/")

        db.execute("INSERT INTO stocks (user, symbol, quantity) VALUES (?, ?, ?)", session["user_id"], sym, share)
        db.execute("UPDATE users SET cash = :c WHERE id = :i", c=cash, i=session["user_id"])
        db.execute("INSERT INTO HISTORY (user_id, action, symbol, price, shares, date, time) VALUES (?, ?, ?, ?, ?, date('now'), time('now'))", session["user_id"], "BUY", sym, val["price"], share)
        return redirect("/")


@app.route("/history")
@login_required
def history():
    history = db.execute("SELECT * FROM HISTORY WHERE user_id = :i", i = session["user_id"])
    i = 1
    for stock in history:
        stock["ind"] = i
        stock["price"] = float("{:.2f}".format(stock["price"]))
        i += 1
    return render_template("history.html", history=history)




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    else:
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        val = lookup(request.form.get("symbol"))

        if not val:
            return apology("symbol not found", 403)

        return render_template("quoted.html", name=val["name"], price=usd(val["price"]), symbol=val["symbol"])

@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password1"):
            return apology("must provide password", 403)

        elif not request.form.get("password2"):
            return apology("must retype password", 403)

        elif not request.form.get("password1") == request.form.get("password2"):
            return apology("passwords dont match", 403)


        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 0:
            return apology("username is unavailable", 403)

        username = request.form.get("username")
        password = request.form.get("password2")
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        stock = db.execute("SELECT symbol, quantity FROM stocks WHERE user = :i", i=session["user_id"])
        stock = [d["symbol"] for d in stock]
        return render_template("sell.html", stock=stock)

    else:
        sym = request.form.get("symbol")
        share = int(request.form.get("shares"))
        if not sym:
            return apology("must select symbol", 403)

        if not share or share == 0:
            return apology("must provide shares", 403)

        shares = db.execute("SELECT quantity FROM stocks WHERE user = :i AND symbol = :s", i=session["user_id"], s=sym)
        shares = shares[0]["quantity"]
        if share > shares:
            return apology("not enough shares", 403)

        val = lookup(sym)

        if not val:
            return apology("symbol not found", 403)

        cash = db.execute("SELECT cash FROM users WHERE id = :i", i=session["user_id"])
        cash = cash[0]["cash"]

        value = val["price"] * int(share)
        cash = cash + value
        shares -= share
        if shares == 0:
            db.execute("DELETE FROM stocks WHERE user = :i AND symbol=:sy", i=session["user_id"], sy=sym)
        else:
            db.execute("UPDATE stocks SET quantity = :s WHERE user = :i AND symbol=:sy", s=shares, i=session["user_id"], sy=sym)
        db.execute("UPDATE users SET cash = :c WHERE id = :i", c=cash, i=session["user_id"])
        db.execute("INSERT INTO HISTORY (user_id, action, symbol, price, shares, date, time) VALUES (?, ?, ?, ?, ?, date('now'), time('now'))", session["user_id"], "SELL", sym, val["price"], share)
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
