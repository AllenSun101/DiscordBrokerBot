import yfinance as yf
from datetime import datetime, timezone

def get_asset_info(ticker: str) -> tuple[tuple[float, datetime], tuple[float, datetime], str]:
    """
    Returns:
        latest_price: (float, datetime in UTC)
        previous_close: (float, datetime in UTC)
        asset_type: (str)
    """
    asset = yf.Ticker(ticker)
    asset_type = asset.info.get("quoteType")

    intraday = asset.history(period="1d", interval="1m")
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

# price, timestamp, type = get_asset_info("BTC-USD")
# print(price, timestamp, type)