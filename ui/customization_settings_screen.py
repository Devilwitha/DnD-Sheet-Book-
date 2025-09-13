from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.uix.colorpicker import ColorPicker
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from utils.helpers import (
    load_settings, save_settings, apply_styles_to_widget, apply_background,
    create_styled_popup
)

class CustomizationSettingsScreen(Screen):
    """Screen for visual customization settings."""
    def __init__(self, **kwargs):
        super(CustomizationSettingsScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.load_switch_states()

    def go_back(self):
        self.app.change_screen('settings')

    def load_switch_states(self):
        settings = load_settings()
        self.ids.font_color_switch.active = settings.get('font_color_enabled', False)
        self.ids.popup_color_switch.active = settings.get('popup_color_enabled', False)
        self.ids.button_font_color_switch.active = settings.get('button_font_color_enabled', False)
        self.ids.button_bg_color_switch.active = settings.get('button_bg_color_enabled', False)

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
