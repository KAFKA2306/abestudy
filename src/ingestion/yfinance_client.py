import pandas as pd
import yfinance as yf
from zoneinfo import ZoneInfo


def fetch_series(ticker, start, end, timezone):
    data = yf.download(
        ticker,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )[["Adj Close", "Volume"]]
    data.columns = ["close", "volume"]
    index = pd.DatetimeIndex(data.index).tz_localize("UTC").tz_convert(ZoneInfo(timezone))
    data.index = index
    return data.dropna()


def collect(tickers, start, end, timezone):
    return {ticker: fetch_series(ticker, start, end, timezone) for ticker in tickers}
