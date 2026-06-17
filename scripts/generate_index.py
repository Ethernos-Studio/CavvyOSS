#!/usr/bin/env python3
"""
ESSO-10430 Package Index Generator (Dual-Domain Edition)

Fetches cert data from cert repository via GitHub API,
generates index.html and index.json for package.cavvy.ethernos.net

Usage:
    CERT_REPO=ethernos/esso-certs python scripts/generate_index.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import jinja2
import requests

PAGES_DIR = Path("pages")
PAGES_DIR.mkdir(exist_ok=True)

CERT_REPO = os.getenv("CERT_REPO", "ethernos/esso-certs")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CERT_BASE = "https://cert.cavvy.ethernos.net"


def fetch_cert_files():
    """Download all .json and .cert files from cert repo via GitHub API."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    api_url = f"https://api.github.com/repos/{CERT_REPO}/contents/"
    resp = requests.get(api_url, headers=headers, timeout=30)
    resp.raise_for_status()
    files = resp.json()

    tmp_dir = Path("certs-tmp")
    tmp_dir.mkdir(exist_ok=True)

    for f in files:
        if not isinstance(f, dict):
            continue
        name = f.get("name", "")
        if not (name.endswith(".json") or name.endswith(".cert")):
            continue
        download_url = f.get("download_url")
        if not download_url:
            continue

        r = requests.get(download_url, timeout=30)
        r.raise_for_status()
        (tmp_dir / name).write_text(r.text, encoding="utf-8")
        print(f"[Fetch] {name}")

    return tmp_dir


def scan_certs(certs_dir):
    packages = []
    for meta_file in sorted(certs_dir.glob("*.json")):
        if meta_file.name.endswith(".cert"):
            continue
        fingerprint = meta_file.stem
        cert_file = certs_dir / f"{fingerprint}.cert"

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Failed to parse {meta_file}: {e}")
            continue

        entry = {
            "fingerprint": fingerprint,
            "name": meta.get("current_name", "unknown"),
            "repository": meta.get("current_repository", ""),
            "publisher": meta.get("current_publisher", ""),
            "status": "active",
            "latest_version": None,
            "latest_commit": None,
            "latest_sha256": None,
            "certified_at": None,
            "expires_at": None,
        }

        if cert_file.exists():
            try:
                cert = json.loads(cert_file.read_text(encoding="utf-8"))
                entry["latest_version"] = cert.get("version")
                entry["latest_commit"] = cert.get("commit_hash")
                entry["latest_sha256"] = cert.get("package_sha256")
                entry["certified_at"] = cert.get("certified_at")
                entry["expires_at"] = cert.get("expires_at")
            except Exception as e:
                print(f"[WARN] Failed to parse {cert_file}: {e}")

        packages.append(entry)

    return packages


def generate_index_json(packages):
    data = {
        "esso_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "packages": []
    }

    for p in packages:
        pkg = {
            "fingerprint": p["fingerprint"],
            "name": p["name"],
            "latest_version": p.get("latest_version") or "0.0.0",
            "repository": p["repository"],
            "latest_commit": p.get("latest_commit") or "",
            "latest_sha256": p.get("latest_sha256") or "",
            "cert_url": f"{CERT_BASE}/{p['fingerprint']}.cert",
            "meta_url": f"{CERT_BASE}/{p['fingerprint']}.json",
            "status": p["status"]
        }
        data["packages"].append(pkg)

    path = PAGES_DIR / "index.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {path}")
    return data


