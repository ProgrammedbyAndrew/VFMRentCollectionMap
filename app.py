#!/usr/bin/env python3

import os
import json
from flask import Flask, render_template_string
from occupant_service import get_leases_data

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
# 2) MAIN ROUTE: show the map only (no occupant list),
#    occupant data in popups, mobile-friendly, centered, same logic as before
############################################################################
@app.route("/")
def index():
    # 1) fetch occupant data & filter
    all_data= get_leases_data()
    filtered= [r for r in all_data if r["property_name"]=="Visitors Flea Market"]

    print("\n=== VISITORS FLEA MARKET occupant data (map only) ===")
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

    # 3) same final HTML template from your single-file code, with placeholders
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VFM - Map Only</title>
  <style>
  body {
    font-family: sans-serif;
    margin: 20px;
  }
  #mapContainer {
    display: block;
    margin: 0 auto;              /* center horizontally */
    border: 2px solid #333;
    background: #fff;
    max-width: 100%;
    position: relative;
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
        const div= document.createElement("div");
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

    # 4) use Jinja + string replacement same as your single-file approach
    rendered= render_template_string(html_template, booths=booths)
    rendered= rendered.replace("__PW__", str(planeW))
    rendered= rendered.replace("__PH__", str(planeH))
    rendered= rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__=="__main__":
    app.run(debug=True, port=5001)