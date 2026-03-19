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

NLV_EMAILS = {
    "yuri.kim@nextladder.com",
    "kurt.tsuo@nextladder.com",
    "callie.schwartz@nextladder.com",
    "kyle.nelson@nextladder.com",
    "aras.jizan@nextladder.com",
    "baoyi.lei@nextladder.com",
    "rhett.dornbach-bender@nextladder.com",
    "richard.holmes@nextladder.com",
    "clarence.wardell@nextladder.com",
    "ryan.rippel@nextladder.com",
    "traci.terry@nextladder.com",
    "gretchen.reiter@nextladder.com",
    "jerry.kuo@nextladder.com",
    "hugh.chang@nextladder.com",
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
    """Fetch all team members from Fireflies."""
    query = """
    {
        users {
            user_id
            email
            name
            num_transcripts
            recent_meeting
            minutes_consumed
            is_admin
        }
    }
    """
    data = graphql_request(query)
    users = data.get("users", [])
    # Filter to NLV emails only
    return [u for u in users if u.get("email", "").lower() in NLV_EMAILS]


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

    # Build user lookup by email
    user_map = {}
    for u in users:
        email = u.get("email", "").lower()
        user_map[email] = {
            "name": u.get("name") or email.split("@")[0],
            "email": email,
            "num_transcripts": u.get("num_transcripts", 0),
            "minutes_consumed": u.get("minutes_consumed", 0),
            "recent_meeting": u.get("recent_meeting"),
            "is_admin": u.get("is_admin", False),
            "meetings_organized_all_time": 0,
            "meetings_organized_last_30": 0,
        }

    # Also add entries for NLV emails that may not appear in users but do organize meetings
    for email in NLV_EMAILS:
        if email not in user_map:
            user_map[email] = {
                "name": email.split("@")[0].replace(".", " ").title(),
                "email": email,
                "num_transcripts": 0,
                "minutes_consumed": 0,
                "recent_meeting": None,
                "is_admin": False,
                "meetings_organized_all_time": 0,
                "meetings_organized_last_30": 0,
            }

    # Count organized meetings per NLV user
    for t in transcripts:
        organizer = (t.get("organizer_email") or "").lower()
        if organizer not in user_map:
            continue

        user_map[organizer]["meetings_organized_all_time"] += 1

        # Check if within last 30 days
        date_str = t.get("date")
        if date_str:
            try:
                # Fireflies dateString can be various formats; try common ones
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    continue
                if dt >= thirty_days_ago:
                    user_map[organizer]["meetings_organized_last_30"] += 1
            except Exception:
                pass

    # Sort by meetings organized all time descending
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

    html = f"""<!DOCTYPE html>
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
        .admin-badge {{
            background: #dbeafe;
            color: #1e40af;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
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
                    <th>Email</th>
                    <th>Role</th>
                    <th class="num">Transcripts</th>
                    <th class="num">Minutes</th>
                    <th class="num">Organized (All)</th>
                    <th class="num">Organized (30d)</th>
                    <th>Last Meeting</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>

    <script>
        const DATA = {js_data};

        // Populate table
        const tbody = document.getElementById('tableBody');
        DATA.forEach(d => {{
            const row = document.createElement('tr');
            const adminBadge = d.is_admin ? '<span class="admin-badge">Admin</span>' : '';
            const lastMeeting = d.recent_meeting
                ? new Date(d.recent_meeting).toLocaleDateString()
                : '—';
            row.innerHTML = `
                <td>${"${d.name}"}</td>
                <td>${"${d.email}"}</td>
                <td>${"${adminBadge}"}</td>
                <td class="num">${"${d.num_transcripts.toLocaleString()}"}</td>
                <td class="num">${"${Math.round(d.minutes_consumed).toLocaleString()}"}</td>
                <td class="num">${"${d.meetings_organized_all_time.toLocaleString()}"}</td>
                <td class="num">${"${d.meetings_organized_last_30.toLocaleString()}"}</td>
                <td>${"${lastMeeting}"}</td>
            `;
            tbody.appendChild(row);
        }});

        // Chart colors
        const colors = [
            '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
            '#ec4899','#06b6d4','#84cc16','#f97316','#6366f1',
            '#14b8a6','#e11d48','#a855f7','#0ea5e9'
        ];

        const names = {json.dumps(names)};
        const allTime = {json.dumps(all_time)};
        const last30 = {json.dumps(last_30)};

        function makeChart(canvasId, data, label) {{
            new Chart(document.getElementById(canvasId), {{
                type: 'bar',
                data: {{
                    labels: names,
                    datasets: [{{
                        label: label,
                        data: data,
                        backgroundColor: colors.slice(0, data.length),
                        borderRadius: 4,
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{ display: false }},
                    }},
                    scales: {{
                        y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }},
                        x: {{ ticks: {{ maxRotation: 45, minRotation: 45, font: {{ size: 11 }} }} }}
                    }}
                }}
            }});
        }}

        makeChart('chartAllTime', allTime, 'Meetings Organized');
        makeChart('chartLast30', last30, 'Meetings (30d)');
    </script>
</body>
</html>"""
    return html


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
    print(f"  Found {len(users)} NLV users.")

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
