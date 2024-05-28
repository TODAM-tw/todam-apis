from datetime import datetime, timedelta, timezone


def convert_timestamp_to_utc_plus_8(timestamp: int) -> str:
    # Convert milliseconds to seconds
    if timestamp > 1e10:  # Check if timestamp is likely in milliseconds
        timestamp /= 1000  # Convert from milliseconds to seconds

    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    utc_plus_8 = timezone(timedelta(hours=8))
    time_in_utc_plus_8 = utc_time.astimezone(utc_plus_8)

    format = "%Y-%m-%d %H:%M:%S"
    time_in_utc_plus_8 = time_in_utc_plus_8.strftime(format)

    return time_in_utc_plus_8
