"""DM-owned character updates shared by the sheet and network handlers."""
import copy

from core.character_actions import apply_character_action, state_token
from ui.character_approval import ask_dm


class CharacterAuthority:
    def commit_character(self, character, message=None):
        gm, nm = self.game_manager, self.network_manager
        cid, name = character.character_id, character.name
        current = gm.get_character_or_enemy_by_name(name)
        if current is None or getattr(current, 'character_id', None) != cid:
            raise ValueError('Charakter gehört nicht mehr zu dieser Sitzung.')
        if name in gm.online_players:
            gm.online_players[name] = character
        elif name in gm.disconnected_players:
            gm.disconnected_players[name] = character
        else:
            gm.offline_players = [character if p.character_id == cid else p for p in gm.offline_players]
        if name in gm.online_players or name in gm.disconnected_players:
            self.session_roster[cid] = copy.deepcopy(character.to_dict())
        with nm.lock:
            for info in nm.clients.values():
                if info.get('approved', True) and info['character'].character_id == cid:
                    info['character'] = character
        manager = getattr(self, 'manager', None)
        if manager and manager.has_screen('sheet'):
            sheet = manager.get_screen('sheet')
            if getattr(sheet.character, 'character_id', None) == cid:
                sheet.character = character
                if manager.current == 'sheet':
                    sheet.update_sheet()
        if manager and manager.has_screen('level_up'):
            level = manager.get_screen('level_up')
            if getattr(level.character, 'character_id', None) == cid:
                level.character = character
                if manager.current == 'level_up':
                    level.refresh_hp_preview()
        if message:
            self.log_message(message)
        self.update_ui()
        self.broadcast_game_state()
        self.checkpoint_archive('Charakter aktualisiert')

    def handle_character_action(self, addr, client, payload):
        request_id = payload.get('request_id')
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
            return
        seen = client.setdefault('character_requests', {})
        if request_id in seen:
            self._character_reply(addr, client, request_id, *seen[request_id])
            return
        if client.get('pending_character_action'):
            self._character_reply(addr, client, request_id, False, 'Eine Rast wartet noch auf die Entscheidung des DM.')
            return
        seen[request_id] = (False, 'Diese Aktion wird bereits bearbeitet.')
        while len(seen) > 128:
            del seen[next(iter(seen))]

        def finish(approved=True):
            with self.network_manager.lock:
                if self.network_manager.clients.get(addr) is not client:
                    return  # Never apply an old popup decision to a new connection.
            client.pop('pending_character_action', None)
            current = self.game_manager.online_players.get(client['character'].name)
            try:
                if not approved:
                    raise ValueError('Die Spielleitung hat die Rast abgelehnt.')
                if current is None or payload.get('state') != state_token(current):
                    raise ValueError('Der DM-Spielstand hat sich geändert. Anzeige aktualisiert; bitte Aktion erneut auswählen.')
                changed, message = apply_character_action(current, payload.get('action'), payload.get('args', {}))
                self.commit_character(changed, message)
            except ValueError as exc:
                self._character_reply(addr, client, request_id, False, str(exc))
            else:
                self._character_reply(addr, client, request_id, True, message)

        if payload.get('action') in ('short_rest', 'long_rest'):
            current = self.game_manager.online_players.get(client['character'].name)
            if current is None or payload.get('state') != state_token(current):
                finish()
                return
            client['pending_character_action'] = request_id
            kind = 'kurze' if payload['action'] == 'short_rest' else 'lange'
            ask_dm('Rast bestätigen', f'{current.name} möchte eine {kind} Rast machen. Zulassen?',
                   finish, lambda: finish(False))
        else:
            finish()

    def _character_reply(self, addr, client, request_id, success, message):
        client.setdefault('character_requests', {})[request_id] = (success, message)
        seen = client['character_requests']
        while len(seen) > 128:
            del seen[next(iter(seen))]
        current = self.game_manager.online_players.get(client['character'].name)
        if current is not None:
            self.network_manager.send_message(addr, 'SYNC_CHARACTER', current.to_dict())
        self.network_manager.send_message(addr, 'CHARACTER_ACTION_RESULT', {
            'request_id': request_id, 'success': success, 'message': message})
