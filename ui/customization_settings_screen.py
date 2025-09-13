import os
import sys
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.colorpicker import ColorPicker
from utils.helpers import (
    load_settings, save_settings, apply_background, apply_styles_to_widget,
    create_styled_popup
)

class CustomizationSettingsScreen(Screen):
    """
    Screen for managing UI customization settings.
    """
    def __init__(self, **kwargs):
        super(CustomizationSettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.load_and_apply_settings()

    def load_and_apply_settings(self):
        settings = load_settings()
        self.ids.transparency_slider.value = settings.get('button_transparency', 1.0)
        self.ids.transparency_label.text = f"Button Transparenz: {int(self.ids.transparency_slider.value * 100)}%"
        self.ids.transparency_switch.active = settings.get('transparency_enabled', True)
        self.ids.keyboard_switch.active = settings.get('keyboard_enabled', sys.platform.startswith('linux'))
        self.ids.font_color_switch.active = settings.get('font_color_enabled', False)
        self.ids.popup_color_switch.active = settings.get('popup_color_enabled', False)
        self.ids.button_font_color_switch.active = settings.get('button_font_color_enabled', False)
        self.ids.button_bg_color_switch.active = settings.get('button_bg_color_enabled', False)

    def on_transparency_change(self, value):
        settings = load_settings()
        settings['button_transparency'] = value
        save_settings(settings)
        self.ids.transparency_label.text = f"Button Transparenz: {int(value * 100)}%"
        apply_styles_to_widget(self.manager)

    def on_transparency_toggle(self, value):
        settings = load_settings()
        settings['transparency_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_keyboard_toggle(self, value):
        settings = load_settings()
        settings['keyboard_enabled'] = value
        save_settings(settings)
        self.show_popup("Neustart erforderlich", "Die Änderung an der Bildschirmtastatur\nwird nach einem Neustart der Anwendung wirksam.")

    def on_font_color_toggle(self, value):
        settings = load_settings()
        settings['font_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_popup_color_toggle(self, value):
        settings = load_settings()
        settings['popup_color_enabled'] = value
        save_settings(settings)

    def on_button_font_color_toggle(self, value):
        settings = load_settings()
        settings['button_font_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def on_button_bg_color_toggle(self, value):
        settings = load_settings()
        settings['button_bg_color_enabled'] = value
        save_settings(settings)
        apply_styles_to_widget(self.manager)

    def show_color_picker(self, setting_type):
        settings = load_settings()
        key = f'custom_{setting_type}_color'
        initial_color = settings.get(key, [1, 1, 1, 1])
        color_picker = ColorPicker(color=initial_color)
        content = BoxLayout(orientation='vertical', spacing=10)
        content.add_widget(color_picker)
        save_btn = Button(text="Speichern", size_hint_y=None, height=44)
        content.add_widget(save_btn)
        popup = create_styled_popup(title="Farbe auswählen", content=content, size_hint=(0.8, 0.8))
        def save_color(instance):
            new_color = color_picker.color
            settings[key] = new_color
            save_settings(settings)
            if setting_type in ['font', 'button_font', 'button_bg']:
                apply_styles_to_widget(self.manager)
            popup.dismiss()
        save_btn.bind(on_press=save_color)
        popup.open()

    def show_popup(self, title, message):
        popup = create_styled_popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def go_back(self):
        self.manager.current = 'settings'
