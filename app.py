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
    If token starts with 'S' or 'P', we strip that letter for booth label (e.g. 'S24' -> label '24').
    If token starts with 'K' or 'OF', we keep the entire token as the booth label (e.g. 'K1' -> 'K1').
    Otherwise, no prefix => use the raw token as booth label.
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
    1) If any occupant behind on rent => RED
    2) Else check prefixes (S->purple, P->blue, K->orange, OF->pink)
    3) Else => green
    """
    total_bal = sum(o["balance"] for o in occupant_list)
    # 1) rent due => red
    if total_bal > 0:
        return "red"

    # 2) gather prefix from occupant tokens
    prefix_set = set()
    for occ in occupant_list:
        loc_str = occ.get("location","").strip()
        tokens = loc_str.split()
        for t in tokens:
            pfx, _ = parse_token(t)
            if pfx:
                prefix_set.add(pfx)

    if "S"  in prefix_set:
        return "purple"
    if "P"  in prefix_set:
        return "blue"
    if "K"  in prefix_set:
        return "orange"
    if "OF" in prefix_set:
        return "pink"

    # 3) no prefix => green
    return "green"


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

        if loc_str and loc_str != "N/A":
            tokens = loc_str.split()
            for t in tokens:
                pfx, booth_lbl = parse_token(t)
                occupant_map.setdefault(booth_lbl, []).append({
                    "occupant_name": occupant,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str
                })

    # 3) color-code the booths
    for b in booths:
        label = b.get("label","").strip()
        occupant_list = occupant_map.get(label, [])
        if not occupant_list:
            b["color"] = "gray"
            b["occupants"] = []
        else:
            b["occupants"] = occupant_list
            b["color"] = occupantColor(occupant_list)

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
      margin: 0; /* We'll handle spacing differently below */
      padding: 0;
    }
    h1 {
      text-align: center;
      margin: 20px 0 10px; /* top and bottom spacing for the title */
    }

    /* .pageContent includes the map container, 
       with extra bottom padding so it won't be hidden behind the fixed legend */
    .pageContent {
      padding-bottom: 90px; /* space for the bottom legend bar */
      margin: 0 20px;       /* some side margin if you want */
    }

    /* The pinned legend at the bottom as a bar */
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
      justify-content: center; /* center items horizontally */
      flex-wrap: wrap;         /* wrap items if needed on small phones */
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

    /* The map container - no border, just the plane area */
    #mapContainer {
      display: block;
      margin: 0 auto;
      background: #fff;
      max-width: 100%;
      position: relative;
    }
    .booth {
      position: absolute;
      box-sizing: border-box;
      border: 2px solid #111; /* put back booth borders */
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
      <!-- The legend items as a bottom bar -->
      <div class="legend-item">
        <div class="color-box" style="background:red;"></div>
        <span>Behind on Rent</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:gray;"></div>
        <span>Vacant</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:purple;"></div>
        <span>S + number</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:blue;"></div>
        <span>P + number</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:orange;"></div>
        <span>K1, K2, etc.</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:pink;"></div>
        <span>OF1, OF2, etc.</span>
      </div>
      <div class="legend-item">
        <div class="color-box" style="background:green;"></div>
        <span>No prefix + No rent due</span>
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

      // phone narrower => scale
      let containerParent = ctn.parentNode; // .pageContent
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

    # same text replacements
    rendered = render_template_string(html_template, booths=booths)
    rendered = rendered.replace("__PW__", str(planeW))
    rendered = rendered.replace("__PH__", str(planeH))
    rendered = rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__ == "__main__":
    app.run(debug=True, port=5001)