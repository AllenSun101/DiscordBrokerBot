import yfinance as yf

def get_latest_price(ticker: str) -> tuple[float, str]:
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d", interval="1m")
    if data.empty:
        return None, None
    latest_row = data.iloc[-1]
    price = latest_row["Close"]
    timestamp = latest_row.name.to_pydatetime()
    return float(price), timestamp

# price, timestamp = get_latest_price("BTC-USD")
# print(price, timestamp)