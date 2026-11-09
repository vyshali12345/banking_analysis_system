
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from db_connection import get_connection


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)


def load_transactions():
    connection = get_connection()

    try:
        query = """
            SELECT
                transaction_date,
                transaction_type,
                amount,
                payment_method,
                transaction_status
            FROM transactions
        """
        return pd.read_sql(query, connection)
    finally:
        connection.close()


def save_transaction_type_chart(df):
    data = df[df["transaction_status"] == "Success"]

    totals = (
        data.groupby("transaction_type")["amount"]
        .sum()
        .reindex(["Deposit", "Withdrawal"], fill_value=0)
    )

    fig, ax = plt.subplots(figsize=(7, 4))
    totals.plot(kind="bar", ax=ax)
    ax.set_title("Deposits vs Withdrawals")
    ax.set_xlabel("Transaction Type")
    ax.set_ylabel("Amount (INR)")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(STATIC_DIR / "transaction_types.png", dpi=150)
    plt.close(fig)


def save_monthly_chart(df):
    data = df[df["transaction_status"] == "Success"].copy()

    if not data.empty:
        data["month"] = pd.to_datetime(
            data["transaction_date"]
        ).dt.to_period("M").astype(str)

        monthly = data.pivot_table(
            index="month",
            columns="transaction_type",
            values="amount",
            aggfunc="sum",
            fill_value=0
        )

        for column in ["Deposit", "Withdrawal"]:
            if column not in monthly.columns:
                monthly[column] = 0

        monthly = monthly[["Deposit", "Withdrawal"]].sort_index()
    else:
        monthly = pd.DataFrame(
            columns=["Deposit", "Withdrawal"]
        )

    fig, ax = plt.subplots(figsize=(7, 4))

    if monthly.empty:
        ax.text(0.5, 0.5, "No successful transactions",
                ha="center", va="center")
        ax.set_axis_off()
    else:
        monthly.plot(kind="bar", ax=ax)
        ax.set_xlabel("Month")
        ax.set_ylabel("Amount (INR)")
        ax.tick_params(axis="x", rotation=0)

    ax.set_title("Monthly Transaction Activity")
    fig.tight_layout()
    fig.savefig(STATIC_DIR / "monthly_transactions.png", dpi=150)
    plt.close(fig)


def save_payment_method_chart(df):
    data = df[df["transaction_status"] == "Success"]

    counts = data["payment_method"].value_counts()

    fig, ax = plt.subplots(figsize=(7, 4))

    if counts.empty:
        ax.text(0.5, 0.5, "No successful transactions",
                ha="center", va="center")
        ax.set_axis_off()
    else:
        counts.plot(kind="bar", ax=ax)
        ax.set_xlabel("Payment Method")
        ax.set_ylabel("Number of Transactions")
        ax.tick_params(axis="x", rotation=25)

    ax.set_title("Transactions by Payment Method")
    fig.tight_layout()
    fig.savefig(STATIC_DIR / "payment_methods.png", dpi=150)
    plt.close(fig)


def main():
    df = load_transactions()

    if df.empty:
        print("No transactions found. Add sample data first.")
        return

    save_transaction_type_chart(df)
    save_monthly_chart(df)
    save_payment_method_chart(df)

    print("All three charts were generated in the static folder.")


if __name__ == "__main__":
    main()
