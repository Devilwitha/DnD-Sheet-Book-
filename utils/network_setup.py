"""Local endpoint selection and actionable connection diagnostics, without scanning."""
import ipaddress
import socket

MAX_ADDRESSES = 8
_LAN = tuple(ipaddress.ip_network(n) for n in
             ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'))
_VIRTUAL = ('vethernet', 'vmware', 'virtualbox', 'virtual', 'vpn', 'tailscale',
            'wireguard', 'tunnel', 'docker', 'hamachi', 'zerotier', 'loopback', 'wsl')


def lan_address(value):
    if not isinstance(value, str):
        raise ValueError('Nur lokale IPv4-Adressen sind zulässig.')
    try:
        ip = ipaddress.IPv4Address(value)
    except ValueError:
        raise ValueError('Nur lokale IPv4-Adressen sind zulässig.') from None
    if not any(ip in net for net in _LAN):
        raise ValueError('Nur lokale IPv4-Adressen sind zulässig.')
    return str(ip)


def local_interfaces():
    """Prefer physical LAN/WLAN; retain valid virtual addresses as fallbacks."""
    try:
        import psutil
        stats = psutil.net_if_stats()
        result = []
        for name, entries in psutil.net_if_addrs().items():
            if name not in stats or not stats[name].isup:
                continue
            for entry in entries:
                if entry.family != socket.AF_INET:
                    continue
                try:
                    address = lan_address(entry.address)
                except ValueError:
                    continue
                virtual = any(word in name.casefold() for word in _VIRTUAL)
                link_local = ipaddress.IPv4Address(address).is_link_local
                result.append({'address': address, 'adapter': name, 'virtual': virtual, 'link_local': link_local})
        result.sort(key=lambda r: (r['link_local'], r['virtual'], r['adapter'].casefold(), r['address']))
        seen = set()
        ordered = []
        for row in result:
            if row['address'] not in seen:
                ordered.append(row)
                seen.add(row['address'])
        return ordered[:MAX_ADDRESSES]
    except Exception:
        return []


def connection_error_kind(error):
    text = str(error).lower()
    if 'abgebrochen' in text or 'cancel' in text:
        return 'cancelled'
    if 'version' in text or 'protocol' in text:
        return 'version'
    if 'authentication' in text or 'wrong code' in text or 'proof' in text:
        return 'code'
    if 'duplicate character' in text:
        return 'duplicate'
    if 'timed out' in text or 'timeout' in text or '10060' in text:
        return 'timeout'
    if 'refused' in text or '10061' in text:
        return 'refused'
    if 'unreachable' in text or '10051' in text or '10065' in text:
        return 'unreachable'
    return 'connection'


def connection_help(error):
    kind = connection_error_kind(error)
    specific = {
        'code': 'Der Beitrittscode passt nicht zu diesem Host. Bitte den aktuellen QR-Code des DM erneut scannen.',
        'version': 'Host und Smartphone verwenden unterschiedliche App-Versionen. Bitte beide aktualisieren.',
        'duplicate': 'Dieser Charakter ist bereits verbunden. Die alte Verbindung zuerst beenden oder einen anderen Charakter wählen.',
        'cancelled': 'Verbindungsaufbau abgebrochen.',
    }
    if kind in specific:
        return specific[kind]
    lead = ('Der Laptop antwortet nicht rechtzeitig.' if kind == 'timeout' else
            'An dieser Adresse nimmt kein DM-Spiel Verbindungen an.' if kind == 'refused' else
            'Die Adresse des DM ist aus diesem Netzwerk nicht erreichbar.' if kind == 'unreachable' else
            'Die Verbindung zum DM konnte nicht aufgebaut werden.')
    return (lead + '\n\n1. DM-Sitzung geöffnet lassen und den aktuellen QR-Code neu scannen.'
            '\n2. Am Windows-DM unter „Verbindungshilfe“ die Windows-Freigabe einrichten.'
            '\n3. Beide Geräte ins normale WLAN verbinden. Gast-WLAN und manche Hotspots trennen Geräte voneinander.'
            '\n\nBei getrennter WLAN-Kommunikation hilft ein anderes gemeinsames Netzwerk. '
            'Diese Meldung allein beweist keine Firewall-Blockade.')
