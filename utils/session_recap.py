"""Bounded, editable DM recap. No inference and no changes to saved notes."""
from collections import deque


def build_recap(events, participants=None):
    tail, count = deque(maxlen=30), 0
    for event in events:
        count += 1
        def short(value, limit):
            value = str(value or '')
            return value if len(value) <= limit else value[:limit] + ' … [gekürzt]'
        tail.append(f"{short(event.get('time'), 40)} | {short(event.get('actor'), 80)}\n"
                    + short(event.get('message'), 240))
    names = ', '.join(str(p)[:100] for p in (participants or [])[:40]) or 'Noch keine erfasst'
    chunks = ['Rückblick – Entwurf für den DM', 'Teilnehmende: ' + names,
              f'Protokollierte Ereignisse: {count}']
    if count > len(tail):
        chunks.append(f'{count - len(tail)} frühere Ereignisse sind im vollständigen Journal nachlesbar.')
    chunks.extend(tail or ['Noch keine Spielereignisse protokolliert.'])
    chunks.append('Erzählerische Entscheidungen und offene Aufgaben bitte ergänzen. Dieser Entwurf bleibt privat.')
    result = '\n\n'.join(chunks)
    suffix = '\n[Entwurf gekürzt; vollständige Ereignisse im Journal.]'
    return result if len(result) <= 12000 else result[:12000-len(suffix)] + suffix
