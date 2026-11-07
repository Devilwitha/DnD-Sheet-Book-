from kivy.uix.screenmanager import Screen
from kivy.utils import platform

class MainMenu(Screen):
    def on_pre_enter(self, *args):
        super(MainMenu, self).on_pre_enter(*args)
        if platform == 'android':
            for btn_id in ('btn_charakter', 'btn_dmspiel', 'btn_optionen'):
                btn = self.ids.get(btn_id)
                if btn:
                    btn.size_hint_y = 0.10