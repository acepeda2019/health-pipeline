"""
One-time OAuth2 flow to get Whoop access + refresh tokens.
Run from project root: uv run scripts/whoop_auth.py
"""

import base64
import http.server
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
import json
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["WHOOP_CLIENT_ID"]
CLIENT_SECRET = os.environ["WHOOP_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost:9090/callback"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPES = "offline read:recovery read:sleep read:workout read:profile read:body_measurement"

auth_code = None
state = secrets.token_hex(16)


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Auth successful! You can close this tab.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

    def log_message(self, format, *args):
        pass


def get_tokens(code):
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}")
        print(e.read().decode())
        raise


params = urllib.parse.urlencode({
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPES,
    "state": state,
})
url = f"{AUTH_URL}?{params}"

print("Opening Whoop authorization page...")
webbrowser.open(url)
print(f"If it didn't open, visit:\n{url}\n")
print("Waiting for callback on http://localhost:9090/callback ...")

server = http.server.HTTPServer(("localhost", 9090), CallbackHandler)
server.handle_request()

if not auth_code:
    print("ERROR: No authorization code received.")
    exit(1)

print("Got auth code, exchanging for tokens...")
tokens = get_tokens(auth_code)

print("\n--- Add these to your .env ---")
print(f"WHOOP_ACCESS_TOKEN={tokens['access_token']}")
print(f"WHOOP_REFRESH_TOKEN={tokens['refresh_token']}")
print(f"\nAccess token expires in: {tokens.get('expires_in', '?')} seconds")
