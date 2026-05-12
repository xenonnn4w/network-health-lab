"""Probe each endpoint independently at DNS, TCP, and HTTP layers."""
import json
import socket
import time
import urllib.request
from collections import Counter


def inspect(host):
    result = {'host': host, 'healthy': False}
    start = time.monotonic()
    stage = 'dns'
    try:
        address = socket.gethostbyname(host)
        result['address'] = address
        stage = 'tcp'
        with socket.create_connection((address, 8080), timeout=1):
            pass
        stage = 'http'
        with urllib.request.urlopen(f'http://{address}:8080/', timeout=1) as response:
            result['http_status'] = response.status
            result['healthy'] = response.status == 200
    except (OSError, ValueError) as error:
        result.update(failed_stage=stage, error=str(error))
    result['duration_seconds'] = round(time.monotonic() - start, 4)
    return result


if __name__ == '__main__':
    checks = [inspect(host) for host in ['node-a', 'node-b']]
    print(json.dumps({'checks': checks, 'failure_groups': dict(Counter(
        item['failed_stage'] for item in checks if not item['healthy']))}))
