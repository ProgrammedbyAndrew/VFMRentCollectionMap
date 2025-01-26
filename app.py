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
    Given a location token like "S25", "P14", "K1", or "OF2",
    return (prefix, booth_label) such that:
      - "S25" => ( "S",  "25" )
      - "P14" => ( "P",  "14" )
      - "K1"  => ( "K",  "K1" )   # keep the entire token as booth label
      - "OF2" => ( "OF", "OF2" )  # keep entire token
      - "39"  => ( "",   "39" )   # no prefix, numeric booth label
    """
    up = token.upper().strip()
    if up.startswith("S"):
        # "S25" => prefix "S", booth "25"
        return ("S", up[1:])
    if up.startswith("P"):
        # "P12" => prefix "P", booth "12"
        return ("P", up[1:])
    if up.startswith("K"):
        # "K5" => prefix "K", booth "K5"
        return ("K", up)
    if up.startswith("OF"):
        # "OF2" => prefix "OF", booth "OF2"
        return ("OF", up)
    # else no recognized prefix => entire token is the booth label
    return ("", up)


def occupantColor(occupant_list):
    """
    1) If total rent due >0 => red
    2) Else check occupant prefixes:
        - if prefix "S" => purple
        - if prefix "P" => blue
        - if prefix "K" => orange
        - if prefix "OF" => pink
       If multiple occupants have different prefixes, we pick in order S->P->K->OF
    3) If no prefix => green
    """

    # 1) If occupant behind on rent => red
    total_bal = sum(o["balance"] for o in occupant_list)
    if total_bal > 0:
        return "red"

    # 2) gather all prefixes from occupant data
    prefix_set = set()
    for occ in occupant_list:
        loc_str = occ.get("location","").strip()
        if loc_str:
            tokens = loc_str.split()
            for t in tokens:
                pfx, _ = parse_token(t)
                if pfx:
                    prefix_set.add(pfx)

    # In case multiple occupants => pick color by priority
    # e.g. if there's any occupant with prefix "S", we do purple first, else "P" => blue, else "K" => orange, etc.
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

    # occupant_map => { booth_label: [ occupantDict, occupantDict, ... ] }
    occupant_map = {}
    for row in filtered:
        occupant    = row["occupant_name"]
        loc_str     = row["location"].strip()
        bal         = row["balance"]
        lease_id    = row["lease_id"]
        end_date    = row["lease_end_date"]

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
            # vacant => gray
            b["color"] = "gray"
            b["occupants"] = []
        else:
            b["occupants"] = occupant_list
            booth_color = occupantColor(occupant_list)
            b["color"] = booth_color

    # 4) Final HTML (pinned legend)
    html_template= """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>VFM - Mixed S/P (Numeric) & K/OF (Lettered)</title>
  <style>
  body {
    font-family: sans-serif;
    margin: 20px;
  }

  .legend {
    position: fixed;
    top: 20px;
    left: 20px;
    width: 200px;
    background: #fff;
    border: 2px solid #333;
    border-radius: 8px;
    padding: 10px;
    z-index: 999;
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

  <div class="legend">
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
      <span>S + number => e.g. "S24"</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:blue;"></div>
      <span>P + number => e.g. "P14"</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:orange;"></div>
      <span>K + number => e.g. "K1"</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:pink;"></div>
      <span>OF + number => e.g. "OF2"</span>
    </div>
    <div class="legend-item">
      <div class="color-box" style="background:green;"></div>
      <span>No prefix + No rent => Green</span>
    </div>
  </div>

  (% if booths|length > 0 %)
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

      // phone/screen narrower => scale
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