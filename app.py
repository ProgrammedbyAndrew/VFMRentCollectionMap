#!/usr/bin/env python3

import os
import json
from flask import Flask, render_template_string
from occupant_service import get_leases_data

app = Flask(__name__)

# Keep your custom Jinja delimiters (unchanged)
app.jinja_options = {
    'block_start_string': '(%',
    'block_end_string': '%)',
    'variable_start_string': '((',
    'variable_end_string': '))',
    'comment_start_string': '(#',
    'comment_end_string': '#)'
}

@app.route("/")
def index():
    # 1) occupant data, filter for "Visitors Flea Market"
    all_data = get_leases_data()
    filtered = [r for r in all_data if r["property_name"]=="Visitors Flea Market"]
    print("\n=== VFM occupant data (map only) ===")
    for row in filtered:
        print(row)

    # 2) load map_layout.json
    try:
        with open("map_layout.json","r") as f:
            map_data = json.load(f)
    except:
        map_data = None

    planeW = 600
    planeH = 1000
    booths = []
    if map_data:
        planeW = map_data.get("planeWidth", 600)
        planeH = map_data.get("planeHeight", 1000)
        booths = map_data.get("booths", [])

    # occupant_map => { booth_label: [ occupantData,... ] }
    occupant_map = {}
    for row in filtered:
        occupant = row["occupant_name"]
        loc_str  = row["location"].strip()
        bal      = row["balance"]
        lease_id = row["lease_id"]
        end_date = row["lease_end_date"]

        if loc_str != "N/A" and loc_str != "":
            booth_list = loc_str.split()
            for b_label in booth_list:
                occupant_map.setdefault(b_label, []).append({
                    "occupant_name": occupant,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal
                })

    # 3) Color code the booths & assign occupant array
    for b in booths:
        label = b.get("label","").strip()
        occupant_list = occupant_map.get(label, [])
        if not occupant_list:
            # vacant => gray
            b["color"] = "gray"
            b["occupants"] = []
        else:
            b["occupants"] = occupant_list
            total_bal = sum(o["balance"] for o in occupant_list)

            # check occupant name for "company storage"
            has_company_storage = any("company storage" in o["occupant_name"].lower()
                                      for o in occupant_list)
            if has_company_storage:
                b["color"] = "blue"
            else:
                if total_bal > 0:
                    b["color"] = "red"
                else:
                    b["color"] = "green"

    # 4) Final HTML w/ minimal extra for mobile scaling
    html_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <!-- Added for mobile responsiveness: -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  
  <title>VFM - Map Only w/ .env API keys</title>
  <style>
  body {
    font-family: sans-serif;
    margin: 20px;
  }
  .legend {
    margin-bottom: 1rem;
  }
  .legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
  }
  .color-box {
    width: 20px;
    height: 20px;
    border: 2px solid #333;
    margin-right: 8px;
  }

  #mapContainer {
    display: block;
    margin: 0 auto;
    border: 2px solid #333;
    background: #fff;
    max-width: 100%; /* keep container from exceeding screen width */
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
  <h1>Visitors Flea Market - Map Only (.env for API keys)</h1>

  <!-- Legend -->
  <div class="legend">
    <div class="legend-item">
      <div class="color-box" style="background:green;"></div>
      <span>No Amount Due</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:red;"></div>
      <span>Past Due</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:blue;"></div>
      <span>Company Storage</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:gray;"></div>
      <span>Vacant</span>
    </div>
  </div>

  (% if booths|length > 0 %)
    <!-- Same inline style for the map's absolute pixel size: -->
    <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
    
    <script>
    function initMap() {
      let planeWidth  = __PW__;
      let planeHeight = __PH__;
      const ctn = document.getElementById("mapContainer");

      // same occupant code
      ctn.style.width  = planeWidth + "px";
      ctn.style.height = planeHeight + "px";

      const data = __BOOTH_JSON__;
      data.forEach(b => {
        const div = document.createElement("div");
        div.className = "booth";
        div.style.left   = b.x + "px";
        div.style.top    = b.y + "px";
        div.style.width  = b.width + "px";
        div.style.height = b.height + "px";

        div.style.backgroundColor = b.color || "gray";
        div.textContent = b.label;

        let occList = b.occupants || [];
        if (occList.length > 0) {
          let info = occList.map(o => {
            return (
              "LeaseID: " + o.lease_id + "\\n" +
              "Occupant: " + o.occupant_name + "\\n" +
              "End: " + o.lease_end + "\\n" +
              "Balance: $" + o.balance.toFixed(2)
            );
          }).join("\\n----\\n");
          div.onclick = () => {
            alert("Booth " + b.label + "\\n" + info);
          }
        } else {
          div.onclick = () => {
            alert("Booth " + b.label + "\\nVacant");
          }
        }

        ctn.appendChild(div);
      });
      
      // NEW: If screen is narrower than planeWidth, scale the container
      let actualWidth = ctn.clientWidth; // or parentNode.clientWidth
      if (planeWidth > 0 && actualWidth < planeWidth) {
        let scale = actualWidth / planeWidth;
        ctn.style.transformOrigin = "top left";
        ctn.style.transform       = "scale(" + scale + ")";
      }
    }
    window.onload = initMap;
    </script>
  (% else %)
    <p>No map_layout.json or no booths found.</p>
  (% endif %)
</body>
</html>
    """

    from json import dumps
    booth_json_str = dumps(booths)

    # same text replacements
    rendered = render_template_string(html_template, booths=booths)
    rendered = rendered.replace("__PW__", str(planeW))
    rendered = rendered.replace("__PH__", str(planeH))
    rendered = rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered


if __name__=="__main__":
    app.run(debug=True, port=5001)