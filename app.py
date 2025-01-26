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

def parse_prefixes_in_location(loc_str):
    """
    Given the occupant's location string (e.g. 'S25 SX100 P32'),
    return a set of detected prefixes: {'S','SX','P'} etc.
    """
    if not loc_str or loc_str.strip().upper() == "N/A":
        return set()

    results = set()
    tokens = loc_str.strip().split()
    for t in tokens:
        up = t.upper()
        if up.startswith("SX"):
            results.add("SX")
        elif up.startswith("PX"):
            results.add("PX")
        elif up.startswith("KX"):
            results.add("KX")
        elif up.startswith("OFX"):
            results.add("OFX")
        elif up.startswith("S"):
            results.add("S")
        elif up.startswith("P"):
            results.add("P")
        elif up.startswith("K"):
            results.add("K")
        elif up.startswith("OF"):
            results.add("OF")
        # else no prefix recognized => ignore
    return results

def occupantColor(occupant_list):
    """
    Decide booth color by checking occupant prefixes (SX/PX/KX/OFX or S/P/K/OF).
    If none found, revert to old logic:
      - If occupant name has 'company storage' => blue
      - Else if total balance > 0 => red
      - Else => green
    """

    # Gather all prefixes & total balance
    all_prefixes = set()
    total_bal = 0.0
    has_company_storage = False

    for occ in occupant_list:
        loc = occ.get("location","")
        pfx_set = parse_prefixes_in_location(loc)
        all_prefixes |= pfx_set  # union
        total_bal += occ.get("balance", 0.0)

        # Check occupant name for "company storage"
        if "company storage" in occ["occupant_name"].lower():
            has_company_storage = True

    # 1) Extended prefixes first
    if "SX" in all_prefixes:
        return "brown"    # e.g. SX => Storage Extended
    if "PX" in all_prefixes:
        return "cyan"     # PX => Pantry Extended
    if "KX" in all_prefixes:
        return "lime"     # KX => Kitchen Extended
    if "OFX" in all_prefixes:
        return "gold"     # OFX => Office Extended

    # 2) Then simpler ones
    if "S" in all_prefixes:
        return "purple"   # S => Storage
    if "P" in all_prefixes:
        return "blue"     # P => Pantry
    if "K" in all_prefixes:
        return "orange"   # K => Kitchen
    if "OF" in all_prefixes:
        return "pink"     # OF => Office

    # 3) No prefixes => fallback to your original logic
    if has_company_storage:
        return "blue"
    elif total_bal > 0:
        return "red"
    else:
        return "green"


@app.route("/")
def index():
    # 1) occupant data, filter for "Visitors Flea Market"
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
        planeH = map_data.get("planeHeight",1000)
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
                # Store occupant data, including the full loc_str for prefix parsing
                occupant_map.setdefault(b_label, []).append({
                    "occupant_name": occupant,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str  # <--- store entire location string
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
            # Now pick the color using new prefix logic
            booth_color = occupantColor(occupant_list)
            b["color"] = booth_color

    # 4) Final HTML w/ just a short scaling step in JS
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <!-- IMPORTANT for mobile responsiveness -->
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
    max-width: 100%;
    position: relative;
    /* We'll set planeWidth × planeHeight inline, as you do below */
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
      <span>Company Storage or P-Pantry</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:gray;"></div>
      <span>Vacant</span>
    </div>
  </div>

  (% if booths|length > 0 %)
    <!-- Same inline style for pixel size -->
    <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
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

      // NEW: If the container is wider than the phone screen, scale to fit
      // We'll compare planeWidth to container's parent width (or screen width).
      let containerParent = ctn.parentNode; // or document.body
      let actualWidth = containerParent.clientWidth;
      // If phone is narrower than planeWidth => scale it
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