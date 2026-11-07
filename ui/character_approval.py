"""Explicit DM decisions, with no character mutation before confirmation."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from utils.helpers import create_styled_popup, apply_styles_to_widget


def ask_dm(title, text, accept, reject, accept_text='Zulassen'):
    content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
    scroll = ScrollView()
    label = Label(text=text, size_hint_y=None, halign='left', valign='top')
    label.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)),
               texture_size=lambda w, v: setattr(w, 'height', v[1]))
    scroll.add_widget(label)
    content.add_widget(scroll)
    row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
    yes, no = Button(text=accept_text), Button(text='Ablehnen')
    row.add_widget(yes)
    row.add_widget(no)
    content.add_widget(row)
    popup = create_styled_popup(title=title, content=content, size_hint=(.9, .75), auto_dismiss=False)
    done = False

    def decide(callback):
        nonlocal done
        if done:
            return
        done = True
        popup.dismiss()
        callback()

    yes.bind(on_release=lambda *_: decide(accept))
    no.bind(on_release=lambda *_: decide(reject))
    popup.cancel_decision = lambda: decide(reject)

    def dismissed(*_):
        nonlocal done
        if not done:
            done = True
            reject()

    popup.bind(on_dismiss=dismissed)
    apply_styles_to_widget(content)
    popup.open()
    return popup


def character_summary(character):
    c = character
    return (f'{c.name}\n{c.race} · {c.char_class} · Stufe {c.level}\n'
            f'HP {c.hit_points}/{c.max_hit_points} · Rüstungsklasse {c.armor_class}\n'
            + ', '.join(f'{k}: {v}' for k, v in c.abilities.items())
            + f'\nWaffe: {c.equipped_weapon}\nInventar: '
            + ', '.join(f"{i['name']} ×{i.get('quantity', 1)}" for i in c.inventory)
            + '\n\nNeuer Charakter: Diese Anfangswerte kommen vom Spieler. '
            'Nur mit deiner Zustimmung werden sie in die Sitzung übernommen. '
            'Danach gilt der DM-Spielstand. Korrekturen und Stufenaufstiege kannst du im Charakterbogen vornehmen.')
