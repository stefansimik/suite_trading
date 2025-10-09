import os

from dotenv import load_dotenv
import typing
import csv
import logging
import requests
import re
import hashlib
from urllib.parse import urlparse, quote
from datetime import datetime, timezone, timedelta
from decimal import Decimal

FMP_CODE_LIMIT_REACHED = 429
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30

"""
1. Go to https://site.financialmodelingprep.com/ and create an account.
   If you chose the the free account, you cannot load so much data per day and need to run the script next day again.
   The fmp response is cached, so the request are not called twice.
2. Create .env file with your apikey.
   The apikey is not stored in the script.
   Format apikey='01234567890abcdef'
3. adjust the values below and run the script.
"""
# INPUT
SYMBOL: str = "EURUSD"
FROM_DT: str = "2015-01-01"
TO_DT: str = "2025-07-31"
# 1week, 1day, 4hour, 1hour, 30min, 15min, 5min, 1min
PERIOD: str = "5min"
# OUTPUT
CSV_OUTPUT_PATH: str = "../../../../../res/data"
CACHE_PATH: str = "../../../../../res/cache"

# load apikey from .env file
load_dotenv()
apikey = os.environ.get("apikey")


def store_to_cache(url, query_vars, content):
    """
    create a valid filename from url and query params except the apikey and store the content into the file
    :param url:
    :param query_vars:
    :param content:
    :return:
    """
    file_path = create_file_path(query_vars, url)
    try:
        with open(file_path, "wb") as f:
                f.write(content)
        print(f"Cached response to {file_path}")
    except Exception as e:
        logging.warning(f"Failed to cache response to {file_path}: {e}")

def read_from_cache(url, query_vars):
    file_path = create_file_path(query_vars, url)
    # if the file not exists return None
    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            with open(file_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"Failed to read from cache {file_path}: {e}")
    return None

def create_file_path(query_vars, url):
    """
    Encodes the url and parameters from query_vars into a file path. This is used to cache the response.
    :param query_vars:
    :param url:
    :return:
    """
    parsed = urlparse(url)
    # Build canonical parts: base path and sorted query without apikey
    filtered_qs = {k: v for k, v in (query_vars or {}).items() if k and k.lower() != "apikey" and v is not None}
    sorted_items = sorted(filtered_qs.items(), key=lambda kv: kv[0])
    base = f"{parsed.netloc}{parsed.path}".strip("/")
    base = base.replace("/", "_")
    # Create a stable, URL-encoded query segment
    if sorted_items:
        qs_segment = "&".join(f"{quote(str(k), safe='')}"
                              f"={quote(str(v), safe='')}" for k, v in sorted_items)
        name = f"{base}__{qs_segment}"
    else:
        name = base
    # Sanitize to filesystem-friendly
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    # Bound length and add hash tail if necessary
    if len(sanitized) > 240:
        tail = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        sanitized = f"{sanitized[:200]}__{tail}"
    # Guess extension
    ext = "txt"
    # Ensure cache directory
    cache_dir = os.path.join(os.getcwd(), CACHE_PATH)
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{sanitized}.{ext}")
    return file_path

def get_historical_chart(
        _period: str, _symbol: str,
        from_date: datetime, to_date: datetime):
    """
    The single call to FMP with the given parameter.
    :param _period:
    :param _symbol:
    :param from_date:
    :param to_date:
    :return:
    """
    urlpath = f"historical-chart/{_period}/{_symbol}"
    query_vars = {
        "apikey": apikey,
        "from": from_date.strftime("%Y-%m-%d"),
        "to": to_date.strftime("%Y-%m-%d")
    }
    # https://financialmodelingprep.com:443/api/v3/historical-chart/1week/EURUSD?from=2024-07-07&to=2025-07-13&apikey=<abcde0123456789>
    url = f"https://financialmodelingprep.com:443/api/v3/{urlpath}"
    return_var = None
    content = read_from_cache(url, query_vars)
    if content is None:
        print(f"FMP: Requesting {urlpath} to {to_date}")
        response = requests.get(
            url, params=query_vars, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
        )
        if response.status_code == FMP_CODE_LIMIT_REACHED:
            raise Exception(f"FMP: Limit reached. Abort (Free account=> come back next day, Paid account => don't run multiple scripts in parallel.)")
        if len(response.content) > 0:
            return_var = response.json()
            # store to cache
            store_to_cache(url, query_vars, response.content)
            content = response.content
    else:
        print(f"Use cached request {urlpath} to {to_date}")
        # convert content to dict
        return_var = eval(content)

    if len(content) == 0 or (
        isinstance(return_var, dict) and len(return_var.keys()) == 0
        ):
        # logging.warning("Response appears to have no data. Returning empty List.")
        return_var = []

    print(f"received {return_var[0]['date']} until {return_var[-1]['date']}")
    return return_var

