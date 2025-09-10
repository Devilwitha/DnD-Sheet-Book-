from kivy.uix.screenmanager import Screen, FadeTransition
from kivy.animation import Animation
from kivy.clock import Clock

class SplashScreen(Screen):
    """A splash screen that appears at startup."""

    def on_enter(self, *args):
        """Called when the screen is entered. Starts the animation."""
        self.start_pulsating_animation()

    def start_pulsating_animation(self):
        """Creates and starts a pulsating animation on the label."""
        label = self.ids.pulsating_label
        anim = Animation(font_size=35, duration=1.5) + Animation(font_size=30, duration=1.5)
        anim.repeat = True
        anim.start(label)

    def on_touch_down(self, touch):
        """Called when the screen is touched. Switches to the main menu."""
        # Stop the animation
        Animation.cancel_all(self.ids.pulsating_label)

        # Switch to the main menu
        self.manager.transition = FadeTransition(duration=0.5)
        self.manager.current = 'main'
        return super().on_touch_down(touch)
