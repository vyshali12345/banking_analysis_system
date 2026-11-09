
from decimal import Decimal, InvalidOperation

import mysql.connector
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from db_connection import get_connection


app = Flask(__name__)
app.secret_key = "banksight-college-project-key"

PAYMENT_METHODS = {"UPI", "Cash", "Card", "Bank Transfer"}
TRANSACTION_TYPES = {"Deposit", "Withdrawal"}

# Educational project rule:
# Transactions of ₹10,000 or more are flagged for manual review.
REVIEW_THRESHOLD = Decimal("10000.00")


# --------------------------------------------------
# DASHBOARD DATA
# --------------------------------------------------

def get_dashboard_data():
    conn = get_connection()

    try:
        cursor = conn.cursor(dictionary=True)

        try:
            # 1. All transactions
            cursor.execute("""
                SELECT
                    transaction_id,
                    account_id,
                    transaction_date,
                    transaction_type,
                    amount,
                    payment_method,
                    transaction_status,
                    review_flag,
                    description
                FROM transactions
                ORDER BY transaction_date DESC, transaction_id DESC
            """)

            transactions = cursor.fetchall()

            # 2. Dashboard summary
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_transactions,

                    COALESCE(SUM(
                        CASE
                            WHEN transaction_type = 'Deposit'
                            AND transaction_status = 'Success'
                            THEN amount
                            ELSE 0
                        END
                    ), 0) AS total_deposits,

                    COALESCE(SUM(
                        CASE
                            WHEN transaction_type = 'Withdrawal'
                            AND transaction_status = 'Success'
                            THEN amount
                            ELSE 0
                        END
                    ), 0) AS total_withdrawals,

                    COALESCE(SUM(
                        CASE
                            WHEN review_flag = 1 THEN 1
                            ELSE 0
                        END
                    ), 0) AS flagged_count

                FROM transactions
            """)

            summary = cursor.fetchone()

            # 3. Monthly transaction report
            cursor.execute("""
                SELECT
                    DATE_FORMAT(transaction_date, '%Y-%m') AS month,

                    SUM(
                        CASE
                            WHEN transaction_type = 'Deposit'
                            AND transaction_status = 'Success'
                            THEN amount
                            ELSE 0
                        END
                    ) AS total_deposits,

                    SUM(
                        CASE
                            WHEN transaction_type = 'Withdrawal'
                            AND transaction_status = 'Success'
                            THEN amount
                            ELSE 0
                        END
                    ) AS total_withdrawals,

                    SUM(
                        CASE
                            WHEN transaction_status = 'Success'
                            THEN 1
                            ELSE 0
                        END
                    ) AS successful_transactions

                FROM transactions
                GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
                ORDER BY month DESC
            """)

            monthly_report = cursor.fetchall()

            # 4. Account-wise summary
            cursor.execute("""
                SELECT
                    a.account_id,
                    c.customer_name,
                    a.account_type,

                    COALESCE(SUM(
                        CASE
                            WHEN t.transaction_type = 'Deposit'
                            AND t.transaction_status = 'Success'
                            THEN t.amount
                            ELSE 0
                        END
                    ), 0) AS total_deposits,

                    COALESCE(SUM(
                        CASE
                            WHEN t.transaction_type = 'Withdrawal'
                            AND t.transaction_status = 'Success'
                            THEN t.amount
                            ELSE 0
                        END
                    ), 0) AS total_withdrawals,

                    COALESCE(SUM(
                        CASE
                            WHEN t.transaction_status = 'Success'
                            THEN 1
                            ELSE 0
                        END
                    ), 0) AS successful_transactions

                FROM accounts a

                JOIN customers c
                    ON c.customer_id = a.customer_id

                LEFT JOIN transactions t
                    ON t.account_id = a.account_id

                GROUP BY
                    a.account_id,
                    c.customer_name,
                    a.account_type

                ORDER BY a.account_id
            """)

            account_summary = cursor.fetchall()

            # 5. Deposit versus withdrawal chart
            cursor.execute("""
                SELECT
                    transaction_type,
                    COUNT(*) AS count,
                    COALESCE(SUM(amount), 0) AS total

                FROM transactions

                WHERE transaction_status = 'Success'

                GROUP BY transaction_type
            """)

            type_rows = cursor.fetchall()

            # 6. Monthly chart data
            cursor.execute("""
                SELECT
                    DATE_FORMAT(transaction_date, '%Y-%m') AS month,

                    SUM(
                        CASE
                            WHEN transaction_type = 'Deposit'
                            THEN amount
                            ELSE 0
                        END
                    ) AS deposits,

                    SUM(
                        CASE
                            WHEN transaction_type = 'Withdrawal'
                            THEN amount
                            ELSE 0
                        END
                    ) AS withdrawals

                FROM transactions

                WHERE transaction_status = 'Success'

                GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')

                ORDER BY month
            """)

            monthly_chart_rows = cursor.fetchall()

            # 7. Payment method chart
            cursor.execute("""
                SELECT
                    payment_method,
                    COUNT(*) AS count,
                    COALESCE(SUM(amount), 0) AS total

                FROM transactions

                WHERE transaction_status = 'Success'

                GROUP BY payment_method

                ORDER BY payment_method
            """)

            payment_rows = cursor.fetchall()

            # 8. Active accounts for the transaction form
            cursor.execute("""
                SELECT
                    account_id,
                    account_number,
                    account_type

                FROM accounts

                WHERE account_status = 'Active'

                ORDER BY account_id
            """)

            active_accounts = cursor.fetchall()

            return (
                transactions,
                summary,
                monthly_report,
                account_summary,
                type_rows,
                monthly_chart_rows,
                payment_rows,
                active_accounts,
            )

        finally:
            cursor.close()

    finally:
        conn.close()


# --------------------------------------------------
# HOME / DASHBOARD ROUTE
# --------------------------------------------------

@app.route("/")
def home():
    try:
        (
            transactions,
            summary,
            monthly_report,
            account_summary,
            type_rows,
            monthly_chart_rows,
            payment_rows,
            active_accounts,
        ) = get_dashboard_data()

        return render_template(
            "index.html",
            transactions=transactions,
            total_transactions=summary["total_transactions"] or 0,
            total_deposits=summary["total_deposits"] or 0,
            total_withdrawals=summary["total_withdrawals"] or 0,
            flagged_count=summary["flagged_count"] or 0,
            monthly_report=monthly_report,
            account_summary=account_summary,
            type_rows=type_rows,
            monthly_chart_rows=monthly_chart_rows,
            payment_rows=payment_rows,
            active_accounts=active_accounts,
        )

    except mysql.connector.Error:
        app.logger.exception("Dashboard database error")

        return (
            "Could not load the dashboard. Check your MySQL connection "
            "and table columns.",
            500,
        )


# --------------------------------------------------
# ADD TRANSACTION ROUTE
# --------------------------------------------------

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    conn = None
    cursor = None

    try:
        # Read form data
        account_id = int(request.form.get("account_id", "0"))
        transaction_type = request.form.get("transaction_type", "")
        payment_method = request.form.get("payment_method", "")
        description = request.form.get("description", "").strip()
        amount_text = request.form.get("amount", "").strip()

        # Validate account ID
        if account_id <= 0:
            flash("Please select a valid account.", "error")
            return redirect(url_for("home"))

        # Validate transaction type
        if transaction_type not in TRANSACTION_TYPES:
            flash("Please select Deposit or Withdrawal.", "error")
            return redirect(url_for("home"))

        # Validate payment method
        if payment_method not in PAYMENT_METHODS:
            flash("Please select a valid payment method.", "error")
            return redirect(url_for("home"))

        # Validate description
        if len(description) > 255:
            flash(
                "Description must be 255 characters or fewer.",
                "error",
            )
            return redirect(url_for("home"))

        # Validate amount
        try:
            amount = Decimal(amount_text)

            if (
                not amount.is_finite()
                or amount <= 0
                or amount.as_tuple().exponent < -2
                or amount > Decimal("9999999999.99")
            ):
                raise InvalidOperation

            amount = amount.quantize(Decimal("0.01"))

        except (InvalidOperation, ValueError):
            flash(
                "Enter a positive amount with at most 2 decimal places.",
                "error",
            )
            return redirect(url_for("home"))

        # Start database transaction
        conn = get_connection()
        conn.start_transaction()

        cursor = conn.cursor(dictionary=True)

        # Lock the account row while checking the balance
        cursor.execute("""
            SELECT
                account_id,
                opening_balance,
                account_status

            FROM accounts

            WHERE account_id = %s

            FOR UPDATE
        """, (account_id,))

        account = cursor.fetchone()

        if not account:
            conn.rollback()
            flash("Account not found.", "error")
            return redirect(url_for("home"))

        if account["account_status"] != "Active":
            conn.rollback()
            flash("This account is inactive.", "error")
            return redirect(url_for("home"))

        # Calculate the net amount from successful transactions
        cursor.execute("""
            SELECT
                COALESCE(SUM(
                    CASE
                        WHEN transaction_type = 'Deposit'
                            THEN amount

                        WHEN transaction_type = 'Withdrawal'
                            THEN -amount

                        ELSE 0
                    END
                ), 0) AS net_amount

            FROM transactions

            WHERE account_id = %s
            AND transaction_status = 'Success'
        """, (account_id,))

        result = cursor.fetchone()
        net_amount = result["net_amount"]

        # Current balance = opening balance + net transactions
        balance = (
            Decimal(str(account["opening_balance"]))
            + Decimal(str(net_amount or 0))
        )

        # Prevent withdrawals greater than the available balance
        if transaction_type == "Withdrawal" and amount > balance:
            conn.rollback()

            flash(
                f"Insufficient balance. Available balance: ₹{balance:.2f}",
                "error",
            )

            return redirect(url_for("home"))

        # Calculate balance after this transaction
        if transaction_type == "Deposit":
            balance_after = balance + amount
        else:
            balance_after = balance - amount

        # AUTOMATIC REVIEW FLAG
        # ₹10,000 or more = 1 (flagged)
        # Below ₹10,000 = 0 (not flagged)
        review_flag = 1 if amount >= REVIEW_THRESHOLD else 0

        # Save the transaction
        cursor.execute("""
            INSERT INTO transactions (
                account_id,
                transaction_date,
                transaction_type,
                amount,
                balance_after,
                payment_method,
                description,
                transaction_status,
                review_flag
            )

            VALUES (
                %s,
                NOW(),
                %s,
                %s,
                %s,
                %s,
                %s,
                'Success',
                %s
            )
        """, (
            account_id,
            transaction_type,
            amount,
            balance_after,
            payment_method,
            description or None,
            review_flag,
        ))

        # Save database changes
        conn.commit()

        # Show the appropriate success message
        message = (
            f"{transaction_type} of ₹{amount:.2f} "
            "recorded successfully."
        )

        if review_flag == 1:
            message += " Flagged for manual review."

        flash(message, "success")

    except ValueError:
        if conn:
            conn.rollback()

        flash("Please enter a valid account ID.", "error")

    except mysql.connector.Error:
        if conn:
            conn.rollback()

        app.logger.exception("Could not save transaction")

        flash(
            "Database error. The transaction was not saved.",
            "error",
        )

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return redirect(url_for("home"))


# --------------------------------------------------
# TRANSACTIONS API
# --------------------------------------------------
@app.route("/accounts")
def accounts_api():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(accounts)

@app.route("/customers")
def customers_api():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM customers")
    customers = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(customers)
@app.route("/transactions")
def transactions_api():
    conn = get_connection()

    try:
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT
                    transaction_id,
                    account_id,
                    transaction_date,
                    transaction_type,
                    amount,
                    balance_after,
                    payment_method,
                    description,
                    transaction_status,
                    review_flag

                FROM transactions

                ORDER BY transaction_date DESC, transaction_id DESC
            """)

            return jsonify(cursor.fetchall())

        finally:
            cursor.close()

    finally:
        conn.close()


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
