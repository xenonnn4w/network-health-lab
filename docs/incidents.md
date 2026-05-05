# Network incident guide

Start with `python3 lab.py check`. A failure stage narrows the investigation but does not prove a root cause: both a blackhole route and a firewall rejection can fail at TCP. Inspect routes and firewall rules to distinguish them.

## DNS

`socket.gethostbyname` fails for both endpoints when the client resolver points at an unused loopback address. Inspect `/etc/resolv.conf` and `nslookup`. Restore the original resolver configuration rather than replacing names with hard-coded IP addresses.

## Routing

A /32 blackhole route affects only node B. Compare `ip route` with baseline addresses. Remove exactly that route; node A must remain healthy throughout the scenario.

## Firewall

An OUTPUT rule rejects TCP port 8080 to B. DNS should still resolve. Inspect `iptables -S OUTPUT`, remove the precise injected rule, and confirm both endpoints recover. Host firewall rules are untouched.

## Endpoint

Stopping B makes it unavailable. Depending on Docker DNS registration, this can appear as DNS or TCP failure. The test deliberately does not require a fixed failure stage here. Use node lifecycle evidence to identify the cause.

## Evidence and limits

`evidence/latest.json` records baseline, failed checks, resolver/routes/firewall diagnostics, recovered checks, and elapsed seconds. `failure_groups` groups current failures by stage; it is not a historical trend detector. Two endpoints are a demonstration, not a claim of fleet scale. Elapsed time includes fault injection and tooling overhead, not a production service-level metric.