def write_bars_to_csv(bars: typing.Union[list, dict], _period: str, out_csv_path: str) -> str:
    """
    Write bars to CSV with header:
    start_dt,end_dt,open,high,low,close,volume

    Input bars are items with fields: date, open, high, low, close, volume.
    Dates are assumed UTC ('YYYY-MM-DD HH:MM:SS'). The end_dt is computed from the period.
    Returns the output CSV path.
    """
    # Normalize bars into a list of dicts
    if isinstance(bars, dict):
        # Accept common wrappers like {"historical": [...]} or direct single bar dict
        if "historical" in bars and isinstance(bars["historical"], list):
            records = bars["historical"]
        else:
            records = [bars]
    else:
        records = list(bars or [])

    # Map period strings to timedeltas
    def _period_delta(p: str) -> timedelta:
        p = (p or "").lower()
        if p in ("1week", "1w", "week", "w1"):
            return timedelta(days=7)
        if p in ("1day", "1d", "day", "d1"):
            return timedelta(days=1)
        if p in ("4hour", "4h"):
            return timedelta(hours=4)
        if p in ("1hour", "1h"):
            return timedelta(hours=1)
        if p in ("30min", "30m"):
            return timedelta(minutes=30)
        if p in ("15min", "15m"):
            return timedelta(minutes=15)
        if p in ("5min", "5m"):
            return timedelta(minutes=5)
        if p in ("1min", "1m"):
            return timedelta(minutes=1)
        # Default to 1 day if unknown
        return timedelta(days=1)

    delta = _period_delta(_period)

    def _parse_start_utc(s: str) -> datetime:
        # Incoming format example: "2025-08-18 00:00:00"
        dt = datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)

    def _end_from_start(start: datetime) -> datetime:
        # Inclusive end
        return start + delta

    def _fmt_dt(dt: datetime) -> str:
        return dt.isoformat().replace("+00:00", "+00:00")

    def _fmt_price(x: typing.Any) -> str:
        return f"{Decimal(str(x)):.5f}"

    def _fmt_volume(v: typing.Any) -> str:
        if v is None or v == "":
            return ""
        return str(int(Decimal(str(v))))

    os.makedirs(os.path.dirname(out_csv_path) or ".", exist_ok=True)
    with open(out_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["start_dt", "end_dt", "open", "high", "low", "close", "volume"])

        # check that each date is unique
        seen_dates: set[str] = set()

        for r in records:
            if not isinstance(r, dict):
                continue
            date_str = r.get("date")
            if not date_str:
                continue

            # check for already seen dates, skip duplicate entries (should not happen, but just in case)
            if date_str in seen_dates:
                continue
            seen_dates.add(date_str)

            start_dt = _parse_start_utc(date_str)
            end_dt = _end_from_start(start_dt)

            writer.writerow([
                _fmt_dt(start_dt),
                _fmt_dt(end_dt),
                _fmt_price(r.get("open")),
                _fmt_price(r.get("high")),
                _fmt_price(r.get("low")),
                _fmt_price(r.get("close")),
                _fmt_volume(r.get("volume")),
            ])

    return out_csv_path

def bulk_load(_period: str, _symbol: str,
              from_date: str, to_date: str):
    """
    Main call in the script to handle the result from FMP and call the next fetch request.
    :param _period:
    :param _symbol:
    :param from_date:
    :param to_date:
    :return:
    """
    def _parse_dt_utc(s: str) -> datetime:
        # Incoming format example: "2025-08-18"
        dt = datetime.strptime(s.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)

    def _filter_bars_before(_bars: typing.Iterable[dict], cutoff_utc: datetime) -> list[dict]:
        """
        Filter our bars before cutoff_utc (remove overlapping bars)
        :param _bars:
        :param cutoff_utc:
        :return:
        """
        out = []
        for r in _bars or []:
            if not isinstance(r, dict):
                continue
            ds = r.get("date")
            if not ds:
                continue
            dt = datetime.strptime(str(ds).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if dt <= cutoff_utc:
                out.append(r)
            #else:
            #    print(f"ignoring overlapping bar: {dt} <= {cutoff_utc}")
        return out

    f = _parse_dt_utc(from_date)
    t = _parse_dt_utc(to_date)
    print(f"fetching data from {f} to {t}")
    far = datetime.strptime("1970-01-01", "%Y-%m-%d")
    if f > t:
        raise ValueError(f"from_date ({f}) must be before to_date ({t})")
    res = []
    oldest = None
    gap_tries = 0
    while f <= t:
        bars = get_historical_chart(_period=_period, _symbol=_symbol, from_date=far, to_date=t)
        if (oldest is not None) and bars:
            # filter out all bars that are before the oldest date
            cutoff = datetime.strptime(str(oldest["date"]).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            bars = _filter_bars_before(bars, cutoff)
        res.extend(bars)
        #print(f"current data: from {_parse_dt_utc(result[0]["date"][:10])} to {_parse_dt_utc(result[-1]["date"][:10])}")
        # get oldest received bar
        oldest = bars[-1]
        new_oldest = _parse_dt_utc(oldest["date"][:10])
        if new_oldest == t:
            gap_tries = gap_tries + 1
            new_oldest = new_oldest - timedelta(days=1)
            print(f"!!!!!!!!!!! WARNING #{gap_tries} !!!!!!!!!!!!: no new data received. Try to skip one day: {new_oldest}")
        t = new_oldest
        #print("new oldest: ", t)
    return res


# main call
result = bulk_load(_period=PERIOD, _symbol=SYMBOL, from_date=FROM_DT, to_date=TO_DT)
path = write_bars_to_csv(result, PERIOD, f"{CSV_OUTPUT_PATH}/bars_{SYMBOL}_{PERIOD}_{FROM_DT}_{TO_DT}.csv")
print (path)
