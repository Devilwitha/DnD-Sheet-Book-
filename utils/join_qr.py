"""Bounded, local-only pairing QR payloads. Scanning never opens a URL."""
import ipaddress
import json

from utils.pairing import normalize_code, valid_code16hex
from utils.network_setup import lan_address, MAX_ADDRESSES

_NETWORKS = tuple(ipaddress.ip_network(n) for n in
                  ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'))


def _validate(data):
    if not isinstance(data, dict):
        raise ValueError('Kein gültiger DnD-Lokal-Beitrittscode.')
    fields = {'app', 'v', 'host', 'port', 'code'}
    if data.get('v') == 2:
        fields.add('hosts')
    if set(data) != fields:
        raise ValueError('Kein gültiger DnD-Lokal-Beitrittscode.')
    if data['app'] != 'dnd-local' or type(data['v']) is not int or data['v'] not in (1, 2):
        raise ValueError('Dieser QR-Code gehört nicht zu dieser App-Version.')
    try:
        address = ipaddress.IPv4Address(data['host'])
    except (ValueError, TypeError):
        raise ValueError('Der QR-Code muss eine lokale IPv4-Adresse enthalten.') from None
    if not any(address in network for network in _NETWORKS):
        raise ValueError('Im QR-Code sind nur lokale Netzwerkadressen erlaubt.')
    if type(data['port']) is not int or not 1 <= data['port'] <= 65535:
        raise ValueError('Ungültiger Netzwerkport im QR-Code.')
    code = normalize_code(data['code'])
    if not valid_code16hex(code):
        raise ValueError('Ungültiger Beitrittscode im QR-Code.')
    hosts = data.get('hosts', [str(address)])
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= MAX_ADDRESSES:
        raise ValueError('Ungültige Adressliste im QR-Code.')
    hosts = [lan_address(host) for host in hosts]
    if hosts[0] != str(address) or len(set(hosts)) != len(hosts):
        raise ValueError('Ungültige Adressliste im QR-Code.')
    return hosts, data['port'], code


def make_join_payload(host, port, code, addresses=None):
    data = {'app': 'dnd-local', 'v': 1, 'host': host, 'port': port, 'code': code}
    if addresses is not None:
        data.update(v=2, hosts=list(dict.fromkeys([host, *addresses]))[:MAX_ADDRESSES])
    hosts, port, code = _validate(data)
    data.update(host=hosts[0], port=port, code=code)
    return json.dumps(data, separators=(',', ':'), ensure_ascii=True)


def parse_join_payload(text):
    hosts, port, code = parse_join_candidates(text)
    return hosts[0], port, code


def parse_join_candidates(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 1024:
        raise ValueError('Kein gültiger DnD-Lokal-Beitrittscode.')
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError('Doppelte Felder im QR-Code.')
            data[key] = value
        return data
    try:
        data = json.loads(text, object_pairs_hook=unique)
    except (ValueError, RecursionError):
        raise ValueError('Kein gültiger DnD-Lokal-Beitrittscode.') from None
    return _validate(data)
