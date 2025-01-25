#!/usr/bin/env python3

import os
import json
import requests
from flask import Flask, render_template_string

############################################################################
# A) CUSTOM JINJA DELIMITERS
############################################################################
app = Flask(__name__)
app.jinja_options = {
    'block_start_string': '(%',
    'block_end_string': '%)',
    'variable_start_string': '((',
    'variable_end_string': '))',
    'comment_start_string': '(#',
    'comment_end_string': '#)'
}

############################################################################
# B) BUILDUM FETCH CODE (unchanged)
############################################################################

BUILDIUM_CLIENT_ID = "77131864-17a2-4460-a12b-0bcbe22051bf"
BUILDIUM_CLIENT_SECRET = "pt0yNFdfIjPDyT9ftL2F3gh2fAmFlDVtsElPJhe5QuI="

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
    offset=0
    limit=100
    all_leases=[]
    while True:
        params={"offset":offset,"limit":limit,"leasestatuses":list(lease_statuses)}
        r= requests.get(LEASES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            break
        batch= r.json()
        if not batch:
            break
        all_leases.extend(batch)
        if len(batch)<limit:
            break
        offset+=limit
    return all_leases

def fetch_outstanding_balances(lease_statuses=("Active",)):
    offset=0
    limit=100
    all_balances=[]
    while True:
        params={"offset":offset,"limit":limit,"leasestatuses":list(lease_statuses)}
        r= requests.get(OUTSTANDING_BALANCES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            break
        batch= r.json()
        if not batch:
            break
        all_balances.extend(batch)
        if len(batch)<limit:
            break
        offset+=limit
    return all_balances

def fetch_all_units():
    offset=0
    limit=100
    all_units=[]
    while True:
        params={"offset":offset,"limit":limit}
        r= requests.get(UNITS_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            break
        batch=r.json()
        if not batch:
            break
        all_units.extend(batch)
        if len(batch)<limit:
            break
        offset+=limit
    return all_units

def fetch_all_properties():
    offset=0
    limit=100
    all_props=[]
    while True:
        params={"offset":offset,"limit":limit}
        r= requests.get(PROPERTIES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            break
        batch=r.json()
        if not batch:
            break
        all_props.extend(batch)
        if len(batch)<limit:
            break
        offset+=limit
    return all_props

def get_units_map():
    units= fetch_all_units()
    return {u["Id"]:u for u in units if "Id" in u}

def get_property_map():
    props= fetch_all_properties()
    return { p["Id"]: p.get("Name","Unknown Property") for p in props if "Id" in p }

############################################################################
# C) MERGE occupant => location
############################################################################
def get_leases_data():
    leases= fetch_all_leases(["Active"])
    if not leases:
        return []

    balances= fetch_outstanding_balances(["Active"])
    bal_map= {b["LeaseId"]: b.get("TotalBalance",0.0) for b in balances}

    units_map= get_units_map()
    prop_map= get_property_map()

    data=[]
    for lease in leases:
        lease_id= lease.get("Id")
        occupant_name= lease.get("UnitNumber","Unknown")
        end_date= lease.get("LeaseToDate","N/A")
        property_id= lease.get("PropertyId")
        property_name= prop_map.get(property_id,"Unknown Property")
        bal= bal_map.get(lease_id,0.0)

        potential_unit_id= lease.get("RentalUnitId")
        unit_info=None
        if potential_unit_id and potential_unit_id in units_map:
            unit_info= units_map[potential_unit_id]
        else:
            for u in units_map.values():
                if u.get("UnitNumber")== occupant_name:
                    unit_info=u
                    break

        if unit_info:
            addr= unit_info.get("Address",{})
            location= addr.get("AddressLine1","")
            if not location:
                location="N/A"
        else:
            location="N/A"

        data.append({
            "lease_id": lease_id,
            "unit_number": occupant_name,
            "lease_end_date": end_date,
            "location": location,   # multiple? "41 42"
            "balance": bal,
            "property_name": property_name
        })
    return data

############################################################################
# D) MAIN ROUTE: Filter "Visitors Flea Market", handle multi-booths, map
############################################################################
@app.route("/")
def index():
    all_data= get_leases_data()
    # filter
    data_rows=[r for r in all_data if r["property_name"]=="Visitors Flea Market"]

    print("\n=== VISITORS FLEA MARKET ONLY ===")
    for row in data_rows:
        print(row)

    try:
        with open("map_layout.json","r") as f:
            map_data=json.load(f)
    except:
        map_data=None

    planeW=600
    planeH=1000
    booths=[]
    if map_data:
        planeW= map_data.get("planeWidth",600)
        planeH= map_data.get("planeHeight",1000)
        booths= map_data.get("booths",[])

    occupant_map={}
    for row in data_rows:
        occupant= row["unit_number"]
        loc_str= row["location"].strip()
        bal= row["balance"]
        lease_id= row["lease_id"]
        end_date= row["lease_end_date"]

        if loc_str!="N/A" and loc_str!="":
            booth_list= loc_str.split()
            for b_label in booth_list:
                occupant_map.setdefault(b_label,[]).append({
                    "occupant_name": occupant,
                    "balance": bal,
                    "lease_id": lease_id,
                    "lease_end": end_date
                })

    for b in booths:
        label= b.get("label","").strip()
        occupant_list= occupant_map.get(label,[])
        if occupant_list:
            b["color"]="lightblue"
            b["occupants"]= occupant_list
        else:
            b["color"]="gray"
            b["occupants"]=[]

    # Because we have custom delimiters:
    #  - block:  (% ... %)
    #  - var:    (( ... ))
    # We'll code the template accordingly.
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>VFM - changed delimiters (no raw block needed)</title>
  <style>
  body {
    font-family: sans-serif;
    margin: 20px;
  }
  .flex-container {
    display: flex;
    gap: 20px;
  }
  .half {
    flex: 1;
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th, td {
    padding: 8px 12px;
    border-bottom: 1px solid #ccc;
  }
  th {
    background: #f0f0f0;
    text-align: left;
  }
  #mapContainer {
    position: relative;
    border: 2px solid #333;
    background: #fff;
  }
  .booth {
    position: absolute;
    box-sizing: border-box;
    border: 2px solid #111;
    display: flex;
    justify-content: center;
    align-items: center;
    font-weight: bold;
    font-size: 12px;
    color: #000;
    cursor: pointer;
  }
  </style>
</head>
<body>
  <h1>Visitors Flea Market - multi booths, custom delimiters</h1>
  <div class="flex-container">
    <div class="half">
      <h2>Lease Data</h2>
      <table>
        <thead>
          <tr>
            <th>Lease ID</th>
            <th>Occupant</th>
            <th>End</th>
            <th>Location</th>
            <th>Balance</th>
          </tr>
        </thead>
        <tbody>
        (% for r in data_rows %)
          <tr>
            <td>(( r.lease_id ))</td>
            <td>(( r.unit_number ))</td>
            <td>(( r.lease_end_date ))</td>
            <td>(( r.location ))</td>
            <td>$(( "%.2f"|format(r.balance) ))</td>
          </tr>
        (% endfor %)
        </tbody>
      </table>
    </div>

    <div class="half">
      <h2>Map Layout</h2>
      (% if booths|length > 0 %)
        <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
        <script>
        function initMap() {
          const planeWidth = __PW__;
          const planeHeight= __PH__;
          const ctn = document.getElementById("mapContainer");
          ctn.style.width  = planeWidth + "px";
          ctn.style.height = planeHeight+ "px";

          const data = __BOOTH_JSON__;
          data.forEach(b => {
            let d = document.createElement("div");
            d.className="booth";
            d.style.left= b.x+"px";
            d.style.top = b.y+"px";
            d.style.width= b.width+"px";
            d.style.height=b.height+"px";
            d.style.backgroundColor= b.color||"gray";
            d.textContent= b.label;

            if(b.occupants && b.occupants.length>0) {
              let info= b.occupants.map(o=>{
                return (
                  "LeaseID: "+o.lease_id+"\\n"+
                  "Occupant: "+o.occupant_name+"\\n"+
                  "End: "+o.lease_end+"\\n"+
                  "Balance: $"+o.balance.toFixed(2)
                );
              }).join("\\n----\\n");
              d.onclick= ()=>{
                alert("Booth "+b.label+"\\n"+info);
              }
            } else {
              d.onclick= ()=>{
                alert("Booth "+b.label+"\\nVacant");
              }
            }

            ctn.appendChild(d);
          });
        }
        window.onload= initMap;
        </script>
      (% else %)
        <p>No map_layout.json or no booths found.</p>
      (% endif %)
    </div>
  </div>
</body>
</html>
    """

    from json import dumps
    booth_json_str= dumps(booths)

    rendered= render_template_string(html_template, data_rows=data_rows, booths=booths)
    # next, replace placeholders
    rendered= rendered.replace("__PW__", str(planeW))
    rendered= rendered.replace("__PH__", str(planeH))
    rendered= rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__=="__main__":
    app.run(debug=True, port=5001)