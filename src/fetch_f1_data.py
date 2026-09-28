from datetime import datetime, timezone, timedelta
import requests

def get_local_time(date_start, gmt_offset_hrs, gmt_offset_mins):
    gmt_shift =  timezone(timedelta(hours=gmt_offset_hrs, minutes=gmt_offset_mins))
    return date_start.astimezone(gmt_shift)
    
def get_session_id(year):
    url = f"https://api.openf1.org/v1/sessions?year={year}"
    response = requests.get(url=url).json()
    for data in response:
        session_key = data.get("session_key")
        country = data.get("country_name")
        location = data.get("location")
        date_start = get_local_time(
                    datetime.fromisoformat(data.get("date_start")), 2, 00)
        if country == "Bahrain":
            print(date_start)
                   
get_session_id(2026)


