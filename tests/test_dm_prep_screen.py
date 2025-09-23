import unittest
import os
import json
from unittest.mock import MagicMock, patch

# Since the app is not running, we need to mock Kivy's App.get_running_app()
from kivy.base import EventLoop
EventLoop.ensure_window()
from kivy.app import App
App.get_running_app = MagicMock()

from ui.dm_prep_screen import DMPrepScreen
from core.enemy import Enemy

class TestDMPrepScreen(unittest.TestCase):

    def setUp(self):
        self.screen = DMPrepScreen()
        self.saves_dir = "enemies"
        self.test_file = os.path.join(self.saves_dir, "my_enemies.enemies")

        # Clean up any old test files
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        # Clean up test files after tests
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_save_and_load_enemy_list(self):
        # 1. Add a dummy enemy to the list
        test_enemy = Enemy(name="Goblin", hp=10, armor_class=12, attacks=[])
        self.screen.enemy_list.append(test_enemy)

        # 2. Save the list
        self.screen.save_enemy_list()

        # 3. Check if the file was created in the 'saves' directory
        self.assertTrue(os.path.exists(self.test_file))

        # 4. Check the content of the file
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['name'], "Goblin")

        # 5. Clear the enemy list and load from the file
        self.screen.enemy_list = []
        self.screen.load_enemy_list()

        # 6. Check if the enemy is loaded correctly
        self.assertEqual(len(self.screen.enemy_list), 1)
        self.assertEqual(self.screen.enemy_list[0].name, "Goblin")

if __name__ == '__main__':
    unittest.main()
