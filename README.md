# Network Health Lab

Two Linux HTTP endpoints on separate Docker networks and a diagnostic client attached to both. Health checks distinguish DNS resolution, TCP reachability, and HTTP responses, then group failures across endpoints.

## Run

Requires Python 3.10+ and Docker Engine on Linux, with container-scoped `NET_ADMIN` support.

```sh
python3 lab.py test
```

Builds the image, creates two internal networks and three containers, tests DNS/routing/firewall/endpoint failures, and writes `evidence/latest.json`. Every scenario must detect its expected affected endpoints and recover both endpoints. Resources are removed afterward.

```sh
python3 lab.py up
python3 lab.py check
python3 lab.py down
```

## Scenarios

| Fault | Expected impact | Repair |
|---|---|---|
| Invalid client DNS resolver | Both names fail resolution | Restore resolver configuration |
| Blackhole route to node B | Node B TCP fails; A stays healthy | Remove host route |
| Client firewall rejects B:8080 | Node B TCP fails; A stays healthy | Remove exact firewall rule |
| Node B stopped | B fails; A stays healthy | Restart B |

Only the client gets `NET_ADMIN`; commands change its network namespace. No host ports, host mounts, host routing changes, or privileged containers are used. Networks are internal. The client is dual-homed, not a router. See [incident guide](docs/incidents.md).

This is a small virtual network lab, not evidence of physical cabling or production fleet administration.
