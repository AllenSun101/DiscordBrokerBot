import data
import datetime
from datetime import datetime, timezone
import pytz
from pydantic import BaseModel

class Order(BaseModel):
    type: str
    ticker: str
    shares: int
    fill_price: float
    timestamp: datetime
    status: str

def get_market_open_close() -> tuple[datetime, datetime]:
    eastern = pytz.timezone("America/New_York")
    now = datetime.now(eastern)

    market_open = eastern.localize(datetime(now.year, now.month, now.day, 4, 0))
    market_close = eastern.localize(datetime(now.year, now.month, now.day, 20, 0))

    return market_open.astimezone(pytz.utc), market_close.astimezone(pytz.utc)

def market_order(ticker: str, shares: int, timestamp: datetime) -> Order:
    print(ticker, shares, timestamp)
    latest, prev, asset_type = data.get_asset_info(ticker, extended_hours=True)
    latest_price, latest_timestamp = latest
    print(latest_price, latest_timestamp)
    market_open, market_close = get_market_open_close()
    
    if latest_price is None:
        return Order(type="market", ticker=ticker, shares=0, fill_price=0, timestamp=timestamp, status="Invalid ticker")
        
    timestamp_date = latest_timestamp.date()
    current_date = timestamp.date()

    if timestamp_date != current_date:
        return Order(type="market", ticker=ticker, shares=0, fill_price=0, timestamp=timestamp, status="Market is closed")
    elif asset_type == "EQUITY" and (timestamp < market_open or timestamp > market_close):
        return Order(type="market", ticker=ticker, shares=0, fill_price=0, timestamp=timestamp, status="Market is closed")
    elif timestamp.replace(second=0, microsecond=0) > latest_timestamp.replace(second=0, microsecond=0):
        return Order(type="market", ticker=ticker, shares=shares, fill_price=0, timestamp=timestamp, status="Reconciliation")
    else:
        return Order(type="market", ticker=ticker, shares=shares, fill_price=latest_price, timestamp=timestamp, status="Filled")

# now_utc = datetime.now(timezone.utc)
# print(market_order("AAPL", now_utc))