#!/usr/bin/env python3

import os
import json
import requests
from flask import Flask, render_template_string

############################################################################
# 1) Custom Jinja delimiters
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
# 2) Buildium fetch logic
############################################################################
BUILDIUM_CLIENT_ID = ""
BUILDIUM_CLIENT_SECRET = ""

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
    limit  = 100
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
        r=requests.get(OUTSTANDING_BALANCES_URL, headers=headers, params=params)
        try:
            r.raise_for_status()
        except:
            break
        batch=r.json()
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
        r=requests.get(UNITS_URL, headers=headers, params=params)
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
        r=requests.get(PROPERTIES_URL, headers=headers, params=params)
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
    return {p["Id"]: p.get("Name","Unknown Property") for p in props if "Id" in p}

############################################################################
# 3) Merging occupant => location from AddressLine1
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
        occupant= lease.get("UnitNumber","Unknown")
        end_date= lease.get("LeaseToDate","N/A")
        property_id= lease.get("PropertyId")
        property_name= prop_map.get(property_id,"Unknown Property")
        bal= bal_map.get(lease_id,0.0)

        potential_unit_id= lease.get("RentalUnitId")
        unit_info=None
        if potential_unit_id and potential_unit_id in units_map:
            unit_info=units_map[potential_unit_id]
        else:
            for u in units_map.values():
                if u.get("UnitNumber")== occupant:
                    unit_info=u
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
            "location": loc,  # multiple => "41 42"
            "balance": bal,
            "property_name": property_name
        })
    return data

############################################################################
# 4) MAIN ROUTE: Show only a map, occupant data in popups, mobile-friendly
############################################################################
@app.route("/")
def index():
    # 1) fetch occupant data & filter
    all_data= get_leases_data()
    filtered= [r for r in all_data if r["property_name"]=="Visitors Flea Market"]

    print("\n=== VISITORS FLEA MARKET occupant data (map only, mobile-centered) ===")
    for row in filtered:
        print(row)

    # 2) load map_layout.json
    try:
        with open("map_layout.json","r") as f:
            map_data= json.load(f)
    except:
        map_data=None

    planeW=600
    planeH=1000
    booths=[]
    if map_data:
        planeW= map_data.get("planeWidth",600)
        planeH= map_data.get("planeHeight",1000)
        booths= map_data.get("booths",[])

    # occupant_map => { booth_label: [ occupantData, ... ] }
    occupant_map={}
    for row in filtered:
        occupant= row["occupant_name"]
        loc_str= row["location"].strip()
        bal= row["balance"]
        lease_id= row["lease_id"]
        end_date= row["lease_end_date"]

        if loc_str!="N/A" and loc_str!="":
            booth_list= loc_str.split()
            for b_label in booth_list:
                occupant_map.setdefault(b_label,[]).append({
                    "occupant_name": occupant,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal
                })

    # Merge occupant => booth
    for b in booths:
        label= b.get("label","").strip()
        occupant_list= occupant_map.get(label,[])
        if occupant_list:
            b["color"]="lightblue"
            b["occupants"]= occupant_list
        else:
            b["color"]="gray"
            b["occupants"]=[]

    #####################################################################
    # Mobile-friendly, centered map: 
    #   - meta name="viewport"
    #   - #mapContainer { margin:0 auto; max-width:100%; etc. }
    #   - we keep planeWidth x planeHeight from the JSON 
    #   - user might still scroll if planeWidth> phone width, 
    #     but at least it's centered, doesn't overflow horizontally, 
    #     and is as "friendly" as possible with minimal code changes.
    #####################################################################
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VFM - Map Only, Mobile & Centered</title>
  <style>
  body {
    font-family: sans-serif;
    margin: 20px;
  }
  #mapContainer {
    display: block;
    margin: 0 auto;              /* center on wide screens */
    border: 2px solid #333;
    background: #fff;
    max-width: 100%;            /* shrink if screen is narrower than planeWidth */
    position: relative;
    /* If you want a fixed ratio approach, you'd do more CSS here, 
       but let's keep it straightforward. */
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
  <h1>Visitors Flea Market - Map Only (Mobile-friendly, centered)</h1>
  (% if booths|length > 0 %)
    <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
    <script>
    function initMap() {
      let planeWidth = __PW__;
      let planeHeight= __PH__;
      const ctn = document.getElementById("mapContainer");
      ctn.style.width  = planeWidth + "px";
      ctn.style.height = planeHeight+"px";

      const data= __BOOTH_JSON__;
      data.forEach(b => {
        const div = document.createElement("div");
        div.className= "booth";
        div.style.left= b.x+"px";
        div.style.top = b.y+"px";
        div.style.width= b.width+"px";
        div.style.height=b.height+"px";

        div.style.backgroundColor= b.color||"gray";
        div.textContent= b.label;

        let occList= b.occupants||[];
        if(occList.length>0) {
          let info= occList.map(o=>{
            return (
              "LeaseID: " + o.lease_id + "\\n"+
              "Occupant: " + o.occupant_name + "\\n"+
              "End: " + o.lease_end + "\\n"+
              "Balance: $"+ o.balance.toFixed(2)
            );
          }).join("\\n----\\n");
          div.onclick= ()=>{
            alert("Booth "+ b.label + "\\n" + info);
          }
        } else {
          div.onclick= ()=>{
            alert("Booth "+ b.label + "\\nVacant");
          }
        }

        ctn.appendChild(div);
      });
    }
    window.onload= initMap;
    </script>
  (% else %)
    <p>No map_layout.json or no booths found.</p>
  (% endif %)
</body>
</html>
    """

    from json import dumps
    booth_json_str= dumps(booths)

    rendered= render_template_string(html_template, booths=booths)
    rendered= rendered.replace("__PW__", str(planeW))
    rendered= rendered.replace("__PH__", str(planeH))
    rendered= rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__=="__main__":
    app.run(debug=True, port=5001)