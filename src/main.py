import requests

url = "https://api.openf1.org/v1/car_data?driver_number=55&session_key=latest"

response = requests.get(url=url)

print(response.text)
