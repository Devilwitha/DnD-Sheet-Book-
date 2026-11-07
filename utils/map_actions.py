"""Shared map geometry and user-facing action results."""
from collections import deque


def reachable_tiles(map_data, start, budget):
    tiles = (map_data or {}).get('tiles', {})
    if start not in tiles or budget <= 0:
        return {}
    seen = {start: 0}
    queue = deque([start])
    while queue:
        row, col = queue.popleft()
        cost = seen[(row, col)] + 1
        if cost > budget:
            continue
        for pos in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
            tile = tiles.get(pos)
            if pos in seen or not isinstance(tile, dict):
                continue
            if tile.get('type') == 'Wall' or tile.get('object') or tile.get('furniture'):
                continue
            seen[pos] = cost
            queue.append(pos)
    seen.pop(start, None)
    return seen


_REASONS = {
    'Cannot move out of turn.': 'Diese Figur ist gerade nicht am Zug.',
    'Cannot attack out of turn.': 'Diese Figur ist gerade nicht am Zug.',
    'No map loaded.': 'Zuerst eine Karte laden.',
    'Invalid target position.': 'Ungültiges Zielfeld.',
    'Target out of bounds.': 'Das Ziel liegt außerhalb der Karte.',
    'Target tile does not exist.': 'Dieses Feld existiert nicht.',
    'Target is a wall.': 'Eine Wand blockiert dieses Feld.',
    'Target is occupied.': 'Dieses Feld ist bereits besetzt.',
    'Target is blocked by furniture.': 'Ein Gegenstand blockiert dieses Feld.',
    'Target not reachable with remaining movement.': 'Dieses Feld ist mit der übrigen Bewegung nicht erreichbar.',
    'No attacks left.': 'Für diesen Zug sind keine Angriffe mehr übrig.',
    'Attacker or target not found.': 'Angreifer oder Ziel ist nicht in der Sitzung vorhanden.',
    'Cannot attack self.': 'Wähle eine andere Figur als Ziel.',
    'Attacker or target not on map.': 'Angreifer und Ziel müssen auf der Karte stehen.',
    'Target out of range.': 'Das Ziel liegt außerhalb der Waffenreichweite.',
    'Invalid attack roll.': 'Ungültiger Angriffswurf.',
    'Invalid damage roll.': 'Ungültiger Schadenswurf.',
}


def action_reason(reason):
    return _REASONS.get(reason, reason or 'Aktion nicht möglich.')


def attack_result_text(attacker, target, result):
    if not result.get('success'):
        return action_reason(result.get('reason'))
    detail = (result.get('roll_detail', '') + '\n') if result.get('roll_detail') else ''
    if not result.get('hit'):
        return detail + f'{attacker} verfehlt {target}.'
    suffix = (' 0 TP – Figur bleibt auf der Karte; Zustand beim DM klären.' if result.get('incapacitated')
              else ' Ziel besiegt.' if result.get('defeated') else f" {result['target_hp']} LP verbleiben.")
    if result.get('critical'):
        detail += 'Kritischer Treffer.\n'
    return detail + f"{attacker} trifft {target}: {result['damage']} Schaden." + suffix
