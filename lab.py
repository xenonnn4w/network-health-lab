#!/usr/bin/env python3
"""Two isolated networks, two endpoints, and one diagnostic client."""
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = 'network-health-lab'
IMAGE = PREFIX + ':local'
LABEL_KEY = 'io.xenonnn4w.lab'
LABEL_VALUE = 'network-health'
CLIENT = PREFIX + '-client'
NODES = [PREFIX + '-a', PREFIX + '-b']
NETWORKS = [PREFIX + '-front', PREFIX + '-back']


def run(*args, check=True):
    proc = subprocess.run(args, capture_output=True, text=True, timeout=180)
    if check and proc.returncode:
        raise RuntimeError(f'{args}: {proc.stderr or proc.stdout}')
    return {'code': proc.returncode, 'stdout': proc.stdout.strip(), 'stderr': proc.stderr.strip()}


def execute(command, check=True):
    return run('docker', 'exec', CLIENT, 'sh', '-c', command, check=check)


def down():
    for kind, names in [('container', [CLIENT] + NODES), ('network', NETWORKS)]:
        for name in names:
            fmt = '{{index .Config.Labels "' + LABEL_KEY + '"}}' if kind == 'container' else '{{index .Labels "' + LABEL_KEY + '"}}'
            result = run('docker', kind, 'inspect', '--format', fmt, name, check=False)
            if result['code'] == 0 and result['stdout'] == LABEL_VALUE:
                args = ['docker', kind, 'rm'] + (['-f'] if kind == 'container' else []) + [name]
                run(*args)


def up():
    for kind, names in [('container', [CLIENT] + NODES), ('network', NETWORKS)]:
        for name in names:
            if run('docker', kind, 'inspect', name, check=False)['code'] == 0:
                raise RuntimeError(f'{name} already exists. Run down first.')
    run('docker', 'build', '-f', str(ROOT / 'Containerfile'), '-t', IMAGE, str(ROOT))
    try:
        for network in NETWORKS:
            run('docker', 'network', 'create', '--internal', '--label', LABEL_KEY + '=' + LABEL_VALUE, network)
        for index, name in enumerate(NODES):
            run('docker', 'run', '-d', '--name', name, '--label', LABEL_KEY + '=' + LABEL_VALUE,
                '--network', NETWORKS[index], '--network-alias', ['node-a', 'node-b'][index],
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--user', '10001:10001', '--memory', '64m', '--cpus', '0.5', '--pids-limit', '32',
                IMAGE, 'python', '-m', 'http.server', '8080')
        run('docker', 'run', '-d', '--name', CLIENT, '--label', LABEL_KEY + '=' + LABEL_VALUE,
            '--network', NETWORKS[0], '--cap-drop', 'ALL', '--cap-add', 'NET_ADMIN',
            '--security-opt', 'no-new-privileges', '--memory', '64m', '--cpus', '0.5',
            '--pids-limit', '32', IMAGE)
        run('docker', 'network', 'connect', NETWORKS[1], CLIENT)
        execute('cp /etc/resolv.conf /tmp/resolv.original')
        wait_healthy()
    except BaseException:
        down()
        raise


def probe():
    return json.loads(run('docker', 'exec', CLIENT, 'python', '/opt/lab/health.py')['stdout'])


def wait_healthy():
    for _ in range(30):
        result = probe()
        if all(item['healthy'] for item in result['checks']):
            return result
        time.sleep(0.2)
    raise AssertionError(f'Endpoints did not recover: {result}')


def diagnostics():
    return execute('ip -br address; ip route; cat /etc/resolv.conf; iptables -S OUTPUT; '
                   'nslookup node-a; nslookup node-b', check=False)


def scenario(name):
    baseline = wait_healthy()
    address = baseline['checks'][1]['address']
    commands = {
        'dns': ("printf 'nameserver 127.0.0.2\noptions timeout:1 attempts:1\n' > /etc/resolv.conf",
                'cat /tmp/resolv.original > /etc/resolv.conf'),
        'route': (f'ip route add blackhole {address}/32', f'ip route del blackhole {address}/32'),
        'firewall': (f'iptables -A OUTPUT -d {address} -p tcp --dport 8080 -j REJECT',
                     f'iptables -D OUTPUT -d {address} -p tcp --dport 8080 -j REJECT'),
    }
    started = time.monotonic()
    try:
        if name == 'endpoint':
            run('docker', 'stop', '-t', '1', NODES[1])
        else:
            execute(commands[name][0])
        failed = probe()
        evidence = diagnostics()
        expected_count = 2 if name == 'dns' else 1
        if sum(not item['healthy'] for item in failed['checks']) != expected_count:
            raise AssertionError(f'{name}: unexpected affected endpoints: {failed}')
        if name == 'dns' and failed['failure_groups'] != {'dns': 2}:
            raise AssertionError(f'{name}: DNS layer not identified: {failed}')
        if name in ['route', 'firewall'] and failed['failure_groups'] != {'tcp': 1}:
            raise AssertionError(f'{name}: TCP layer not identified: {failed}')
    finally:
        if name == 'endpoint':
            run('docker', 'start', NODES[1])
        else:
            execute(commands[name][1])
    return {'scenario': name, 'baseline': baseline, 'failure': failed,
            'diagnostics': evidence, 'recovered': wait_healthy(),
            'elapsed_seconds': round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['up', 'down', 'check', 'test'])
    args = parser.parse_args()
    if args.action == 'up':
        up()
    elif args.action == 'down':
        down()
    elif args.action == 'check':
        print(json.dumps(probe(), indent=2))
    else:
        up()
        try:
            results = [scenario(name) for name in ['dns', 'route', 'firewall', 'endpoint']]
            folder = ROOT / 'evidence'
            folder.mkdir(exist_ok=True)
            report = {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
                      'environment': 'Docker Linux networks; synthetic faults', 'scenarios': results}
            (folder / 'latest.json').write_text(json.dumps(report, indent=2) + '\n')
            print(f'PASS: {len(results)} fault scenarios; evidence/latest.json')
        finally:
            down()


if __name__ == '__main__':
    main()
