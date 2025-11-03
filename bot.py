import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv
import order
from order import Order
from collections import deque
import data
import performance
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from math import ceil
import threading
from flask import Flask
import aiohttp
from pymongo import MongoClient
import charts
from sectors import sectors

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB")]
collection = db[os.getenv("MONGO_COLLECTION")]

app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

async def keep_alive_ping():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(deployment_url) as resp:
                print(f"Pinged self ({resp.status})")
    except Exception as e:
        print(f"Ping failed: {e}")

load_dotenv() 

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID", "0"))
db_file_path = os.getenv("FILE_PATH", "")
db_path = os.path.join(db_file_path, "db.json")
deployment_url = os.getenv("DEPLOYMENT_URL", "")

not_enough_funds_message = os.getenv("NOT_ENOUGH_FUNDS_MESSAGE", "")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone=pytz.UTC)

reconciliation_orders = []

@bot.event
async def on_ready():
    await bot.tree.sync()
    if not process_reconciliation_orders.is_running():
        process_reconciliation_orders.start()
    scheduler.start()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

def get_current_date():
    now_utc = datetime.now(timezone.utc)
    return now_utc.date()

def get_prev_date():
    now_utc = datetime.now(timezone.utc)
    prev_date = now_utc.date() - timedelta(days=1)
    return prev_date

def get_current_time():
    now_utc = datetime.now(timezone.utc)
    return now_utc

def load_accounts() -> dict:
    doc = collection.find_one()

    if doc and "db" in doc:
        return doc["db"]
    else:
        return {}

def get_account_names() -> list[str]:
    accounts = load_accounts()
    return accounts.keys()

def save_accounts(data: dict) -> None:
    collection.update_one(
        {},
        {"$set": {"db": data}},
        upsert=True
    )

def evaluate_account_positions(account_name: str) -> tuple[dict, dict]:
    if account_name not in get_account_names():
        return None, None
    
    account = load_accounts()[account_name]
    account_info = {"cash": account["cash"]}
    amount_invested = 0
    
    positions_info = {}
    unmatched_trades = account["unmatched_trades"]
    for ticker in unmatched_trades:
        total_shares = 0
        total_cost = 0
        for unmatched_trade in unmatched_trades[ticker]:
            total_shares += unmatched_trade["shares"]
            total_cost += unmatched_trade["shares"] * unmatched_trade["price"]
        
        cost_basis = total_cost / total_shares

        current, prev = data.get_asset_info(ticker)[:2]
        current_price = current[0]
        prev_price = prev[0]
        if prev_price is None:
            prev_price = current_price

        total_value = current_price * total_shares
        prev_value = prev_price * total_shares
        amount_invested += total_value
        pnl = total_value - total_cost
        day_pnl = total_value - prev_value
        day_change = day_pnl / prev_value * 100
        
        positions_info[ticker] = {
            "shares": total_shares,
            "price": current_price,
            "cost_basis": cost_basis,
            "total_value": total_value,
            "pnl": pnl,
            "day_pnl": day_pnl,
            "day_change": day_change,
        }

    account_info["invested"] = amount_invested
    current_value = amount_invested + account_info["cash"]
    previous_value = list(account["account_history"].values())[-1]["value"]

    account_info["account_value"] = current_value
    day_pnl = current_value - previous_value
    day_change = day_pnl / previous_value * 100

    account_info["day_pnl"] = day_pnl
    account_info["day_change"] = day_change

    return positions_info, account_info   

