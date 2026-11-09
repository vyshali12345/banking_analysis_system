
from decimal import Decimal
from random import choice, randint, random
from datetime import datetime, timedelta

from db_connection import get_connection


TARGET_TOTAL = 100
REVIEW_THRESHOLD = Decimal("10000.00")

PAYMENT_METHODS = ["UPI", "Cash", "Card", "Bank Transfer"]
TRANSACTION_TYPES = ["Deposit", "Withdrawal"]


def generate_transactions():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # Lock existing accounts while generating sample transactions.
        cursor.execute("""
            SELECT account_id, opening_balance, account_status
            FROM accounts
            ORDER BY account_id
            FOR UPDATE
        """)

        accounts = cursor.fetchall()

        if not accounts:
            raise ValueError("No accounts found in the database.")

        accounts = [
            account for account in accounts
            if account["account_status"] == "Active"
        ]

        if not accounts:
            raise ValueError("No active accounts found.")

        # Count the transactions already stored.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM transactions
        """)

        current_total = cursor.fetchone()["total"]
        remaining = TARGET_TOTAL - current_total

        if remaining <= 0:
            conn.rollback()
            print(f"Database already contains {current_total} transactions.")
            print("No new transactions were added.")
            return

        # Calculate the current balance of each account.
        balances = {}

        for account in accounts:
            account_id = account["account_id"]

            cursor.execute("""
                SELECT COALESCE(
                    SUM(
                        CASE
                            WHEN transaction_type = 'Deposit'
                                THEN amount
                            WHEN transaction_type = 'Withdrawal'
                                THEN -amount
                            ELSE 0
                        END
                    ), 0
                ) AS net_amount

                FROM transactions

                WHERE account_id = %s
                AND transaction_status = 'Success'
            """, (account_id,))

            net_amount = cursor.fetchone()["net_amount"] or Decimal("0.00")

            balances[account_id] = (
                Decimal(str(account["opening_balance"]))
                + Decimal(str(net_amount))
            )

        inserted = 0

        for _ in range(remaining):
            account = choice(accounts)
            account_id = account["account_id"]
            current_balance = balances[account_id]

            # Use varied sample amounts.
            amount = Decimal(
                str(choice([
                    250, 500, 750, 1000, 1500, 2000,
                    2500, 3000, 4000, 5000, 7500,
                    10000, 12000, 15000, 20000
                ]))
            )

            # Withdraw only when the account has enough money.
            if random() < 0.45 and current_balance >= Decimal("250.00"):
                transaction_type = "Withdrawal"

                # Limit the withdrawal to the current balance.
                if amount > current_balance:
                    amount = current_balance.quantize(Decimal("0.01"))

                if amount <= 0:
                    transaction_type = "Deposit"
                    amount = Decimal("500.00")
            else:
                transaction_type = "Deposit"

            if transaction_type == "Deposit":
                balance_after = current_balance + amount
            else:
                balance_after = current_balance - amount

            review_flag = (
                1 if amount >= REVIEW_THRESHOLD else 0
            )

            # Generate dates within the past 60 days.
            random_days = randint(0, 59)
            random_minutes = randint(0, 1439)

            transaction_date = (
                datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                - timedelta(days=random_days)
                + timedelta(minutes=random_minutes)
            )

            payment_method = choice(PAYMENT_METHODS)

            description = (
                f"Sample {transaction_type.lower()} "
                f"via {payment_method}"
            )

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
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Success', %s)
            """, (
                account_id,
                transaction_date,
                transaction_type,
                amount,
                balance_after,
                payment_method,
                description,
                review_flag
            ))

            balances[account_id] = balance_after
            inserted += 1

        conn.commit()

        print(f"Successfully inserted {inserted} sample transactions.")
        print(f"Previous transaction count: {current_total}")
        print(f"New transaction count: {current_total + inserted}")
        print("All generated records use fictional sample data.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    generate_transactions()
