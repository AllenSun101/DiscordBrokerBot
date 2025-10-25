import yfinance as yf
from datetime import datetime, timezone, timedelta

def get_asset_info(ticker: str, extended_hours: bool = False) -> tuple[tuple[float, datetime], tuple[float, datetime], str]:
    """
    Returns:
        latest_price: (float, datetime in UTC)
        previous_close: (float, datetime in UTC)
        asset_type: (str)
    """
    asset = yf.Ticker(ticker)
    asset_type = asset.info.get("quoteType")

    intraday = asset.history(period="1d", interval="1m", prepost=extended_hours)
    if intraday.empty:
        latest_price = (None, None)
    else:
        latest_row = intraday.iloc[-1]
        price = latest_row["Close"]
        timestamp = latest_row.name.to_pydatetime().astimezone(timezone.utc)
        latest_price = (float(price), timestamp)

    daily = asset.history(period="2d", interval="1d")
    if len(daily) < 2:
        previous_close = (None, None)
    else:
        prev_row = daily.iloc[-2]
        price = prev_row["Close"]
        timestamp = prev_row.name.to_pydatetime().astimezone(timezone.utc)
        previous_close = (float(price), timestamp)

    return latest_price, previous_close, asset_type

def get_five_min_data(ticker: str) -> tuple[list[datetime], list[float], float]:
    asset = yf.Ticker(ticker)
    data = asset.history(period="1d", interval="5m")
    prev_close = asset.info.get("previousClose", None)
    return data.index.to_list(), data["Close"].to_list(), prev_close

def get_extended_hours_five_min_data(ticker: str) -> tuple[list[datetime], list[float], float]:
    asset = yf.Ticker(ticker)
    data = asset.history(period="1d", interval="5m", prepost=True)
    prev_close = asset.info.get("previousClose", None)
    return data.index.to_list(), data["Close"].to_list(), prev_close

def get_hourly_data(ticker: str) -> tuple[list[datetime], list[float], float]:
    asset = yf.Ticker(ticker)
    data = asset.history(period="14d", interval="1h")

    latest_date = data.index[-1].date()
    this_week = data[data.index.date >= latest_date.replace(day=latest_date.day - 7)]
    prev_week = data[data.index.date < latest_date.replace(day=latest_date.day - 7)]

    prev_close = prev_week["Close"].iloc[-1] if not prev_week.empty else None
    return this_week.index.to_list(), this_week["Close"].to_list(), prev_close

def get_daily_data(ticker: str) -> tuple[list[datetime], list[float], float]:
    asset = yf.Ticker(ticker)
    data = asset.history(period="70d", interval="1d")
    
    if data.empty:
        return [], [], None
    
    latest_date = data.index[-1].date()
    sixty_days_ago = latest_date - timedelta(days=60)
    
    this_month = data[data.index.date >= sixty_days_ago]
    prev_month = data[data.index.date < sixty_days_ago]
    
    prev_close = prev_month["Close"].iloc[-1] if not prev_month.empty else None
    return this_month.index.to_list(), this_month["Close"].to_list(), prev_close

# price, timestamp, type = get_asset_info("BTC-USD")
# print(price, timestamp, type)
# print(get_asset_info("AAPL"))