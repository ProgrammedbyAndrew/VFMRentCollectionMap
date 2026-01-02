#!/usr/bin/env python3

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
        return ("K", up)  # e.g. 'K3'
    if up.startswith("OF"):
        return ("OF", up) # e.g. 'OF2'
    return ("", up)

def occupantColor(occupant_list):
    """
    Slightly darker pastel color logic:
      1) If total_bal > 0 => Past Due => #ff8a8a
      2) If occupant_name has 'company storage' => #bca4ff
      3) Else prefix-based:
         S => #a7aae6        (Storage)
         P => #84c7ff        (Pantry)
         K => #72f0d5        (Kitchen)
         OF => #ffca7a       (Office)
      4) Else => #8ae89f     (On Time)
    """
    total_bal = sum(o["balance"] for o in occupant_list)
    if total_bal > 0:
        return "#ff8a8a"  # Past due

    has_company_storage = any("company storage" in o["occupant_name"].lower()
                              for o in occupant_list)
    if has_company_storage:
        return "#bca4ff"  # Company Storage => pastel purple

    # Check prefix
    prefix_set = set()
    for occ in occupant_list:
        loc_str = occ.get("location","").strip()
        for t in loc_str.split():
            pfx, _ = parse_token(t)
            if pfx:
                prefix_set.add(pfx)

    # Priority S->P->K->OF
    if "S" in prefix_set:
        return "#a7aae6"
    if "P" in prefix_set:
        return "#84c7ff"
    if "K" in prefix_set:
        return "#72f0d5"
    if "OF" in prefix_set:
        return "#ffca7a"

    # Otherwise => On Time
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

    # occupant_map => { booth_label.upper().strip(): [ occupantData, ... ] }
    occupant_map = {}
    for row in filtered:
        occupant_name = row["occupant_name"]
        loc_str       = (row["location"] or "").strip()
        bal           = row["balance"]
        lease_id      = row["lease_id"]
        end_date      = row["lease_end_date"]

        if loc_str and loc_str != "N/A":
            for t in loc_str.split():
                pfx, booth_lbl = parse_token(t)
                # Force uppercase & strip
                booth_key = booth_lbl.upper().strip()
                occupant_map.setdefault(booth_key, []).append({
                    "occupant_name": occupant_name,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str
                })

    # 3) color-code each booth
    for b in booths:
        original_label = (b.get("label","").strip())
        label_up       = original_label.upper().strip()

        occupant_list  = occupant_map.get(label_up, [])
        if occupant_list:
            b["occupants"] = occupant_list
            b["color"]     = occupantColor(occupant_list)
        else:
            b["occupants"] = []
            b["color"]     = "#bdbdbd"  # vacant pastel gray

    # -------------------
    # ADD: Occupancy & Rent Collection
    # -------------------
    total_spots = len(booths)
    occupied_spots = sum(1 for b in booths if len(b["occupants"]) > 0)
    occupancy_pct = round((occupied_spots / total_spots * 100), 1) if total_spots else 0

    occupant_count = sum(len(b["occupants"]) for b in booths)
    occupant_on_time = sum(len([occ for occ in b["occupants"] if occ["balance"] <= 0]) for b in booths)
    rent_collection_pct = round((occupant_on_time / occupant_count * 100), 1) if occupant_count else 0
    # -------------------

    # 4) Final HTML
    html_template = """
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
      padding-bottom: 90px;
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
      cursor: pointer;
    }
    .color-box {
      width: 20px;
      height: 20px;
      margin-right: 6px;
      border: 2px solid #333;
    }
    #mapWrapper {
      margin: 0 auto;
      overflow: hidden;
    }
    #mapContainer {
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
    /* Updated styling to make Occupancy & Rent Collection appear side by side */
    .legend-info {
      cursor: default;
      display: flex;       /* ensure it is displayed as a flex container */
      flex-direction: row; /* row alignment for side-by-side */
      align-items: center;
      gap: 10px;           /* space between items */
      font-weight: bold;
    }
    /* Style the "World Food Trucks" button in red with white text */
    button {
      background: #dc3545; /* red */
      color: #fff;
      border: none;
      padding: 8px 16px;
      margin: 5px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
    }
    button.rotate-btn {
      background: #007bff; /* blue */
    }
    .map-controls {
      display: flex;
      justify-content: center;
      gap: 10px;
      margin-bottom: 10px;
    }
  </style>
</head>
<body>
  <h1>Visitors Flea Market Rent Collection Map</h1>

  (% if booths|length > 0 %)
    <div class="pageContent">
      <div class="map-controls">
        <a href="https://wftmap-c2a97a915c23.herokuapp.com/">
          <button>World Food Trucks</button>
        </a>
        <button class="rotate-btn" onclick="toggleRotation()">Rotate Map</button>
      </div>
      <div id="mapWrapper">
        <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
      </div>
    </div>

    <div class="legend">
      <div class="legend-item" onclick="alert('Pantry - Space rented by food truck vendors for dry, cold, wet storage. Some have walk in freezers, coolers. Some have offices.')">
        <div class="color-box" style="background:#84c7ff;"></div>
        <span>Pantry</span>
      </div>
      <div class="legend-item" onclick="alert('Office Space - Real built out offices near main management offices')">
        <div class="color-box" style="background:#ffca7a;"></div>
        <span>Office</span>
      </div>
      <div class="legend-item" onclick="alert('Kitchen - Areas used by food operators to prepare or store food.')">
        <div class="color-box" style="background:#72f0d5;"></div>
        <span>Kitchen</span>
      </div>
      <div class="legend-item" onclick="alert('Vacant - This booth is currently unoccupied or empty.')">
        <div class="color-box" style="background:#bdbdbd;"></div>
        <span>Vacant</span>
      </div>
      <div class="legend-item" onclick="alert('Past Due - Occupant owes rent; behind on payments.')">
        <div class="color-box" style="background:#ff8a8a;"></div>
        <span>Past Due</span>
      </div>
      <div class="legend-item" onclick="alert('On Time $0 - Occupant is fully paid up.')">
        <div class="color-box" style="background:#8ae89f;"></div>
        <span>On Time $0</span>
      </div>
      <div class="legend-item" onclick="alert('Company Storage - Space used as company storage to store operation items like stages and other misc equipment')">
        <div class="color-box" style="background:#bca4ff;"></div>
        <span>Company Storage</span>
      </div>
      <!-- ADDED: Occupancy & Rent Collection side by side -->
      <div class="legend-item legend-info">
        <span>Occupancy: (( occupancy_pct ))%</span>
        <span>Rent Collection: (( rent_collection_pct ))%</span>
      </div>
    </div>

    <script>
    let isRotated = false;
    let planeWidth  = __PW__;
    let planeHeight = __PH__;

    function initMap() {
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

      applyScaling();
    }

    function applyScaling() {
      const ctn = document.getElementById("mapContainer");
      const wrapper = document.getElementById("mapWrapper");
      const pageContent = document.querySelector(".pageContent");
      const availableWidth = pageContent.clientWidth;

      if (isRotated) {
        // When rotated 90deg, original height becomes width
        // Scale to fill screen width
        const scale = availableWidth / planeHeight;

        // Final visible size after rotation
        const visibleWidth = availableWidth;
        const visibleHeight = planeWidth * scale;

        wrapper.style.width = visibleWidth + "px";
        wrapper.style.height = visibleHeight + "px";
        wrapper.style.position = "relative";

        // Position container at center of wrapper, rotate around its center
        ctn.style.position = "absolute";
        ctn.style.left = "50%";
        ctn.style.top = "50%";
        ctn.style.transformOrigin = "center center";
        ctn.style.transform = "translate(-50%, -50%) rotate(90deg) scale(" + scale + ")";
      } else {
        // Portrait mode - scale to fit width
        const scale = Math.min(1, availableWidth / planeWidth);

        wrapper.style.width = (planeWidth * scale) + "px";
        wrapper.style.height = (planeHeight * scale) + "px";
        wrapper.style.position = "relative";

        ctn.style.position = "relative";
        ctn.style.left = "0";
        ctn.style.top = "0";
        ctn.style.transformOrigin = "top left";
        ctn.style.transform = "scale(" + scale + ")";
      }
    }

    function toggleRotation() {
      isRotated = !isRotated;
      applyScaling();
    }

    window.onload = initMap;
    window.onresize = applyScaling;
    </script>
  (% else %)
    <p style="margin:20px;">No map_layout.json or no booths found.</p>
  (% endif %)
</body>
</html>
    """

    from json import dumps
    booth_json_str = dumps(booths)

    # Pass new occupancy & rent collection values into the template
    rendered = render_template_string(
        html_template,
        booths=booths,
        occupancy_pct=occupancy_pct,
        rent_collection_pct=rent_collection_pct
    )
    rendered = rendered.replace("__PW__", str(planeW))
    rendered = rendered.replace("__PH__", str(planeH))
    rendered = rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__ == "__main__":
    app.run(debug=True, port=5001)