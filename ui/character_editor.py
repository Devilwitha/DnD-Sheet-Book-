import pickle
import random
from functools import partial
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy3 import Scene, Renderer, PerspectiveCamera
from kivy3.light import Light
from .stl_loader import STLLoader

from data_manager import (
    RACE_DATA, CLASS_DATA, ALIGNMENT_DATA, BACKGROUND_DATA
)
from utils.helpers import apply_background, apply_styles_to_widget, load_settings

class CharacterEditor(Screen):
    """Editor-Bildschirm zum Bearbeiten eines vorhandenen Charakters."""
    def __init__(self, **kwargs):
        super(CharacterEditor, self).__init__(**kwargs)
        self.character = None
        self.inputs = {}
        self.ability_scores_labels = {}
        self.scene = Scene()
        self.renderer = Renderer()
        self.renderer.scene = self.scene
        self.light = Light(renderer=self.renderer, intensity=0.5)
        self.light.pos_z = 10
        self.camera = PerspectiveCamera(75, 1, 1, 1000)
        self.stl_path = None
        self.touches = []
        self.last_touch_distance = 0
        self.loaded_obj = None
        self.touch_mode = None

    def build_ui(self):
        layout = self.ids.editor_layout
        layout.clear_widgets()

        back_button = Button(text="Zurück zum Hauptmenü",
                             on_press=lambda x: setattr(self.manager, 'current', 'main'),
                             size_hint_y=None,
                             height=44)
        layout.add_widget(back_button)
        layout.add_widget(Label(text="", size_hint_y=None, height=44))

        default_height = 44
        multiline_height = 120

        fields = [
            ("Name", "TextInput", default_height, []),
            ("Rasse", "Spinner", default_height, sorted(RACE_DATA.keys())),
            ("Klasse", "Spinner", default_height, sorted(CLASS_DATA.keys())),
            ("Gesinnung", "Spinner", default_height, sorted(ALIGNMENT_DATA.keys())),
            ("Hintergrund", "Spinner", default_height, sorted(BACKGROUND_DATA.keys())),
            ("Persönliche Merkmale", "TextInput", multiline_height, []),
            ("Ideale", "TextInput", multiline_height, []),
            ("Bindungen", "TextInput", multiline_height, []),
            ("Makel", "TextInput", multiline_height, [])
        ]

        for field_name, widget_type, height, values in fields:
            label = Label(text=f"{field_name}:", size_hint=(None, None), width=180, height=height, halign='left', valign='middle')
            label.bind(size=label.setter('text_size'))
            layout.add_widget(label)

            if widget_type == "TextInput":
                widget = TextInput(size_hint_y=None, height=height, multiline=(height > default_height))
            else:
                widget = Spinner(values=values, size_hint_y=None, height=height)

            self.inputs[field_name] = widget
            layout.add_widget(widget)

        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(None, None), width=180, height=default_height, halign='left', valign='middle')
            layout.add_widget(label)

            stat_box = BoxLayout(size_hint_y=None, height=default_height)
            minus_btn = Button(text="-", on_press=partial(self.adjust_ability, ability, -1))
            score_label = Label()
            plus_btn = Button(text="+", on_press=partial(self.adjust_ability, ability, 1))

            stat_box.add_widget(minus_btn)
            stat_box.add_widget(score_label)
            stat_box.add_widget(plus_btn)

            self.ability_scores_labels[ability] = score_label
            layout.add_widget(stat_box)

        layout.add_widget(Label(size_hint_y=None, height=10))
        layout.add_widget(Label(size_hint_y=None, height=10))

        save_button = Button(text="Änderungen speichern", on_press=self.save_character, size_hint_y=None, height=default_height)

        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            container = GridLayout(cols=1, size_hint_y=None, height=400)
            viewer_layout = BoxLayout(orientation='vertical')
            stl_viewer_placeholder = BoxLayout()
            self.ids.stl_viewer_placeholder = stl_viewer_placeholder
            viewer_layout.add_widget(stl_viewer_placeholder)

            file_chooser_button = Button(text="STL Datei auswählen", size_hint_y=0.1, on_press=lambda x: self.show_file_chooser())
            viewer_layout.add_widget(file_chooser_button)

            viewer_layout.add_widget(Label(text="Helligkeit", size_hint_y=0.05))
            brightness_slider = Slider(min=0, max=1.5, value=0.5, size_hint_y=0.1)
            self.ids.brightness_slider = brightness_slider
            viewer_layout.add_widget(brightness_slider)

            viewer_layout.add_widget(Label(text="Licht Position X", size_hint_y=0.05))
            light_x_slider = Slider(min=-30, max=30, value=0, size_hint_y=0.1)
            self.ids.light_x_slider = light_x_slider
            viewer_layout.add_widget(light_x_slider)

            viewer_layout.add_widget(Label(text="Licht Position Y", size_hint_y=0.05))
            light_y_slider = Slider(min=-30, max=30, value=0, size_hint_y=0.1)
            self.ids.light_y_slider = light_y_slider
            viewer_layout.add_widget(light_y_slider)

            viewer_layout.add_widget(Label(text="Licht Position Z", size_hint_y=0.05))
            light_z_slider = Slider(min=-30, max=30, value=10, size_hint_y=0.1)
            self.ids.light_z_slider = light_z_slider
            viewer_layout.add_widget(light_z_slider)

            container.add_widget(viewer_layout)
            layout.add_widget(container)
            layout.add_widget(Label())

        layout.add_widget(save_button)

    def on_pre_enter(self, *args):
        self.build_ui()
        self.load_character(self.character)
        apply_background(self)
        apply_styles_to_widget(self)
        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            Clock.schedule_interval(self._update_scene, 1.0 / 60.0)

    def load_character(self, character):
        self.character = character
        if not self.character:
            return

        self.inputs["Name"].text = self.character.name
        self.inputs["Rasse"].text = self.character.race
        self.inputs["Klasse"].text = self.character.char_class
        self.inputs["Gesinnung"].text = self.character.alignment
        self.inputs["Hintergrund"].text = self.character.background
        self.inputs["Persönliche Merkmale"].text = self.character.personality_traits
        self.inputs["Ideale"].text = self.character.ideals
        self.inputs["Bindungen"].text = self.character.bonds
        self.inputs["Makel"].text = self.character.flaws

        for ability, label in self.ability_scores_labels.items():
            label.text = str(self.character.base_abilities.get(ability, 10))

        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            if hasattr(self.character, 'stl_file_path') and self.character.stl_file_path and os.path.exists(self.character.stl_file_path):
                self.load_model(self.character.stl_file_path)
                if self.character.camera_position:
                    self.camera.position.x = self.character.camera_position[0]
                    self.camera.position.y = self.character.camera_position[1]
                    self.camera.position.z = self.character.camera_position[2]
                if hasattr(self.character, 'object_rotation') and self.character.object_rotation and self.loaded_obj:
                    self.loaded_obj.rotation.x = self.character.object_rotation[0]
                    self.loaded_obj.rotation.y = self.character.object_rotation[1]
                    self.loaded_obj.rotation.z = self.character.object_rotation[2]
                if hasattr(self.character, 'light_intensity') and 'brightness_slider' in self.ids:
                    self.ids.brightness_slider.value = self.character.light_intensity
                if hasattr(self.character, 'light_position') and self.character.light_position:
                    if 'light_x_slider' in self.ids:
                        self.ids.light_x_slider.value = self.character.light_position[0]
                    if 'light_y_slider' in self.ids:
                        self.ids.light_y_slider.value = self.character.light_position[1]
                    if 'light_z_slider' in self.ids:
                        self.ids.light_z_slider.value = self.character.light_position[2]
                self.camera.look_at([0,0,0])

    def adjust_ability(self, ability, amount, instance):
        current_score = int(self.ability_scores_labels[ability].text)
        new_score = max(1, min(20, current_score + amount))
        self.ability_scores_labels[ability].text = str(new_score)

    def save_character(self, instance):
        if not self.character:
            return

        self.character.name = self.inputs["Name"].text.strip()
        self.character.race = self.inputs["Rasse"].text
        self.character.char_class = self.inputs["Klasse"].text
        self.character.alignment = self.inputs["Gesinnung"].text
        self.character.background = self.inputs["Hintergrund"].text
        self.character.personality_traits = self.inputs["Persönliche Merkmale"].text
        self.character.ideals = self.inputs["Ideale"].text
        self.character.bonds = self.inputs["Bindungen"].text
        self.character.flaws = self.inputs["Makel"].text

        for ability, label in self.ability_scores_labels.items():
            self.character.base_abilities[ability] = int(label.text)

        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            self.character.stl_file_path = self.stl_path
            if self.camera:
                self.character.camera_position = (self.camera.position.x, self.camera.position.y, self.camera.position.z)
            if self.loaded_obj:
                self.character.object_rotation = (self.loaded_obj.rotation.x, self.loaded_obj.rotation.y, self.loaded_obj.rotation.z)
            if self.light:
                self.character.light_intensity = self.light.intensity
                if 'light_x_slider' in self.ids:
                    self.character.light_position = (
                        self.ids.light_x_slider.value,
                        self.ids.light_y_slider.value,
                        self.ids.light_z_slider.value
                    )
        else:
            self.character.stl_file_path = None
            self.character.camera_position = None
            self.character.object_rotation = None
            self.character.light_intensity = 0.5
            self.character.light_position = (0, 0, 10)

        self.character.initialize_character()

        filename = f"{self.character.name.replace(' ', '_').lower()}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter '{self.character.name}' wurde erfolgreich aktualisiert.")
            self.manager.current = 'main'
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern des Charakters: {e}")

    def show_popup(self, title, message):
        Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()

    def on_leave(self, *args):
        Clock.unschedule(self._update_scene)

    def _update_scene(self, dt):
        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            # Recreate the light every frame to ensure slider value is used
            if 'brightness_slider' in self.ids:
                self.light = Light(renderer=self.renderer, intensity=self.ids.brightness_slider.value)
                self.light.pos_x = self.ids.light_x_slider.value
                self.light.pos_y = self.ids.light_y_slider.value
                self.light.pos_z = self.ids.light_z_slider.value
            self.renderer.render(self.scene, self.camera)

    def on_touch_down(self, touch):
        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            if 'stl_viewer_placeholder' in self.ids and self.ids.stl_viewer_placeholder.collide_point(*touch.pos):
                if touch.is_mouse_scrolling:
                    if touch.button == 'scrollup':
                        self.camera.position.z -= 1
                    elif touch.button == 'scrolldown':
                        self.camera.position.z += 1
                    return True

                touch.grab(self)
                self.touches.append(touch)
                self.touch_mode = touch.button
                return True
        return super(CharacterEditor, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            if touch.grab_current is self and self.loaded_obj:
                if len(self.touches) == 1:
                    if self.touch_mode == 'left':
                        self.loaded_obj.rotation.y += touch.dx
                        self.loaded_obj.rotation.x += touch.dy
                    elif self.touch_mode == 'right':
                        self.camera.position.x -= touch.dx * 0.1
                        self.camera.position.y -= touch.dy * 0.1
                elif len(self.touches) == 2:
                    t1, t2 = self.touches
                    dist = t1.distance(t2)
                    if self.last_touch_distance != 0:
                        zoom_amount = (dist - self.last_touch_distance) * 0.1
                        self.camera.position.z -= zoom_amount
                    self.last_touch_distance = dist
                return True
        return super(CharacterEditor, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        settings = load_settings()
        if settings.get('stl_viewer_enabled', True):
            if touch.grab_current is self:
                touch.ungrab(self)
                self.touches.remove(touch)
                if len(self.touches) == 0:
                    self.touch_mode = None
                if len(self.touches) < 2:
                    self.last_touch_distance = 0
                return True
        return super(CharacterEditor, self).on_touch_up(touch)

    def show_file_chooser(self):
        content = BoxLayout(orientation="vertical")
        file_chooser = FileChooserListView(filters=["*.stl"])
        content.add_widget(file_chooser)

        btn_box = BoxLayout(size_hint_y=None, height=44)
        load_button = Button(text="Laden")
        cancel_button = Button(text="Abbrechen")
        btn_box.add_widget(load_button)
        btn_box.add_widget(cancel_button)
        content.add_widget(btn_box)

        popup = Popup(title="Wähle eine STL Datei", content=content, size_hint=(0.9, 0.9))

        def load_selected_model(instance):
            if file_chooser.selection:
                self.load_model(file_chooser.selection[0])
                popup.dismiss()

        load_button.bind(on_press=load_selected_model)
        cancel_button.bind(on_press=popup.dismiss)
        popup.open()

    def load_model(self, path):
        self.stl_path = path

        self.scene = Scene()
        self.renderer.scene = self.scene

        # Light is now created/updated in the _update_scene loop

        loader = STLLoader()
        self.loaded_obj = loader.load(self.stl_path)
        self.scene.add(self.loaded_obj)

        self.camera.position.x = 0
        self.camera.position.y = 0
        self.camera.position.z = 30
        self.camera.look_at([0,0,0])

        placeholder = self.ids.stl_viewer_placeholder
        if not self.renderer.parent:
            placeholder.add_widget(self.renderer)
