import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
import io

def get_history_plot(account_name: str, account_history: dict) -> io.BytesIO:
    sorted_dates = sorted(account_history.keys())
    values = [account_history[d]["value"] for d in sorted_dates]
    
    dates = pd.to_datetime(sorted_dates)

    plt.figure(figsize=(8, 4), facecolor="black")
    ax = plt.gca()
    ax.set_facecolor("black")

    ax.plot(dates, values, marker="o", linestyle="-", color="cyan", label="Account Value")

    ax.set_title(f"{account_name} Account Value Over Time", color="white")
    ax.set_xlabel("Date", color="white")
    ax.set_ylabel("Value", color="white")

    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    ax.grid(True, linestyle="--", alpha=0.5, color="white")

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=plt.gcf().get_facecolor())
    buf.seek(0)
    plt.close()
    return buf

def get_returns_plot(account_name: str, account_history: dict) -> io.BytesIO:
    sorted_dates = sorted(account_history.keys())
    returns = [account_history[d]["return"] for d in sorted_dates]
    
    dates = pd.to_datetime(sorted_dates)

    plt.figure(figsize=(8, 4), facecolor="black")
    ax = plt.gca()
    ax.set_facecolor("black")

    ax.plot(dates, returns, marker="o", linestyle="-", color="cyan", label="Returns")

    ax.set_title(f"{account_name} Account Returns Over Time", color="white")
    ax.set_xlabel("Date", color="white")
    ax.set_ylabel("Returns", color="white")

    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    ax.grid(True, linestyle="--", alpha=0.5, color="white")

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=plt.gcf().get_facecolor())
    buf.seek(0)
    plt.close()
    return buf

def get_multi_returns_plot(accounts: dict) -> io.BytesIO:
    plt.figure(figsize=(10, 5), facecolor="black")
    ax = plt.gca()
    ax.set_facecolor("black")

    colors = ["cyan", "orange", "lime", "magenta", "yellow"]

    for i, (account_name, account_history) in enumerate(accounts.items()):
        sorted_dates = sorted(account_history.keys())
        returns = [account_history[d]["return"] for d in sorted_dates]
        dates = pd.to_datetime(sorted_dates)

        color = colors[i % len(colors)]

        ax.plot(dates, returns, marker="o", linestyle="-", color=color, label=account_name)

    ax.set_title("Account Returns Over Time", color="white")
    ax.set_xlabel("Date", color="white")
    ax.set_ylabel("Returns", color="white")

    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    ax.grid(True, linestyle="--", alpha=0.5, color="white")

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    ax.legend(facecolor="black", edgecolor="white", labelcolor="white")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=plt.gcf().get_facecolor())
    buf.seek(0)
    plt.close()
    return buf