"""
NLV Fireflies Usage Dashboard Generator

Fetches data from the Fireflies GraphQL API, renders a static HTML dashboard,
and pushes it to GitHub Pages via docs/index.html.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.fireflies.ai/graphql"
API_KEY = os.getenv("FIREFLIES_API_KEY")

if not API_KEY:
    print("ERROR: FIREFLIES_API_KEY not set in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def graphql_request(query, variables=None):
    """Execute a GraphQL request against the Fireflies API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
        sys.exit(1)
    return data["data"]


def fetch_users():
    """Fetch all team members from Fireflies (only paying seats)."""
    query = """
    {
        users {
            user_id
            email
            name
            is_admin
        }
    }
    """
    data = graphql_request(query)
    return data.get("users", [])


def fetch_all_transcripts():
    """Fetch all transcripts by paginating with limit=50."""
    query = """
    query Transcripts($limit: Int, $skip: Int) {
        transcripts(limit: $limit, skip: $skip) {
            id
            title
            date
            organizer_email
        }
    }
    """
    all_transcripts = []
    skip = 0
    limit = 50

    while True:
        data = graphql_request(query, {"limit": limit, "skip": skip})
        batch = data.get("transcripts", [])
        if not batch:
            break
        all_transcripts.extend(batch)
        print(f"  Fetched {len(all_transcripts)} transcripts so far...")
        skip += limit

    return all_transcripts


def compute_dashboard_data(users, transcripts):
    """Compute per-user metrics from users and transcripts."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    thirty_days_ago_ms = int(thirty_days_ago.timestamp() * 1000)

    # Build user lookup from the API-returned users (paying seats only)
    user_emails = set()
    user_map = {}
    for u in users:
        email = u.get("email", "").lower()
        user_emails.add(email)
        user_map[email] = {
            "name": u.get("name") or email.split("@")[0],
            "meetings_organized_all_time": 0,
            "meetings_organized_last_30": 0,
        }

    # Count organized meetings per user
    for t in transcripts:
        organizer = (t.get("organizer_email") or "").lower()
        if organizer not in user_map:
            continue

        user_map[organizer]["meetings_organized_all_time"] += 1

        # date is a Unix timestamp in milliseconds
        date_ms = t.get("date")
        if date_ms and date_ms >= thirty_days_ago_ms:
            user_map[organizer]["meetings_organized_last_30"] += 1

    # Sort by all-time meetings descending
    results = sorted(user_map.values(), key=lambda x: x["meetings_organized_all_time"], reverse=True)
    return results


def render_html(dashboard_data):
    """Render the dashboard as a standalone HTML page."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Prepare chart data
    names = [d["name"] for d in dashboard_data]
    all_time = [d["meetings_organized_all_time"] for d in dashboard_data]
    last_30 = [d["meetings_organized_last_30"] for d in dashboard_data]

    # Bake data as JSON
    js_data = json.dumps(dashboard_data, indent=2, default=str)
    names_json = json.dumps(names)
    all_time_json = json.dumps(all_time)
    last_30_json = json.dumps(last_30)

    # Build HTML with separate CSS/JS blocks to avoid f-string/template-literal conflicts
    html_top = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NLV Fireflies Usage Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #1a1a2e;
            padding: 2rem;
        }}
        .header {{
            text-align: center;
            margin-bottom: 2rem;
        }}
        .header h1 {{
            font-size: 1.8rem;
            color: #1a1a2e;
            margin-bottom: 0.25rem;
        }}
        .header .subtitle {{
            color: #6b7280;
            font-size: 0.95rem;
        }}
        .timestamp {{
            text-align: center;
            color: #9ca3af;
            font-size: 0.85rem;
            margin-bottom: 2rem;
        }}
        .charts {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .chart-card {{
            background: #fff;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        .chart-card h2 {{
            font-size: 1rem;
            color: #374151;
            margin-bottom: 1rem;
        }}
        .table-card {{
            background: #fff;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            overflow-x: auto;
        }}
        .table-card h2 {{
            font-size: 1rem;
            color: #374151;
            margin-bottom: 1rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th {{
            text-align: left;
            padding: 0.6rem 0.8rem;
            border-bottom: 2px solid #e5e7eb;
            color: #6b7280;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        td {{
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid #f3f4f6;
        }}
        tr:hover td {{
            background: #f9fafb;
        }}
        .num {{
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        @media (max-width: 768px) {{
            .charts {{ grid-template-columns: 1fr; }}
            body {{ padding: 1rem; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>NextLadder Ventures &mdash; Fireflies Dashboard</h1>
        <p class="subtitle">Team meeting analytics &amp; usage overview</p>
    </div>
    <p class="timestamp">Last updated: {timestamp}</p>

    <div class="charts">
        <div class="chart-card">
            <h2>Meetings Organized (All Time)</h2>
            <canvas id="chartAllTime"></canvas>
        </div>
        <div class="chart-card">
            <h2>Meetings Organized (Last 30 Days)</h2>
            <canvas id="chartLast30"></canvas>
        </div>
    </div>

    <div class="table-card">
        <h2>Team Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th class="num">Meetings (Last 30 Days)</th>
                    <th class="num">Meetings (All Time)</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>

    <script>
        const DATA = {js_data};
        const names = {names_json};
        const allTime = {all_time_json};
        const last30 = {last_30_json};
"""

    # JS block uses plain string (no f-string) to avoid $ conflicts
    js_block = """
        // Populate table
        const tbody = document.getElementById('tableBody');
        DATA.forEach(d => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${d.name}</td>
                <td class="num">${d.meetings_organized_last_30.toLocaleString()}</td>
                <td class="num">${d.meetings_organized_all_time.toLocaleString()}</td>
            `;
            tbody.appendChild(row);
        });

        // Chart colors
        const colors = [
            '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
            '#ec4899','#06b6d4','#84cc16','#f97316','#6366f1',
            '#14b8a6','#e11d48','#a855f7','#0ea5e9'
        ];

        function makeChart(canvasId, data, label) {
            new Chart(document.getElementById(canvasId), {
                type: 'bar',
                data: {
                    labels: names,
                    datasets: [{
                        label: label,
                        data: data,
                        backgroundColor: colors.slice(0, data.length),
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                        x: { ticks: { maxRotation: 45, minRotation: 45, font: { size: 11 } } }
                    }
                }
            });
        }

        makeChart('chartAllTime', allTime, 'Meetings Organized');
        makeChart('chartLast30', last30, 'Meetings (30d)');
    </script>
</body>
</html>"""

    return html_top + js_block


def git_push():
    """Stage, commit, and push the updated dashboard."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    subprocess.run(["git", "add", "docs/index.html"], check=True)

    # Check if there are changes to commit
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("No changes to commit.")
        return

    subprocess.run(
        ["git", "commit", "-m", f"Dashboard update {date_str}"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)
    print("Pushed to GitHub.")


def main():
    print("Fetching Fireflies users...")
    users = fetch_users()
    print(f"  Found {len(users)} users on Fireflies team.")

    print("Fetching all transcripts...")
    transcripts = fetch_all_transcripts()
    print(f"  Total transcripts: {len(transcripts)}")

    print("Computing dashboard data...")
    dashboard_data = compute_dashboard_data(users, transcripts)

    print("Rendering HTML...")
    html = render_html(dashboard_data)

    output_path = os.path.join(os.path.dirname(__file__), "docs", "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written to {output_path}")

    print("Pushing to GitHub...")
    git_push()

    print("Done!")


if __name__ == "__main__":
    main()
