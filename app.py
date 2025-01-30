#!/usr/bin/env python3

import os
import json
from functools import wraps
from flask import (
    Flask, render_template_string, request,
    redirect, url_for, session
)
from occupant_service import get_leases_data

app = Flask(__name__)
# IMPORTANT: Change this to a strong, random value in production
app.secret_key = "c7aebdfef4b2cf300ceafc1231f683b3404a4f59799af4278b7da3deef8ef53a"

USERNAME = "Visitors Plaza"
PASSWORD = "11qq22ww"

#
# -- MODERN, STYLED LOGIN PAGE (Black background, normal Jinja syntax) --
#
login_page_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Sign into Visitors Plaza Rent Collection Map</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto&display=swap');
    body {
      margin: 0;
      padding: 0;
      font-family: 'Roboto', sans-serif;
      background: #000; /* Black background */
      color: #fff;
    }
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh; /* Full viewport height */
      padding: 0 20px;
      box-sizing: border-box;
    }
    .login-box {
      background: #111;
      width: 100%;
      max-width: 380px;
      padding: 30px;
      border-radius: 8px;
      box-shadow: 0 5px 20px rgba(0,0,0,0.3);
      text-align: center;
    }
    .login-box h2 {
      margin-bottom: 20px;
      color: #fff;
    }
    .login-box .form-group {
      text-align: left;
      margin-bottom: 15px;
    }
    .login-box label {
      display: block;
      margin-bottom: 5px;
      font-size: 14px;
      font-weight: 500;
    }
    .login-box input[type="text"],
    .login-box input[type="password"] {
      width: 100%;
      padding: 10px;
      border: 1px solid #444;
      border-radius: 4px;
      font-size: 16px;
      box-sizing: border-box;
      background: #222;
      color: #fff;
    }
    .error-message {
      color: #ff4b4b;
      margin-bottom: 15px;
    }
    .login-box button {
      width: 100%;
      padding: 12px;
      background: #ff4b4b;
      border: none;
      border-radius: 4px;
      color: #fff;
      font-size: 16px;
      cursor: pointer;
      transition: background 0.3s ease;
      font-weight: bold;
    }
    .login-box button:hover {
      background: #dc3545;
    }
  </style>
</head>
<body>
  <div class="login-container">
    <div class="login-box">
      <h2>Sign into Visitors Plaza Rent Collection Map</h2>
      {% if error_message %}
        <div class="error-message">{{ error_message }}</div>
      {% endif %}
      <form method="POST">
        <div class="form-group">
          <label for="username">Username</label>
          <input name="username" id="username" type="text" required autofocus />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input name="password" id="password" type="password" required />
        </div>
        <button type="submit">Log In</button>
      </form>
    </div>
  </div>
</body>
</html>
"""

#
# -- LOGIN ROUTE --
#
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Displays a modern styled login form. On POST, checks credentials;
    if correct, sets session['logged_in'] and redirects to index.
    Otherwise, shows an error message.
    """
    if request.method == "POST":
        form_user = request.form.get("username", "")
        form_pass = request.form.get("password", "")
        if form_user == USERNAME and form_pass == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            # Invalid credentials => show an error
            return render_template_string(
                login_page_html,
                error_message="Invalid credentials. Please try again."
            )
    # For GET => show the blank form
    return render_template_string(login_page_html, error_message=None)

#
# -- PROTECT ROUTES WITH SESSION-BASED AUTH CHECK --
#
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

#
# -- HELPER FUNCTIONS FOR YOUR MAP/BOOTH LOGIC --
#
def parse_token(token):
    """
    If token starts with 'S' or 'P', strip that letter => numeric booth label.
      e.g. 'S24' => prefix 'S', booth '24'
           'P10' => prefix 'P', booth '10'
    If token starts with 'K' or 'OF', keep entire token => lettered booth
      e.g. 'K3' => prefix 'K', booth 'K3'
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
         K => #72f0d5
         OF => #ffca7a
      4) Otherwise => #8ae89f
    """
    total_bal = sum(o["balance"] for o in occupant_list)
    if total_bal > 0:
        return "#ff8a8a"  # Past due

    has_company_storage = any("company storage" in o["occupant_name"].lower()
                              for o in occupant_list)
    if has_company_storage:
        return "#bca4ff"

    # Check prefix
    prefix_set = set()
    for occ in occupant_list:
        loc_str = occ.get("location","").strip()
        for t in loc_str.split():
            pfx, _ = parse_token(t)
            if pfx:
                prefix_set.add(pfx)

    if "S" in prefix_set:
        return "#a7aae6"
    if "P" in prefix_set:
        return "#84c7ff"
    if "K" in prefix_set:
        return "#72f0d5"
    if "OF" in prefix_set:
        return "#ffca7a"
    return "#8ae89f"

