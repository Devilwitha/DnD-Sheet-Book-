from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty

class ChangelogScreen(Screen):
    """Screen to display the changelog."""
    changelog_text = StringProperty('')

    def on_enter(self, *args):
        self.load_changelog()

    def load_changelog(self):
        try:
            with open('changelog.txt', 'r', encoding='utf-8') as f:
                self.changelog_text = f.read()
        except FileNotFoundError:
            self.changelog_text = "changelog.txt nicht gefunden."
        except Exception as e:
            self.changelog_text = f"Fehler beim Laden des Changelogs:\n{e}"
