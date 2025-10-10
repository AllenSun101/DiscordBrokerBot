import data
import datetime
from datetime import datetime, timezone
import pytz
from pydantic import BaseModel

class Order(BaseModel):
    type: str
    status: str

def get_market_open_close() -> tuple[datetime, datetime]:
    eastern = pytz.timezone("America/New_York")
    now = datetime.now(eastern)

    market_open = eastern.localize(datetime(now.year, now.month, now.day, 9, 30))
    market_close = eastern.localize(datetime(now.year, now.month, now.day, 16, 0))

    return market_open.astimezone(pytz.utc), market_close.astimezone(pytz.utc)

def market_order(ticker: str, timestamp: datetime) -> Order:

    latest_price, latest_timestamp = data.get_latest_price(ticker)
    # if ticker not found?

    # If outside of market hours, do not allow
    if latest_timestamp < timestamp:
        return Order("Market is closed.")
    # If last price was from previous day, do not allow

    market_open, market_close = get_market_open_close()
    if timestamp < market_open or timestamp > market_close:
        return Order("Market is closed.")

    if latest_timestamp >= timestamp:
        pass # fill order
    else:
        pass # reconciliation

now_utc = datetime.now(timezone.utc)
print(now_utc)