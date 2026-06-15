import requests
import urllib3
urllib3.disable_warnings()

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "appid": "109",
    "systemid": "109",
    "clientid": "d3skt0p",
    "Referer": "https://www.naukri.com/",
    "Origin": "https://www.naukri.com",
}

# Step 1: homepage for cookies
r0 = session.get("https://www.naukri.com/", headers=headers, verify=False, timeout=20)
print("Homepage:", r0.status_code, "Cookies:", list(session.cookies.keys()))

# Step 2: API
params = {
    "noOfResults": "20",
    "urlType": "search_by_key_loc",
    "searchType": "adv",
    "keyword": "QA Automation Engineer",
    "location": "Pune",
    "pageNo": "1",
    "experience": "3",
    "src": "jobsearchDesk",
}
r1 = session.get(
    "https://www.naukri.com/jobapi/v3/search",
    params=params, headers=headers, verify=False, timeout=20
)
print("API status:", r1.status_code)
print("API body preview:", r1.text[:300])
if r1.status_code == 200:
    data = r1.json()
    print("Jobs:", len(data.get("jobDetails", [])))
