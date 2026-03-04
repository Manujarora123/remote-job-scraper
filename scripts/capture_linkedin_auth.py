"""
Capture LinkedIn authentication for the job resolver.

Opens a headed Chromium browser, lets the user log in manually,
then extracts li_at + JSESSIONID cookies and (optionally) saves
Playwright storage-state JSON and/or a .env.local file.

Usage:
  python scripts/capture_linkedin_auth.py
  python scripts/capture_linkedin_auth.py --save-env
  python scripts/capture_linkedin_auth.py --save-env --save-storage-state auth_state.json

⚠️  NEVER commit .env.local or storage-state JSON — they contain session secrets.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _extract_cookies(cookies: list[dict], names: set[str]) -> dict[str, str]:
    """Return {name: value} for cookies whose name is in *names*."""
    return {c["name"]: c["value"] for c in cookies if c["name"] in names}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Capture LinkedIn session cookies via headed browser login.",
    )
    ap.add_argument(
        "--save-env",
        action="store_true",
        help="Write LI_AT and JSESSIONID to .env.local in the repo root.",
    )
    ap.add_argument(
        "--save-storage-state",
        metavar="PATH",
        nargs="?",
        const="linkedin_storage_state.json",
        default=None,
        help="Save full Playwright storage state JSON (default: linkedin_storage_state.json).",
    )
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("❌ Playwright is not available. Install dependencies and run: playwright install chromium")
        return 1

    print("🔐 Opening LinkedIn login page in headed Chromium…")
    print("   Log in manually, then return here and press ENTER when done.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        input("✅ Press ENTER after you have logged in successfully → ")

        # --- extract cookies ---
        cookies = context.cookies("https://www.linkedin.com")
        wanted = _extract_cookies(cookies, {"li_at", "JSESSIONID"})

        li_at = wanted.get("li_at", "")
        jsessionid = wanted.get("JSESSIONID", "")

        if not li_at:
            print("❌ li_at cookie not found — login may have failed.")
            browser.close()
            return 1

        # --- display to stdout ---
        print("\n─── Extracted credentials ───")
        print(f"LI_AT={li_at}")
        print(f"JSESSIONID={jsessionid}")
        print("─────────────────────────────\n")

        # --- optional: save .env.local ---
        if args.save_env:
            env_path = Path(__file__).resolve().parent.parent / ".env.local"
            lines: list[str] = []
            if env_path.exists():
                lines = env_path.read_text().splitlines()
            # upsert keys
            key_map = {"LI_AT": li_at, "JSESSIONID": jsessionid}
            for key, val in key_map.items():
                found = False
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={val}"
                        found = True
                        break
                if not found:
                    lines.append(f"{key}={val}")
            env_path.write_text("\n".join(lines) + "\n")
            print(f"📄 Saved to {env_path}")

        # --- optional: save storage state ---
        if args.save_storage_state is not None:
            ss_path = Path(__file__).resolve().parent.parent / args.save_storage_state
            context.storage_state(path=str(ss_path))
            print(f"📦 Storage state saved to {ss_path}")

        context.close()
        browser.close()

    print("\n⚠️  These credentials are secrets — do NOT commit them to git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