def record_filled_order(account: dict, transaction: str, order: Order) -> tuple[dict, str]:
    shares = order.shares if transaction == "BUY" else -order.shares
    total_cost = shares * order.fill_price
    trade = {
        "shares": shares,
        "price": order.fill_price
    }

    if transaction == "BUY" and account["cash"] < total_cost:
        return account, "Not enough funds"
    
    account["cash"] -= total_cost

    if order.ticker not in account["positions"]:
        account["positions"][order.ticker] = shares
        account["unmatched_trades"][order.ticker] = [trade]
    else:
        if transaction == "BUY" and account["positions"][order.ticker] > 0:
            account["positions"][order.ticker] += shares
            account["unmatched_trades"][order.ticker].append(trade)
        elif transaction == "BUY" and account["positions"][order.ticker] < 0:
            updated_shares = account["positions"][order.ticker] + shares
            account["positions"][order.ticker] = updated_shares
            if updated_shares > 0:
                account["unmatched_trades"][order.ticker] = [{
                    "shares": updated_shares,
                    "price": order.fill_price
                }]
            elif updated_shares == 0:
                del account["positions"][order.ticker]
                del account["unmatched_trades"][order.ticker]
            else:
                unmatched_trades = deque(account["unmatched_trades"][order.ticker])
                shares_remaining = shares
                while shares_remaining > 0:
                    if abs(unmatched_trades[0]["shares"]) > shares_remaining:
                        unmatched_trades[0]["shares"] += shares_remaining
                        shares_remaining = 0
                    else:
                        shares_remaining += unmatched_trades[0]["shares"]
                        unmatched_trades.popleft()
                account["unmatched_trades"][order.ticker] = list(unmatched_trades)
        elif transaction == "SELL" and account["positions"][order.ticker] < 0:
            account["positions"][order.ticker] += shares
            account["unmatched_trades"][order.ticker].append(trade)
        elif transaction == "SELL" and account["positions"][order.ticker] > 0:
            updated_shares = account["positions"][order.ticker] + shares
            account["positions"][order.ticker] = updated_shares
            if updated_shares < 0:
                account["positions"][order.ticker] = updated_shares
                account["unmatched_trades"][order.ticker] = [{
                    "shares": updated_shares,
                    "price": order.fill_price
                }]
            elif updated_shares == 0:
                del account["positions"][order.ticker]
                del account["unmatched_trades"][order.ticker]
            else:
                unmatched_trades = deque(account["unmatched_trades"][order.ticker])
                shares_remaining = shares
                while shares_remaining < 0:
                    if unmatched_trades[0]["shares"] > abs(shares_remaining):
                        unmatched_trades[0]["shares"] += shares_remaining
                        shares_remaining = 0
                    else:
                        shares_remaining += unmatched_trades[0]["shares"]
                        unmatched_trades.popleft()
                account["unmatched_trades"][order.ticker] = list(unmatched_trades)
    return account, "Filled"    

@tasks.loop(minutes=1)
async def process_reconciliation_orders():
    global reconciliation_orders

    channel = bot.get_channel(ALLOWED_CHANNEL_ID)
    unfilled_reconciliation_orders = []

    if not reconciliation_orders:
        return
    
    for reconciliation_order in reconciliation_orders:
        account_name = reconciliation_order["account"]
        order_info = reconciliation_order["order"]
        transaction = reconciliation_order["transaction"]
        
        if account_name not in get_account_names():
            await channel.send(f"Account `{account_name}` does not exist.")
            continue

        accounts = load_accounts()
        account = accounts[account_name]
        order_object = order.market_order(order_info.ticker, order_info.shares, order_info.timestamp)

        if order_object.status == "Invalid ticker":
            await channel.send(f"Ticker `{order_object.ticker}` invalid.")
            continue
        elif order_object.status == "Market is closed":
            await channel.send(f"Market is closed")
            continue
        elif order_object.status == "Reconciliation":
            unfilled_reconciliation_orders.append({
                "account": account_name,
                "transaction": transaction,
                "order": order_object
            })
            continue
        elif order_object.status == "Filled":
            updated_account, status = record_filled_order(account, transaction, order_object)
            if status == "Not enough funds":
                await channel.send(f"Not enough account funds in {account_name}")
            elif status == "Filled":
                accounts[account_name] = updated_account
                save_accounts(accounts)
                await channel.send(
                    f"😎 Market order filled: {transaction} {order_info.shares} shares of {order_info.ticker} at ${order_object.fill_price:,.2f} for {account_name}.",
                )

    reconciliation_orders = unfilled_reconciliation_orders

