"""oauthflow: the OAuth side of an MCP host, for the 2026-07-28 authorization profile.

discovery.py, pkce.py and client.py run discovery and the authorization code flow in process.
vault.py keeps issuer-bound credentials, stepup.py and register.py decide step-up scopes and
client enrollment, loopback.py finishes flows from browser redirects, and fetch.py fetches
metadata documents from URLs that someone else chose.
"""
