import csv
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(
    PROJECT_DIR, "data_process", "output", "processed_features.csv"
)
PORT = 8000


def load_rows():
    if not os.path.exists(OUTPUT_FILE):
        return []
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/data":
            payload = json.dumps(
                {
                    "rows": load_rows(),
                    "output_file": OUTPUT_FILE,
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path in ("/", "/index.html"):
            page = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        return


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Travel Guard Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #0f172a; color: #e2e8f0; }
    main { max-width: 1200px; margin: 0 auto; padding: 36px 22px; }
    h1 { margin: 0 0 8px; color: #f8fafc; }
    .muted { color: #94a3b8; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin: 28px 0; }
    .card { min-width: 180px; padding: 18px; border: 1px solid #334155;
      border-radius: 12px; background: #1e293b; }
    .label { color: #94a3b8; font-size: 13px; }
    .value { display: block; margin-top: 8px; font-size: 28px; font-weight: 700; }
    .panel { overflow: auto; border: 1px solid #334155; border-radius: 12px; }
    table { width: 100%; border-collapse: collapse; min-width: 620px; }
    th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #334155; }
    th { background: #1e293b; color: #cbd5e1; }
    tr:last-child td { border-bottom: 0; }
    .status { margin-top: 18px; color: #86efac; }
  </style>
</head>
<body>
  <main>
    <h1>Travel Guard Dashboard</h1>
    <div class="muted">Processed travel recommendation features</div>
    <section class="cards">
      <div class="card"><span class="label">Processed samples</span><span class="value" id="samples">-</span></div>
      <div class="card"><span class="label">Feature columns</span><span class="value" id="features">-</span></div>
      <div class="card"><span class="label">Output status</span><span class="value" id="output">-</span></div>
    </section>
    <div class="panel">
      <table>
        <thead><tr><th>User ID</th><th>Action sequence values</th><th>POI labels</th><th>Travel labels</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <div class="status" id="status">Loading processed data...</div>
  </main>
  <script>
    const size = value => value ? value.split(',').filter(Boolean).length : 0;
    fetch('/api/data').then(response => response.json()).then(data => {
      const rows = data.rows || [];
      document.getElementById('samples').textContent = rows.length;
      document.getElementById('features').textContent = rows.length ? Object.keys(rows[0]).length : 0;
      document.getElementById('output').textContent = rows.length ? 'Ready' : 'No data';
      document.getElementById('rows').innerHTML = rows.map(row => `
        <tr><td>${row.user_id || '-'}</td>
        <td>${size(row.action_list_poi_id)}</td>
        <td>${size(row.iq_label_poi_id)}</td>
        <td>${size(row.iq_label_travel_mode)}</td></tr>`).join('');
      document.getElementById('status').textContent =
        rows.length ? 'Data loaded from processed_features.csv' : 'Run the data pipeline first.';
    }).catch(() => {
      document.getElementById('status').textContent = 'Could not load processed data.';
    });
  </script>
</body>
</html>"""


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DashboardHandler)
    url = "http://127.0.0.1:{}/".format(PORT)
    print("Travel Guard dashboard: {}".format(url))
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