@bot.tree.command(name="market_order", description="Enter a market order")
@app_commands.describe(
    account_name="Account name",
    transaction="Transaction type",
    ticker="Stock ticker",
    shares="Number of shares"
)
@app_commands.choices(transaction=[
    app_commands.Choice(name="BUY", value="BUY"),
    app_commands.Choice(name="SELL", value="SELL")
])
async def execute_market_order(interaction: discord.Interaction, account_name: str, 
                               transaction: str, ticker: str, shares: int):
    global reconciliation_orders

    await keep_alive_ping()

    if account_name not in get_account_names():
        await interaction.response.send_message(f"Account `{account_name}` does not exist.")
        return
    
    await interaction.response.defer(thinking=True)  
    
    accounts = load_accounts()
    account = accounts[account_name]
    order_object = order.market_order(ticker, shares, get_current_time())

    if order_object.status == "Invalid ticker":
        await interaction.followup.send(f"Ticker `{ticker}` invalid.")
        return
    elif order_object.status == "Market is closed":
        await interaction.followup.send(f"Market is closed")
        return
    elif order_object.status == "Reconciliation":
        reconciliation_orders.append({
            "account": account_name,
            "transaction": transaction,
            "order": order_object
        })
        await interaction.followup.send(f"Order pending")
        return
    elif order_object.status == "Filled":
        updated_account, status = record_filled_order(account, transaction, order_object)
        if status == "Not enough funds":
            await interaction.followup.send(f"Not enough account funds in {account_name}")
            return 
        elif status == "Filled":
            accounts[account_name] = updated_account
            save_accounts(accounts)
            await interaction.followup.send(
                f"😎 Market order filled: {transaction} {shares} shares of {ticker} at ${order_object.fill_price:,.2f} for {account_name}.",
            )

