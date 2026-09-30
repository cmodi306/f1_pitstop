from datetime import datetime, timezone, timedelta
import requests

gmt_country_list = {
                    "Germany": {"hours": 2, "mins": 0},
                    "India": {"hours": 5, "mins": 30},
                   }

def get_local_date_time(date_start, gmt_offset_hrs, gmt_offset_mins):
    gmt_shift =  timezone(timedelta(hours=gmt_offset_hrs, minutes=gmt_offset_mins))
    dt = date_start.astimezone(gmt_shift)
    return dt.date().strftime("%Y-%m-%d"), dt.time().strftime("%H:%M")
    
def get_f1_calendar(year, ego_country="Germany"):
    url = f"https://api.openf1.org/v1/sessions?year={year}"
    response = requests.get(url=url)
    if response.status_code == 200:
        response_data = response.json()
        calendar = []
        for data in response_data:
            start_date, start_time = get_local_date_time(
                                                datetime.fromisoformat(data.get("date_start")), 
                                                gmt_country_list[ego_country]["hours"],
                                                gmt_country_list[ego_country]["mins"]
                                            )
            calendar.append({
                "country"       : data.get("country_name"),
                "location"      : data.get("location"),
                "session_key"   : data.get("session_key"),
                "session_type"  : data.get("session_type"),
                "start_date"    : start_date,
                "start_time"    : start_time,
                })
        return(calendar)
    else:
        raise "Error fetching data from API."

def get_drivers():
    drivers = []
    url = f"https://api.openf1.org/v1/drivers"
    response = requests.get(url=url)
    if response.status_code == 200:
        data = response.json()
        i = 0
        for driver in data:
            if driver.get("full_name") not in drivers:
                drivers.append(driver.get("full_name"))
                print(driver)

get_drivers()