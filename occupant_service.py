"""
Merges occupant data from Buildium with AddressLine1 => location
Returns a list of dicts:
[
  {
    "lease_id": <int>,
    "occupant_name": <str>,
    "lease_end_date": <str>,
    "location": "41 42" or "5" or "N/A",
    "balance": <float>,
    "property_name": <str>
  },
  ...
]
"""

from buildium_api import (
    fetch_all_leases,
    fetch_outstanding_balances,
    fetch_all_properties,
    fetch_all_units
)


def get_units_map():
    units = fetch_all_units()
    return {u["Id"]: u for u in units if "Id" in u}

def get_property_map():
    props = fetch_all_properties()
    return {p["Id"]: p.get("Name","Unknown Property") for p in props if "Id" in p}


def get_leases_data():
    leases = fetch_all_leases(["Active"])
    if not leases:
        return []

    balances= fetch_outstanding_balances(["Active"])
    bal_map= {b["LeaseId"]: b.get("TotalBalance", 0.0) for b in balances}

    units_map= get_units_map()
    prop_map= get_property_map()

    data=[]
    for lease in leases:
        lease_id= lease.get("Id")
        occupant= lease.get("UnitNumber","Unknown")
        end_date= lease.get("LeaseToDate","N/A")
        prop_id= lease.get("PropertyId")
        prop_name= prop_map.get(prop_id,"Unknown Property")
        bal= bal_map.get(lease_id, 0.0)

        potential_unit_id= lease.get("RentalUnitId")
        unit_info= None
        if potential_unit_id and potential_unit_id in units_map:
            unit_info= units_map[potential_unit_id]
        else:
            # fallback match occupant
            for u in units_map.values():
                if u.get("UnitNumber")== occupant:
                    unit_info= u
                    break

        if unit_info:
            addr= unit_info.get("Address",{})
            loc= addr.get("AddressLine1","")
            if not loc:
                loc="N/A"
        else:
            loc="N/A"

        data.append({
            "lease_id": lease_id,
            "occupant_name": occupant,
            "lease_end_date": end_date,
            "location": loc,
            "balance": bal,
            "property_name": prop_name
        })

    return data