@bot.tree.command(name="portfolio_summary", description="Show portfolio summary")
@app_commands.describe(name="Account name")
async def portfolio_summary(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    positions_info, account_info = evaluate_account_positions(name)
    if positions_info is None:
        await interaction.followup.send(f"Account `{name}` does not exist.")
        return

    headers = ["Ticker", "Shares", "Price", "Day Change", "Value", "Cost Basis", "P/L", "Day P/L"]
    rows = []

    for ticker, pos in positions_info.items():
        rows.append([
            ticker,
            str(pos["shares"]),
            f"${pos['price']:,.2f}",
            f"${pos['day_change']:+,.2f}",
            f"${pos['total_value']:,.2f}",
            f"${pos['cost_basis']:,.2f}",
            f"{pos['pnl']:+,.2f}",
            f"{pos['day_pnl']:+,.2f}"
        ])

    col_widths = [
        max(len(str(value)) for value in [header] + [row[i] for row in rows])
        for i, header in enumerate(headers)
    ]

    header_line = " ".join(f"{header:^{col_widths[i]}}" for i, header in enumerate(headers))
    separator = " ".join("-" * col_widths[i] for i in range(len(headers)))
    data_lines = "\n".join(
        " ".join(f"{row[i]:^{col_widths[i]}}" for i in range(len(headers))) for row in rows
    )

    report = (
        f"Portfolio Summary for `{name}`\n"
        f"Total Value: ${account_info['account_value']:,.2f}\n"
        f"Invested: ${account_info['invested']:,.2f}\n"
        f"Cash: ${account_info['cash']:,.2f}\n\n"
        f"{header_line}\n{separator}\n{data_lines}"
    )

    await interaction.followup.send(report)

@bot.tree.command(name="create_account", description="Create a trading account")
@app_commands.describe(name="Name of your account", starting_value="Starting cash value")
async def create_account(interaction: discord.Interaction, name: str, starting_value: float):
    if name in get_account_names():
        await interaction.response.send_message(f"Account `{name}` already exists.")
        return
    
    account_history = {str(get_prev_date()): {"value": starting_value, "return": 0}}
    
    account_info = {
        "cash": starting_value,
        "positions": {},
        "unmatched_trades": {},
        "account_history": account_history,
    }

    data = load_accounts()
    data[name] = account_info
    save_accounts(data)

    await interaction.response.send_message(f"Account `{name}` created with ${starting_value:,.2f}.")

@bot.tree.command(name="delete_account", description="Delete an account")
@app_commands.describe(name="Name of the account")
async def delete_account(interaction: discord.Interaction, name: str):
    if name not in get_account_names():
        await interaction.response.send_message(f"Account `{name}` does not exist.")
        return
    accounts = load_accounts()
    del accounts[name]
    save_accounts(accounts)
    await interaction.response.send_message(f"Account `{name}` has been deleted.")

@bot.tree.command(name="accounts_list", description="Show list of accounts")
async def show_accounts_list(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    report = f"Accounts list:\n"
    for account in load_accounts():
        account_info = evaluate_account_positions(account)[1]
        account_value = account_info["account_value"]
        day_pnl = account_info["day_pnl"]
        day_change = account_info["day_change"]
        if day_pnl > 0:
            report += f"- {account}: ${account_value:,.2f} (🟢 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
        elif day_pnl < 0:
            report += f"- {account}: ${account_value:,.2f} (🔴 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
        else:
            report += f"- {account}: ${account_value:,.2f} (⚪ {day_pnl:+,.2f} {day_change:+,.2f}%)\n"

    await interaction.followup.send(report)

@bot.tree.command(name="pending_orders", description="Show pending orders")
async def get_pending_orders(interaction: discord.Interaction):
    global reconciliation_orders

    await keep_alive_ping()

    report = f"Pending orders:\n"
    for reconciliation_order in reconciliation_orders:
        account = reconciliation_order["account"]
        transaction = reconciliation_order["transaction"]
        order_type = reconciliation_order["order"].type
        ticker = reconciliation_order["order"].ticker
        shares = reconciliation_order["order"].shares
        report += f"- {account}: {order_type} order {transaction} for {shares} shares of {ticker}\n"

    await interaction.response.send_message(report)

@bot.tree.command(name="account_history", description="Get account history plot")
@app_commands.describe(name="Name of your account")
async def account_history(interaction: discord.Interaction, name: str):
    if name not in get_account_names():
        await interaction.response.send_message(f"Account `{name}` does not exist.")
        return

    account_history = load_accounts()[name]["account_history"]
    buf = performance.get_history_plot(name, account_history)
    file = discord.File(fp=buf, filename=f"{name}_history.png")
    await interaction.response.send_message(file=file)

@bot.tree.command(name="account_returns", description="Get account returns plot")
@app_commands.describe(name="Name of your account")
async def account_returns(interaction: discord.Interaction, name: str):
    if name not in get_account_names():
        await interaction.response.send_message(f"Account `{name}` does not exist.")
        return

    account_history = load_accounts()[name]["account_history"]
    buf = performance.get_returns_plot(name, account_history)
    file = discord.File(fp=buf, filename=f"{name}_returns.png")
    await interaction.response.send_message(file=file)

@bot.tree.command(name="multi_account_returns", description="Get account returns plot for all accounts")
async def multi_account_returns(interaction: discord.Interaction):
    accounts = {}
    account_infos = load_accounts()
    for account in account_infos:
        accounts[account] = account_infos[account]["account_history"]
    buf = performance.get_multi_returns_plot(accounts)
    file = discord.File(fp=buf, filename=f"multi_returns.png")
    await interaction.response.send_message(file=file)

@bot.tree.command(name="info", description="Show bot info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(
        (
            "Use commands to manage accounts and trade. "
            "A market order will execute your order at the current market price. "
            "Pending orders can be rejected if you do not have sufficient funds."
        )
    )

@app_commands.describe(
    sector="Stock sector",
)
@app_commands.choices(sector=[
    app_commands.Choice(name="Information Technology", value="Information Technology"),
    app_commands.Choice(name="Communication Services", value="Communication Services"),
    app_commands.Choice(name="Consumer Discretionary", value="Consumer Discretionary"),
    app_commands.Choice(name="Consumer Staples", value="Consumer Staples"),
    app_commands.Choice(name="Financials", value="Financials"),
    app_commands.Choice(name="Healthcare", value="Healthcare"),
    app_commands.Choice(name="Industrials", value="Industrials"),
    app_commands.Choice(name="Energy", value="Energy"),
    app_commands.Choice(name="Materials", value="Materials"),
    app_commands.Choice(name="Utilities", value="Utilities"),
    app_commands.Choice(name="Real Estate", value="Real Estate"),
])
@bot.tree.command(name="sector_tickers", description="Show tickers by sector")
async def info(interaction: discord.Interaction, sector: str):
    sector_tickers = sectors[sector]
    tickers_per_page = 20

    formatted_tickers = [f"{ticker}: {name}" for ticker, name in sector_tickers.items()]

    pages = [
        formatted_tickers[i:i + tickers_per_page]
        for i in range(0, len(formatted_tickers), tickers_per_page)
    ]

    class CatalogView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.page = 0

        async def update_message(self, interaction: discord.Interaction):
            embed = discord.Embed(
                title=f"{sector} Tickers",
                description="\n".join(pages[self.page]),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Page {self.page + 1}/{len(pages)}")
            await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page -= 1
            elif self.page == 0:
                self.page = len(pages) - 1
            await self.update_message(interaction)

        @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page < len(pages) - 1:
                self.page += 1
            elif self.page == len(pages) - 1:
                self.page = 0
            await self.update_message(interaction)

    first_embed = discord.Embed(
        title=f"{sector} Tickers",
        description="\n".join(pages[0]),
        color=discord.Color.blue()
    )
    first_embed.set_footer(text=f"Page 1/{len(pages)}")
    await interaction.response.send_message(embed=first_embed, view=CatalogView())

@bot.tree.command(name="getquote", description="Show quote info")
@app_commands.describe(ticker="Stock Ticker")
async def get_quote(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(thinking=True)

    await keep_alive_ping()

    latest_price, previous_close, asset_type = data.get_asset_info(ticker, True)

    if latest_price is None:
        await interaction.followup.send(f"Ticker `{ticker}` is invalid.")

    report = f"{ticker}: ${round(latest_price[0], 2)} "

    day_pnl = latest_price[0] - previous_close[0]
    day_change = day_pnl / previous_close[0] * 100

    if day_pnl > 0:
        report += f"(🟢 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
    elif day_pnl < 0:
        report += f"(🔴 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
    else:
        report += f"(⚪ {day_pnl:+,.2f} {day_change:+,.2f}%)\n"

    market_open, market_close = order.get_market_open_close()
    current_time = get_current_time()

    if get_current_date() != latest_price[1].date():
        report += f"Market Closed"
    elif asset_type == "EQUITY" and (current_time < market_open or current_time > market_close):
        report += f"Market Closed"
    else:
        estimated_delay = ceil((current_time - latest_price[1]).total_seconds() / 60)
        report += f"Estimated Delay: {estimated_delay} minutes"

    await interaction.followup.send(report)

@bot.tree.command(name="five_minute_chart", description="Get 5 minute chart for a ticker")
@app_commands.describe(ticker="Stock Ticker")
async def five_minute_chart(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    buf = charts.close_chart(ticker, "5 minute")
    file = discord.File(fp=buf, filename=f"five_minute_chart.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="extended_hours_five_minute_chart", description="Get extended hours 5 minute chart for a ticker")
async def extended_hours_five_minute_chart(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    buf = charts.close_chart(ticker, "5 minute extended hours")
    file = discord.File(fp=buf, filename=f"extended_hours_five_minute_chart.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="hourly_chart", description="Get hourly chart for a ticker")
@app_commands.describe(ticker="Stock Ticker")
async def hourly_chart(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    buf = charts.close_chart(ticker, "hourly")
    file = discord.File(fp=buf, filename=f"hourly_chart.png")
    await interaction.followup.send(file=file)

@bot.tree.command(name="daily_chart", description="Get daily chart for a ticker")
@app_commands.describe(ticker="Stock Ticker")
async def daily_chart(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(thinking=True)  

    await keep_alive_ping()

    buf = charts.close_chart(ticker, "daily")
    file = discord.File(fp=buf, filename=f"daily_chart.png")
    await interaction.followup.send(file=file)

@scheduler.scheduled_job('cron', hour=2, minute=50, second=0)
async def daily_scheduled_report():
    channel = bot.get_channel(ALLOWED_CHANNEL_ID)

    report = f"Daily update:\n"
    updated_accounts = load_accounts()
    accounts = load_accounts()
    for account_name in accounts:
        account = accounts[account_name]
        account_info = evaluate_account_positions(account_name)[1]
        account_value = account_info["account_value"]
        day_pnl = account_info["day_pnl"]
        day_change = account_info["day_change"]
        if day_pnl > 0:
            report += f"- {account_name}: ${account_value:,.2f} (🟢 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
        elif day_pnl < 0:
            report += f"- {account_name}: ${account_value:,.2f} (🔴 {day_pnl:+,.2f} {day_change:+,.2f}%)\n"
        else:
            report += f"- {account_name}: ${account_value:,.2f} (⚪ {day_pnl:+,.2f} {day_change:+,.2f}%)\n"

        starting_value = list(account["account_history"].values())[0]["value"]
        pnl = account_value - starting_value
        account_return = round(pnl / starting_value * 100, 2)
        
        updated_accounts[account_name]["account_history"][str(get_prev_date())] = {
            "value": account_value,
            "return": account_return
        }
    
    save_accounts(updated_accounts)
    await channel.send(report)

keep_alive()
bot.run(DISCORD_TOKEN)