def generate_index_html(packages):
    env = jinja2.Environment()
    template = env.from_string(HTML_TEMPLATE)
    html = template.render(
        cert_base=CERT_BASE,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        count=len(packages),
        packages=packages
    )
    path = PAGES_DIR / "index.html"
    path.write_text(html, encoding="utf-8")
    print(f"[OK] {path}")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ethernos Official Secure Source Index</title>
    <style>
        :root {
            --bg: #0d1117;
            --fg: #c9d1d9;
            --accent: #58a6ff;
            --border: #30363d;
            --card: #161b22;
            --ok: #3fb950;
            --danger: #f85149;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--fg);
            line-height: 1.6;
        }
        header {
            border-bottom: 1px solid var(--border);
            padding: 2rem 1rem;
            text-align: center;
        }
        header h1 { margin: 0; font-size: 1.75rem; color: var(--accent); }
        header p { margin: 0.5rem 0 0; color: #8b949e; font-size: 0.9rem; }
        .stats {
            display: flex;
            justify-content: center;
            gap: 2rem;
            padding: 1rem;
            border-bottom: 1px solid var(--border);
        }
        .stat { text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: 600; color: var(--accent); }
        .stat-label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
        .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
        .search-box {
            width: 100%; padding: 0.75rem 1rem; background: var(--card);
            border: 1px solid var(--border); border-radius: 6px; color: var(--fg);
            font-size: 1rem; margin-bottom: 1rem;
        }
        .search-box:focus { outline: none; border-color: var(--accent); }
        table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
        thead { position: sticky; top: 0; background: var(--bg); }
        th {
            text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border);
            color: #8b949e; font-weight: 500; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.05em;
        }
        td { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); vertical-align: top; }
        tr:hover td { background: rgba(88, 166, 255, 0.05); }
        .pkg-name { font-weight: 600; color: var(--accent); }
        .pkg-name a { color: inherit; text-decoration: none; }
        .pkg-name a:hover { text-decoration: underline; }
        .fingerprint {
            font-family: "SFMono-Regular", Consolas, Menlo, monospace;
            font-size: 0.75rem; color: #8b949e;
        }
        .hash {
            font-family: "SFMono-Regular", Consolas, Menlo, monospace;
            font-size: 0.7rem; color: #8b949e;
            max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .badge {
            display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px;
            font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
        }
        .badge-active { background: rgba(63, 185, 80, 0.15); color: var(--ok); }
        .badge-retired { background: rgba(248, 81, 73, 0.15); color: var(--danger); }
        .links a { color: var(--accent); text-decoration: none; font-size: 0.8rem; margin-right: 0.75rem; }
        .links a:hover { text-decoration: underline; }
        footer { text-align: center; padding: 2rem 1rem; border-top: 1px solid var(--border); color: #8b949e; font-size: 0.8rem; }
        @media (max-width: 768px) {
            .stats { flex-direction: column; gap: 1rem; }
            th, td { padding: 0.5rem; }
            .hash { max-width: 100px; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🔐 Ethernos Official Secure Source</h1>
        <p>ESSO-10430 Certified Package Index &mdash; Generated at {{ generated_at }}</p>
    </header>
    <div class="stats">
        <div class="stat"><div class="stat-value">{{ count }}</div><div class="stat-label">Certified Packages</div></div>
        <div class="stat"><div class="stat-value">ESSO-10430</div><div class="stat-label">Spec Version</div></div>
        <div class="stat"><div class="stat-value">Ed25519</div><div class="stat-label">Signature</div></div>
    </div>
    <div class="container">
        <input type="text" class="search-box" id="search" placeholder="Search packages by name, fingerprint, or publisher...">
        <table>
            <thead>
                <tr>
                    <th>Package</th><th>Version</th><th>Publisher</th><th>Commit</th><th>SHA-256</th><th>Status</th><th>Links</th>
                </tr>
            </thead>
            <tbody id="pkg-table">
                {% for p in packages %}
                <tr data-search="{{ p.name|lower }} {{ p.fingerprint|lower }} {{ p.publisher|lower }}">
                    <td>
                        <div class="pkg-name">
                            {% if p.repository %}<a href="{{ p.repository }}" target="_blank">{{ p.name }}</a>
                            {% else %}{{ p.name }}{% endif %}
                        </div>
                        <div class="fingerprint">{{ p.fingerprint }}</div>
                    </td>
                    <td>{{ p.latest_version or "N/A" }}</td>
                    <td>{{ p.publisher or "N/A" }}</td>
                    <td>{% if p.latest_commit %}<span class="hash" title="{{ p.latest_commit }}">{{ p.latest_commit[:12] }}...</span>{% else %}N/A{% endif %}</td>
                    <td>{% if p.latest_sha256 %}<span class="hash" title="{{ p.latest_sha256 }}">{{ p.latest_sha256[:16] }}...</span>{% else %}N/A{% endif %}</td>
                    <td><span class="badge badge-{{ p.status }}">{{ p.status }}</span></td>
                    <td class="links">
                        <a href="{{ cert_base }}/{{ p.fingerprint }}.cert" target="_blank">Cert</a>
                        <a href="{{ cert_base }}/{{ p.fingerprint }}.json" target="_blank">Meta</a>
                        {% if p.repository %}<a href="{{ p.repository }}" target="_blank">Repo</a>{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <footer>
        <p>Ethernos Studio &mdash; Security Lab &mdash; <a href="index.json" style="color: var(--accent);">Raw JSON</a></p>
        <p>Cert server: <a href="{{ cert_base }}" style="color: var(--accent);">{{ cert_base }}</a></p>
        <p>Auto-generated by GitHub Actions from cert repository.</p>
    </footer>
    <script>
        document.getElementById('search').addEventListener('input', function(e) {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('#pkg-table tr').forEach(row => {
                const hay = row.getAttribute('data-search') || '';
                row.style.display = hay.includes(term) ? '' : 'none';
            });
        });
    </script>
</body>
</html>
"""


def main():
    print(f"[INFO] Fetching certs from {CERT_REPO}...")
    certs_dir = fetch_cert_files()

    print("[INFO] Scanning...")
    packages = scan_certs(certs_dir)
    print(f"[INFO] Found {len(packages)} package(s)")

    print("[INFO] Generating index.json...")
    generate_index_json(packages)

    print("[INFO] Generating index.html...")
    generate_index_html(packages)

    print("[DONE] All files written to pages/")


if __name__ == "__main__":
    main()
