import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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

    # Select required values from database
    transactions = db.execute(
        "SELECT symbol, SUM(shares) AS total_shares FROM portfolio WHERE user_id = :user_id GROUP BY symbol HAVING shares > 0", user_id=session["user_id"])

    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    # Create dictionary 'quote' to store symbol data
    quote = {}

    # Get symbol / symbol related data
    for transaction in transactions:
        quote[transaction["symbol"]] = lookup(transaction["symbol"])

    cash_owned = user[0]["cash"]

    return render_template("index.html", transactions=transactions, cash_owned=int(cash_owned), quote=quote)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        # Pull input from user
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        quote = lookup(symbol)

        # Error Checking
        if not shares:
            return apology("Enter Shares")
        if not symbol:
            return apology("Enter Symbol")
        if not quote:
            return apology("Non-Existent Symbol")

        # Assign variable for cash owned by user before transaction
        rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash_owned = rows[0]["cash"]

        # Calculate cost of transaction
        total_cost = quote["price"] * int(shares)

        # Calculate updated cash owned after transaction
        cash_current = int(cash_owned) - total_cost

        # Return error if user cannot afford to buy
        if total_cost > cash_owned:
            return apology("Not Enough Money in Account")

        else:
            # Check if user already own stocks
            stock_db = db.execute("SELECT * FROM portfolio WHERE user_id=:user_id AND symbol=:symbol",
                                  user_id=session["user_id"], symbol=request.form.get("symbol"))

            # If true, update existing values
            if len(stock_db) == 1:

                # Calulate updated stock values
                updated_shares = int(stock_db[0]["shares"]) + int(shares)
                updated_pps = "%.2f" % (quote["price"])
                updated_total = float(stock_db[0]["total"]) + total_cost

                # Update new values into portfolio
                db.execute("UPDATE portfolio SET shares = :shares, pps = :pps, total = :total WHERE user_id = :user_id AND symbol = :symbol",
                            shares=updated_shares, pps=updated_pps, total=updated_total, user_id=session["user_id"], symbol=request.form.get("symbol"))

            # If user doesn't own this stock
            else:

                # Insert all required values into portfolio
                db.execute("INSERT INTO portfolio (user_id, symbol, company_name, shares, pps, total) VALUES (:user_id, :symbol, :company_name, :shares, :pps, :total)",
                           user_id=session["user_id"], symbol=request.form.get("symbol"), company_name=quote["name"], shares=shares, pps=quote["price"], total=total_cost)

        # Update cash after transaction
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=cash_current, user_id=session["user_id"])

        # Insert transaction data into the 'history' database
        db.execute("INSERT INTO history (user_id, action, symbol, shares, pps) VALUES (:user_id, :action, :symbol, :shares, :pps)",
                    user_id=session["user_id"], action=1, symbol=request.form.get("symbol"), shares=shares, pps=quote["price"])

        # Confirm transaction to user via 'bought'
        flash("Bought")
        return render_template("bought.html", quote=quote, total_cost=total_cost, cash_current=cash_current, shares=shares)

    else:
        # If method is GET
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    # Insert transaction data from BUY & SELL app routes.
    # Pull required values from 'history' database.
    transactions = db.execute("SELECT * FROM history WHERE user_id=:user_id", user_id=session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():

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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":

        # Pull user input data AND run error checks
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("No Symbol Entered")

        # Assign lookup method to variable 'quote'
        quote = lookup(symbol)

        # Pull cash data
        row = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash_owned = row[0]["cash"]

        # If stock is invalid
        if quote == None:
            return apology("Invalid Symbol")
            return render_template("quote.html")

        # return quote data for user
        else:
            return render_template("quoted.html", quote=quote, cash_owned=cash_owned)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # Pull user input
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Error checking
        if not username:
            return apology("Enter Username")

        if not password:
            return apology("Enter Password")

        if not confirmation:
            return apology("Enter Confirmation")

        if password != confirmation:
            return apology("Password doesn't match with Confirmation")

        # Check if username already exists
        user_check = db.execute("SELECT * FROM users WHERE username = :username", username=username)

        if len(user_check) == 1:
            return apology("User already exists")

        # Encrypt password into hash code
        hash = generate_password_hash(password)

        # Enter new user data into 'users' database
        createuser = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                                username=username, hash=hash)

        # Remember user's session
        session["id"] = user_check
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    # Pull portfolio data
    portfolios = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])

    if request.method == "POST":

        # Pull user input
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        quote = lookup(symbol)

        # Error Checking
        if not symbol:
            return apology("Enter Symbol")

        if not shares:
            return apology("Enter Shares")

        # Pull portfolio data from database to check for validity
        stock_db = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id AND symbol = :symbol",
                              user_id=session["user_id"], symbol=request.form.get("symbol"))

        if stock_db:
            stock_db = stock_db[0]
        else:
            return render_template("sell.html", portfolio=portfolio)

        # Pull user data
        user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"])

        # Return error if user doesn't own enough stocks to sell
        if int(request.form.get("shares")) > stock_db["shares"]:
            return apology("You Don't Own Enough Shares")

        # Calculate total price of transaction
        total_price = float(quote["price"]) * int(request.form.get("shares"))

        # If user inputted shares == shares user owns
        if int(request.form.get("shares")) == stock_db["shares"]:

            # Delete shares owned of specific stock
            db.execute("DELETE FROM portfolio WHERE symbol = :symbol", symbol=request.form.get("symbol"))

        else:

            # Calculate new share and total value
            new_shares = int(stock_db["shares"]) - int(request.form.get("shares"))
            new_total = float(new_shares) * float(stock_db["pps"])

            # Update shares and total values
            db.execute("UPDATE portfolio SET shares=:shares, total=:total WHERE symbol=:symbol",
                       shares=new_shares, total=new_total, symbol=request.form.get("symbol"))

        # Calculate and update cash owned after transaction
        updated_cash = float(user[0]["cash"]) + float(total_price)
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=updated_cash, user_id=session["user_id"])

        # Insert transaction data into history
        db.execute("INSERT INTO history (user_id, action, symbol, shares, pps) VALUES (:user_id, :action, :symbol, :shares, :pps)",
                   user_id=session["user_id"], action=0, symbol=request.form.get("symbol"), shares=shares, pps=stock_db["pps"])

        # Redirect to sold
        flash("Sold")
        return render_template("sold.html", quote=quote, shares=shares, total_price=total_price, updated_cash=updated_cash)

    else:
        # If request method is GET
        return render_template("sell.html", portfolios=portfolios)

@app.route("/addfunds", methods=["GET", "POST"])
@login_required
def addfunds():

    if request.method == "POST":

        # Pull user input
        funds = int(request.form.get("funds"))

        # Error check
        if not funds:
            return apology("Enter Amount to Add")

        # Get cash owned by user currently
        user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash_owned = user[0]["cash"]

        # Calculate updated cash
        cash_updated = funds + float(cash_owned)

        # Update cash in database
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=cash_updated, user_id=session["user_id"])

        # Redirect to index
        flash("Funds Added!")
        return redirect("/")

    else:
        # If method is GET
        return render_template("funds.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
