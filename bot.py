import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, time, timedelta
import pytz
import yfinance as yf
import json
import os
from dotenv import load_dotenv

load_dotenv() 

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
db_file_path = os.getenv("FILE_PATH", "")
db_path = os.path.join(db_file_path, "db.json")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

reconciliation_orders = {
    # timestamp, account, shares
}

def load_accounts() -> dict:
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            return json.load(f)
    return {}

def get_account_names() -> list[str]:
    accounts = load_accounts()
    return accounts.keys()

def save_accounts(data: dict) -> None:
    with open(db_path, "w") as f:
        json.dump(data, f, indent=2)

def evaluate_account_positions(account_name):
    pass

def portfolio_summary_helper(account_name):
    if account_name not in get_account_names():
        return None
    account = load_accounts()[account_name]
    summary = {
        "total_value": account["invested"] + account["cash"],
        "invested": account["invested"],
        "cash": account["cash"],
        "positions": [],
        "daily_pl": 0.0
    }
    for ticker, lots in account["positions"].items():
        price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
        shares_total = sum(lot["shares"] for lot in lots)
        cost_basis = sum(lot["shares"] * lot["cost"] for lot in lots)
        position_value = shares_total * price
        pl = position_value - cost_basis
        summary["total_value"] += position_value
        summary["positions"].append({
            "ticker": ticker,
            "shares": shares_total,
            "value": position_value,
            "cost_basis": cost_basis,
            "pl": pl
        })
    return summary

async def execute_market_order(account_name, ticker, shares, interaction):
    account = load_accounts()[account_name]
    try:
        latest_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except Exception:
        await interaction.response.send_message(f"Ticker `{ticker}` invalid.", ephemeral=True)
        return

    total_estimate = shares * latest_price
    account["cash"] -= total_estimate  # immediate deduction (can go slightly negative)
    
    if ticker not in account["positions"]:
        account["positions"][ticker] = []

    # Add lot to FIFO list
    account["positions"][ticker].append({"shares": shares, "cost": latest_price})
    
    account["history"].append({
        "ticker": ticker,
        "shares": shares,
        "price": latest_price,
        "time": datetime.now().isoformat()
    })
    
    save_accounts()
    await interaction.response.send_message(
        f"Market order placed: {shares} shares of {ticker} at estimated ${latest_price:.2f}.",
        ephemeral=True
    )

@bot.tree.command(name="portfolio_summary", description="Show portfolio summary")
@app_commands.describe(name="Account name")
async def get_portfolio_summary(interaction: discord.Interaction, name: str):
    summary = portfolio_summary_helper(name)
    if not summary:
        await interaction.response.send_message(f"Account `{name}` does not exist.", ephemeral=True)
        return

    report = f"💼 Portfolio Summary for `{name}`\nTotal Value: ${summary['total_value']:.2f}\nInvested: ${summary['invested']:.2f}\nCash: ${summary['cash']:.2f}\n"
    for pos in summary["positions"]:
        report += f"- {pos['ticker']}: {pos['shares']} shares | Value: ${pos['value']:.2f} | Cost: ${pos['cost_basis']:.2f} | P/L: ${pos['pl']:.2f}\n"
    
    await interaction.response.send_message(report)

@bot.tree.command(name="create_account", description="Create a trading account")
@app_commands.describe(name="Name of your account", starting_value="Starting cash value")
async def create_account(interaction: discord.Interaction, name: str, starting_value: float):
    if name in get_account_names():
        await interaction.response.send_message(f"Account `{name}` already exists.", ephemeral=True)
        return
    
    account_info = {
        "cash": starting_value,
        "invested": 0.0,
        "positions": {},
        "unmatched_trades": [],
        "account_history": {}, # time now with starting value
    }

    data = load_accounts()
    data[name] = account_info
    save_accounts(data)

    await interaction.response.send_message(f"Account `{name}` created with ${starting_value:,.2f}.")

@bot.tree.command(name="delete_account", description="Delete an account")
@app_commands.describe(name="Name of the account")
async def delete_account(interaction: discord.Interaction, name: str):
    if name not in get_account_names():
        await interaction.response.send_message(f"Account `{name}` does not exist.", ephemeral=True)
        return
    del load_accounts()[name]
    await interaction.response.send_message(f"Account `{name}` has been deleted.")

def daily_scheduled_report():
    pass

def show_accounts_list():
    pass

def show_historical_return():
    pass

def info():
    pass

bot.run(DISCORD_TOKEN)