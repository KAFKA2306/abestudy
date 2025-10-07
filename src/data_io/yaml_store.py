import pandas as pd
import yaml


def save_frames(frames, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for ticker, frame in frames.items():
        records = [{"timestamp": str(index.isoformat()), "close": float(row["close"]), "volume": float(row["volume"])} for index, row in frame.iterrows()]
        (directory / f"{ticker}.yaml").write_text(yaml.safe_dump(records, sort_keys=False), encoding="utf-8")


def load_frames(tickers, directory):
    frames = {}
    for ticker in tickers:
        records = yaml.safe_load((directory / f"{ticker}.yaml").read_text(encoding="utf-8"))
        frame = pd.DataFrame(records)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame = frame.set_index("timestamp").sort_index()
        frames[ticker] = frame
    return frames
