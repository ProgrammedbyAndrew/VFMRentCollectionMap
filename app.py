#!/usr/bin/env python3

import os
import json
from flask import Flask, render_template_string
from occupant_service import get_leases_data

app = Flask(__name__)

# Keep your custom Jinja delimiters
app.jinja_options = {
    'block_start_string': '(%',
    'block_end_string': '%)',
    'variable_start_string': '((',
    'variable_end_string': '))',
    'comment_start_string': '(#',
    'comment_end_string': '#)'
}

def parse_token(token):
    """
    If token starts with 'S' or 'P', strip that letter => numeric booth label.
      e.g. 'S24' => prefix 'S', booth '24'
           'P10' => prefix 'P', booth '10'
    If token starts with 'K' or 'OF', keep entire token => lettered booth
      e.g. 'K1' => prefix 'K', booth 'K1'
           'OF2' => prefix 'OF', booth 'OF2'
    Otherwise => no prefix => raw token as booth label.
    """
    up = token.upper().strip()
    if up.startswith("S"):
        return ("S", up[1:])
    if up.startswith("P"):
        return ("P", up[1:])
    if up.startswith("K"):
        return ("K", up)
    if up.startswith("OF"):
        return ("OF", up)
    return ("", up)

def occupantColor(occupant_list):
    """
    Slightly darker pastel color logic:

      1) If total_bal > 0 => Past Due => #ff8a8a
      2) If occupant_name has 'company storage' => #bca4ff
      3) Else prefix-based:
         S => #a7aae6
         P => #84c7ff
         K => #ffb884  (changed here to be more distinct from red)
         OF => #ffca7a
      4) Else => #8ae89f (On Time)
    """
    total_bal = sum(o["balance"] for o in occupant_list)
    if total_bal > 0:
        # Past due
        return "#ff8a8a"

    # Check occupant name for "company storage"
    has_company_storage = any("company storage" in o["occupant_name"].lower()
                              for o in occupant_list)
    if has_company_storage:
        # Slightly darker pastel purple for company storage
        return "#bca4ff"

    # Else check prefix
    prefix_set = set()
    for occ in occupant_list:
        loc_str = occ.get("location","").strip()
        for t in loc_str.split():
            pfx, _ = parse_token(t)
            if pfx:
                prefix_set.add(pfx)

    # Priority S->P->K->OF
    if "S" in prefix_set:
        return "#a7aae6"  # Storage
    if "P" in prefix_set:
        return "#84c7ff"  # Pantry
    if "K" in prefix_set:
        return "#ffb884"  # Kitchen (new pastel orange)
    if "OF" in prefix_set:
        return "#ffca7a"  # Office

    # Otherwise => On Time => #8ae89f
    return "#8ae89f"


@app.route("/")
def index():
    # 1) occupant data
    all_data = get_leases_data()
    filtered = [r for r in all_data if r["property_name"] == "Visitors Flea Market"]
    print("\n=== VFM occupant data (map only) ===")
    for row in filtered:
        print(row)

    # 2) load map_layout.json
    try:
        with open("map_layout.json", "r") as f:
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

    # occupant_map => { booth_label.upper(): [ occupantData, ... ] }
    occupant_map = {}
    for row in filtered:
        occupant_name = row["occupant_name"]
        loc_str       = row["location"].strip()
        bal           = row["balance"]
        lease_id      = row["lease_id"]
        end_date      = row["lease_end_date"]

        if loc_str and loc_str != "N/A":
            for t in loc_str.split():
                pfx, booth_lbl = parse_token(t)
                occupant_map.setdefault(booth_lbl.upper(), []).append({
                    "occupant_name": occupant_name,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str
                })

    # 3) color-code each booth
    for b in booths:
        original_label = b.get("label","").strip()
        label_up       = original_label.upper()
        occupant_list  = occupant_map.get(label_up, [])
        if occupant_list:
            b["occupants"] = occupant_list
            b["color"]     = occupantColor(occupant_list)
        else:
            b["occupants"] = []
            # Slightly darker pastel gray for vacant
            b["color"]     = "#bdbdbd"

    # 4) Final HTML
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Visitors Flea Market Rent Collection Map</title>
  <style>
    body {
      font-family: sans-serif;
      margin: 0;
      padding: 0;
    }
    h1 {
      text-align: center;
      margin: 20px 0 10px;
    }

    .pageContent {
      padding-bottom: 90px; /* so the bottom legend won't cover the map */
      margin: 0 20px;
    }

    .legend {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      background: #fff;
      border-top: 2px solid #333;
      padding: 8px;
      z-index: 999;
      display: flex;
      justify-content: space-evenly;
      flex-wrap: wrap;
    }
    .legend-item {
      display: flex;
      align-items: center;
      margin: 4px 8px;
    }
    .color-box {
      width: 20px;
      height: 20px;
      margin-right: 6px;
      border: 2px solid #333;
    }

    #mapContainer {
      display: block;
      margin: 0 auto;
      max-width: 100%;
      position: relative;
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
  <h1>Visitors Flea Market Rent Collection Map</h1>

  (% if booths|length > 0 %)
    <div class="pageContent">
      <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
    </div>

    <div class="legend">
      <!-- Slightly darker pastel colors in legend -->
      <div class="legend-item">
        <div class="color-box" style="background:#84c7ff;"></div>
        <span>Pantry</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#ffca7a;"></div>
        <span>Office</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#ffb884;"></div>
        <span>Kitchen</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#bdbdbd;"></div>
        <span>Vacant</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#ff8a8a;"></div>
        <span>Past Due</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#8ae89f;"></div>
        <span>On Time $0</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:#bca4ff;"></div>
        <span>Company Storage</span>
      </div>
    </div>

    <script>
    function initMap() {
      let planeWidth  = __PW__;
      let planeHeight = __PH__;
      const ctn = document.getElementById("mapContainer");

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

        div.textContent = b.label;

        // Slightly darker pastel color (Kitchen => #ffb884, etc.)
        div.style.backgroundColor = b.color || "#bdbdbd"; 

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

      // phone narrower => scale
      let containerParent = ctn.parentNode;
      let actualWidth = containerParent.clientWidth;
      if (planeWidth > 0 && actualWidth < planeWidth) {
        let scale = actualWidth / planeWidth;
        ctn.style.transformOrigin = "top left";
        ctn.style.transform       = "scale(" + scale + ")";
      }
    }
    window.onload = initMap;
    </script>
  (% else %)
    <p style="margin:20px;">No map_layout.json or no booths found.</p>
  (% endif %)
</body>
</html>
    """

    from json import dumps
    booth_json_str = dumps(booths)

    # Insert plane size & booth data
    rendered = render_template_string(html_template, booths=booths)
    rendered = rendered.replace("__PW__", str(planeW))
    rendered = rendered.replace("__PH__", str(planeH))
    rendered = rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__ == "__main__":
    app.run(debug=True, port=5001)