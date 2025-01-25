import os
import requests
from dotenv import load_dotenv

# Load .env so environment variables are available
load_dotenv()

# Pull from environment variables
BUILDIUM_CLIENT_ID = os.getenv("BUILDIUM_CLIENT_ID", "FAKE_ID")
BUILDIUM_CLIENT_SECRET = os.getenv("BUILDIUM_CLIENT_SECRET", "FAKE_SECRET")

LEASES_URL = "https://api.buildium.com/v1/leases"
OUTSTANDING_BALANCES_URL = "https://api.buildium.com/v1/leases/outstandingbalances"
PROPERTIES_URL = "https://api.buildium.com/v1/rentals"
UNITS_URL = "https://api.buildium.com/v1/rentals/units"

headers = {
    "x-buildium-client-id": BUILDIUM_CLIENT_ID,
    "x-buildium-client-secret": BUILDIUM_CLIENT_SECRET,
    "Content-Type": "application/json"
}


def fetch_all_leases(lease_statuses=("Active",)):
    offset = 0
    limit = 100
    all_leases = []
    while True:
        params = {"offset": offset, "limit": limit, "leasestatuses": list(lease_statuses)}
        r = requests.get(LEASES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            print("Error fetching leases.")
            break

        batch = r.json()
        if not batch:
            break
        all_leases.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return all_leases


def fetch_outstanding_balances(lease_statuses=("Active",)):
    offset = 0
    limit = 100
    all_balances = []
    while True:
        params = {"offset": offset, "limit": limit, "leasestatuses": list(lease_statuses)}
        r = requests.get(OUTSTANDING_BALANCES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            print("Error fetching outstanding balances.")
            break

        data_batch = r.json()
        if not data_batch:
            break
        all_balances.extend(data_batch)
        if len(data_batch) < limit:
            break
        offset += limit

    return all_balances


def fetch_all_properties():
    offset = 0
    limit = 100
    all_props = []
    while True:
        params = {"offset": offset, "limit": limit}
        r = requests.get(PROPERTIES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            print("Error fetching properties.")
            break

        batch = r.json()
        if not batch:
            break
        all_props.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return all_props


def fetch_all_units():
    offset = 0
    limit = 100
    all_units = []
    while True:
        params = {"offset": offset, "limit": limit}
        r = requests.get(UNITS_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            print("Error fetching units.")
            break

        batch = r.json()
        if not batch:
            break
        all_units.extend(batch)
        if len(batch) < limit:
            break
        offset += limit

    return all_units