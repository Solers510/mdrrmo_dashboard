# MDRRMO Naic Production Architecture

## Recommended first production topology

Client browsers -> HTTPS reverse proxy -> Streamlit on loopback -> PostgreSQL.

For the first office deployment:
- expose only the HTTPS reverse-proxy endpoint to users;
- bind Streamlit to 127.0.0.1 when the proxy is on the same host;
- keep PostgreSQL unavailable to general office clients;
- keep the normal PostgreSQL application role least privilege;
- retain the dedicated restore-maintenance role only for restore/database-lifecycle work;
- keep .env and .streamlit/secrets.toml outside Git;
- copy verified backups to approved storage outside the application machine.

## Production OIDC contract

If the public base URL is:

https://mdrrmo.example.gov.ph

the callback must be:

https://mdrrmo.example.gov.ph/oauth2callback

The same callback must be configured in Streamlit secrets and registered in
the Google OIDC client.

## Remaining environment-owned decisions

- final production hostname;
- reverse proxy/TLS implementation;
- Windows server/VM or other approved host;
- service account and automatic startup method;
- firewall/network placement;
- approved off-machine backup destination;
- authoritative barangay/PSGC approval;
- alert-level approval;
- official report-layout decision.