#
# -- MAIN MAP PAGE (REQUIRES LOGIN) --
#
@app.route("/")
@login_required
def index():
    # 1) Get occupant data
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
                booth_key = booth_lbl.upper().strip()
                occupant_map.setdefault(booth_key, []).append({
                    "occupant_name": occupant_name,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str
                })

    # 3) color-code each booth & check if past due
    for b in booths:
        original_label = (b.get("label","").strip())
        label_up       = original_label.upper().strip()

        occupant_list  = occupant_map.get(label_up, [])
        if occupant_list:
            b["occupants"] = occupant_list
            b["color"]     = occupantColor(occupant_list)

            # Past Due => use red border, but fill color from occupantColor logic
            total_bal = sum(o["balance"] for o in occupant_list)
            if total_bal > 0:
                has_company_storage = any(
                    "company storage" in o["occupant_name"].lower()
                    for o in occupant_list
                )
                if has_company_storage:
                    b["color"] = "#bca4ff"
                else:
                    prefix_set = set()
                    for occ in occupant_list:
                        loc_str_ = occ.get("location","").strip()
                        for t_ in loc_str_.split():
                            pfx_, _ = parse_token(t_)
                            if pfx_:
                                prefix_set.add(pfx_)
                    if "S" in prefix_set:
                        b["color"] = "#a7aae6"
                    elif "P" in prefix_set:
                        b["color"] = "#84c7ff"
                    elif "K" in prefix_set:
                        b["color"] = "#72f0d5"
                    elif "OF" in prefix_set:
                        b["color"] = "#ffca7a"
                    else:
                        b["color"] = "#8ae89f"
                b["past_due"] = True
        else:
            b["occupants"] = []
            b["color"]     = "#bdbdbd"  # vacant pastel gray

    # 4) Occupancy & rent collection
    total_spots = len(booths)
    occupied_spots = sum(1 for b in booths if len(b["occupants"]) > 0)
    occupancy_pct = round((occupied_spots / total_spots * 100), 1) if total_spots else 0

    occupant_count = sum(len(b["occupants"]) for b in booths)
    occupant_on_time = sum(
        len([occ for occ in b["occupants"] if occ["balance"] <= 0])
        for b in booths
    )
    rent_collection_pct = round(
        (occupant_on_time / occupant_count * 100), 1
    ) if occupant_count else 0

    # 5) Final HTML with bottom legend
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
      background: #fff;
    }
    h1 {
      text-align: center;
      margin: 20px 0 10px;
    }
    .pageContent {
      padding-bottom: 90px; /* space for legend */
      margin: 0 20px;
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

    /* Bottom legend, more modern style */
    .legend {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      background: #f8f9fa; 
      border-top: 1px solid #ddd;
      box-shadow: 0 -2px 6px rgba(0,0,0,0.1);
      padding: 10px;
      z-index: 9999;
      display: flex;
      flex-wrap: wrap;      /* allows wrapping on small screens */
      justify-content: center;
      align-items: center;
      gap: 14px;            /* spacing between items */
    }
    .legend-item {
      display: flex;
      align-items: center;
      font-size: 14px;
      cursor: pointer;
    }
    .color-box {
      width: 24px;
      height: 24px;
      margin-right: 8px;
      border: 2px solid #333;
      border-radius: 4px; /* slight rounding for modern look */
      box-sizing: border-box;
    }

    /* Past Due box: red border, transparent fill (no X) */
    .past-due-box {
      background: transparent; 
      border-color: #dc3545 !important; /* force red border */
    }

    .legend-info {
      font-weight: bold;
      display: flex;
      align-items: center;
      gap: 12px;
      margin-left: 8px;
    }
    .legend-info span {
      white-space: nowrap; /* keep the percentages in a single line */
    }
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

    /* Force a line break in the legend so "Past Due" is on second line */
    .break-line {
      flex-basis: 100%;
      height: 0;
    }
  </style>
</head>
<body>

  <h1>Visitors Flea Market Rent Collection Map</h1>

  <div style="text-align:center; margin-bottom:10px;">
    <a href="https://wftmap-c2a97a915c23.herokuapp.com/">
      <button>World Food Trucks</button>
    </a>
  </div>

  {% if booths|length > 0 %}
    <div class="pageContent">
      <div id="mapContainer" style="width:{{ planeW }}px; height:{{ planeH }}px;"></div>
    </div>
  {% else %}
    <p style="margin:20px;">No map_layout.json or no booths found.</p>
  {% endif %}

  <!-- Modernized legend at bottom -->
  <div class="legend">
    <div class="legend-item" onclick="alert('Pantry: used for storage and sometimes offices.')">
      <div class="color-box" style="background:#84c7ff;"></div>
      <span>Pantry</span>
    </div>
    <div class="legend-item" onclick="alert('Office: built-out offices near management.')">
      <div class="color-box" style="background:#ffca7a;"></div>
      <span>Office</span>
    </div>
    <div class="legend-item" onclick="alert('Kitchen: used by food operators.')">
      <div class="color-box" style="background:#72f0d5;"></div>
      <span>Kitchen</span>
    </div>
    <div class="legend-item" onclick="alert('Vacant: unoccupied booth.')">
      <div class="color-box" style="background:#bdbdbd;"></div>
      <span>Vacant</span>
    </div>

    <!-- Force a break in the flex layout (moves next items to second line) -->
    <div class="break-line"></div>

    <!-- Past Due => no X, just a red border on transparent fill -->
    <div class="legend-item" onclick="alert('Past Due: vendor has red border on map.')">
      <div class="color-box past-due-box"></div>
      <span>Past Due</span>
    </div>
    <!-- FM Vendor instead of "Flea Market Vendor" -->
    <div class="legend-item" onclick="alert('FM Vendor: occupant is fully paid.')">
      <div class="color-box" style="background:#8ae89f;"></div>
      <span>FM Vendor</span>
    </div>
    <div class="legend-item" onclick="alert('Company Storage: used to store equipment.')">
      <div class="color-box" style="background:#bca4ff;"></div>
      <span>Company Storage</span>
    </div>
    <!-- Occupancy & Rent Collection -->
    <div class="legend-item legend-info">
      <span>Occupancy: {{ occupancy_pct }}%</span>
      <span>Rent: {{ rent_collection_pct }}%</span>
    </div>
  </div>

  <script>
    function initMap() {
      let planeWidth  = {{ planeW }};
      let planeHeight = {{ planeH }};
      const ctn = document.getElementById("mapContainer");
      if(!ctn) return; // if there's no mapContainer or no booths

      ctn.style.width  = planeWidth + "px";
      ctn.style.height = planeHeight + "px";

      const data = {{ booths|tojson }};
      data.forEach(b => {
        const div = document.createElement("div");
        div.className = "booth";
        div.style.left   = b.x + "px";
        div.style.top    = b.y + "px";
        div.style.width  = b.width + "px";
        div.style.height = b.height + "px";

        div.textContent = b.label;
        div.style.backgroundColor = b.color || "#bdbdbd";

        // If past due, border is red & text is red
        if (b.past_due) {
          div.style.border = "2px solid #dc3545";
          div.style.color  = "#dc3545";
        } else {
          div.style.border = "2px solid #111";
          div.style.color  = "#000";
        }

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

      // For narrow screens => scale down
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
</body>
</html>
    """

    # Convert 'booths' to JSON so we can use it in JS
    from json import dumps
    rendered = render_template_string(
        html_template,
        booths=booths,
        planeW=planeW,
        planeH=planeH,
        occupancy_pct=occupancy_pct,
        rent_collection_pct=rent_collection_pct
    )
    return rendered

#
# -- RUN THE SERVER --
#
if __name__ == "__main__":
    app.run(debug=True, port=5001)