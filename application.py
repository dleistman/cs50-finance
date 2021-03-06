from cs50 import SQL
import os
import sqlalchemy

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, currency
# from decimal import Decimal

# start
# added the below as part of Heroku post on Medium
import urllib.parse
import psycopg2
urllib.parse.uses_netloc.append("postgres")
url = urllib.parse.urlparse(os.environ["DATABASE_URL"])
conn = psycopg2.connect(
 database=url.path[1:],
 user=url.username,
 password=url.password,
 host=url.hostname,
 port=url.port
)
# end


# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
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
db = SQL(os.environ["DATABASE_URL"])


# start
# added the below as part of Heroku post on Medium
class SQL(object):
    def __init__(self, url):
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)
    def execute(self, text, *multiparams, **params):
        try:
            statement = sqlalchemy.text(text).bindparams(*multiparams, **params)
            result = self.engine.execute(str(statement.compile(compile_kwargs={"literal_binds": True})))
            # SELECT
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]
            # INSERT
            elif result.lastrowid is not None:
                return result.lastrowid
            # DELETE, UPDATE
            else:
                return result.rowcount
        except sqlalchemy.exc.IntegrityError:
            return None
        except Exception as e:
            raise RuntimeError(e)
# end


############################################################

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # set variables
    username = request.form.get("username")
    password = request.form.get("password")
    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username"):
            return apology("Missing username!")
        elif password == request.form.get("confirmation"):
            # hash the password
            hash = generate_password_hash(password)
            # add user to database, checking to make sure they are not already registered
            success = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
            if not success:
                return apology("Username already exists")
            # log them in
            rows = db.execute("SELECT id FROM users WHERE username = :username", username=username)
            if not rows:
                return apology("Query failed")
            session["user_id"] = rows[0]["id"]
            return redirect("/")
        else:
            return apology("Passwords do not match!")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username!", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password!", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if not rows:
            return apology("Buying stock query failed")

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

############################################################

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    if not cash:
        return apology('Database query failed. Please click "Portfolio" again, Heroku sometimes fails on first attempt')
    cash = round(cash[0]["cash"], 2)
    rows = db.execute("SELECT symbol, SUM(num_shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])

    if not rows:
        return apology('Database query failed. Please click "Portfolio" again, query sometimes fails on first attempt')

    table_display = []
    for row in rows:
        if row['sum'] != 0:
            table_display.append(row)
    stock_total = 0
    for row in table_display:
        stock = lookup(row["symbol"])
        if not stock:
            return apology('API query failed. Please click "Portfolio" again, query sometimes fails on first attempt')
        print(stock)
        row["current_price"] = currency(stock["price"])
        row["total"] = currency(row['sum'] * stock["price"])
        stock_total += row['sum'] * stock["price"]
    total_assets = cash + stock_total
    return render_template("index.html", rows=table_display, stock_total=currency(stock_total), cash=currency(cash), total_assets=currency(total_assets))


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, num_shares, price, timestamp FROM transactions WHERE user_id = :user_id ORDER BY timestamp desc", user_id=session["user_id"])
    if not rows:
        return apology("Buying stock query failed")
    for transaction in rows:
        transaction["total"] = currency(transaction["num_shares"] * transaction["price"])
        transaction["price"] = currency(transaction["price"])
        transaction["timestamp"] = transaction["timestamp"].strftime("%b %d, %Y\n%I:%M %p")
        if transaction["num_shares"] > 0:
            transaction["type"] = "Buy"
        else:
            transaction["type"] = "Sell"
    return render_template("history.html", rows=rows)

############################################################

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Register user"""
    # set variables
    user_id = session["user_id"]
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    verify_password = request.form.get("verify_password")
    if request.method == "GET":
        return render_template("change_password.html")
    else:
        rows = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=user_id)
        if not rows:
            return apology("Database query failed")
        current_pw_hash = rows[0]["hash"]

        if not request.form.get("old_password"):
            return apology("Please enter your current password")
        elif not check_password_hash(current_pw_hash, old_password):
            return apology("Current password is incorrect")
        elif new_password == verify_password:
            hash = generate_password_hash(new_password)
            success = db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", user_id=user_id, hash=hash)
            if not success:
                return apology('Database update failed')
            flash('Password changed!')
            return redirect("/")

        else:
            return apology("Passwords do not match!")


############################################################

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing stock symbol!")
        else:
            stock = lookup(symbol)
            stock["price"] = currency(stock["price"])
            return render_template("quote_result.html", stock=stock)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        num_shares = request.form.get("num_shares")
        if not symbol:
            return apology("Missing stock symbol!")
        elif not num_shares:
            return apology("Missing number of shares!")
        else:
            num_shares = int(num_shares)
            stock = lookup(symbol)
            price = float(stock["price"])

            rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
            if not rows:
                return apology("Buying stock query failed")
            cash = rows[0]["cash"]
            if (price * num_shares) > cash:
                return apology("You don't have enough cash!")
            else:
                buy_stock = db.execute("INSERT INTO transactions (user_id, symbol, num_shares, price) VALUES (:user_id, :symbol, :num_shares, :price)", user_id=session["user_id"], symbol=symbol, num_shares=num_shares, price=price)
                if not buy_stock:
                    return apology("Buying stock query failed")
                spend_cash = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=price*num_shares, user_id=session["user_id"])
                if not spend_cash:
                    return apology("Deducting cash query failed")
                flash(f"Successfully purchased {num_shares} shares of {symbol}")
                return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT symbol, SUM(num_shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])
        if not rows:
            return apology("Buying stock query failed")
        stocks = []
        for row in rows:
            if row["sum"] != 0:
                stocks.append(row)
        return render_template("sell.html", stocks=stocks)
    else:
        symbol = request.form.get("symbol")
        num_shares = request.form.get("num_shares")
        if not symbol:
            return apology("Missing stock symbol!")
        elif not num_shares:
            return apology("Missing number of shares!")
        else:
            num_shares = int(num_shares)
            stock = lookup(symbol)
            price = float(stock["price"])
            num_shares = 0 - num_shares
            sell_stock = db.execute("INSERT INTO transactions (user_id, symbol, num_shares, price) VALUES (:user_id, :symbol, :num_shares, :price)", user_id=session["user_id"], symbol=symbol, num_shares=num_shares, price=price)
            if not sell_stock:
                return apology("Buying stock query failed")
            get_cash = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=price*num_shares, user_id=session["user_id"])
            if not get_cash:
                return apology("Deducting cash query failed")
            flash(f"Successfully sold {abs(num_shares)} shares of {symbol}")
            return redirect("/")

        return render_template("sell.html")


############################################################


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# start
# added the below as part of Heroku post on Medium
if __name__ == '__main__':
     app.debug = True
     port = int(os.environ.get("PORT", 5000))
     app.run(host='0.0.0.0', port=port)
# end
