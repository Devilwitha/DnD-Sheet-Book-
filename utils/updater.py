import subprocess
import os
import sys
import time

def run_update(branch='main'):
    """
    This script is called by main.py to perform an update.
    It waits for the main app to close, then pulls the latest code,
    installs dependencies, and restarts the main app.
    """
    # Give the main app a moment to close to release file locks
    time.sleep(2)

    try:
        # Step 1: Force Git update
        print("Fetching updates from remote...")
        # Use --all to fetch all remote branches
        subprocess.run(["git", "fetch", "--all"], check=True, capture_output=True, text=True)
        
        print(f"Forcing update by resetting local branch to origin/{branch}...")
        # Reset the local branch to match the remote, discarding local changes
        subprocess.run(["git", "reset", "--hard", f"origin/{branch}"], check=True, capture_output=True, text=True)

        # Step 2: Install Dependencies
        print("Installing/updating Python dependencies...")
        # Use sys.executable to ensure we're using the right pip in the right environment
        pip_command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        subprocess.run(pip_command, check=True, capture_output=True, text=True)
        
        # Ensure the start script is executable, in case it was overwritten by the update
        start_script_path = "start_dnd.sh"
        if os.path.exists(start_script_path):
            print("Setting execute permissions for start_dnd.sh...")
            os.chmod(start_script_path, os.stat(start_script_path).st_mode | 0o111)

        print("Update complete.")

    except subprocess.CalledProcessError as e:
        # If something goes wrong, print the error.
        # A more advanced version could write this to a log file or show a GUI error.
        print("--- UPDATE FAILED ---")
        print(f"Error during command: {' '.join(e.cmd)}")
        print(f"Stderr: {e.stderr}")
        print("---------------------")
        # Pause for a few seconds so the user can see the error in the console
        time.sleep(10)
        
    finally:
        # Step 3: Restart the main application
        print("Restarting the main application...")
        # Use Popen to launch the main script in a new, detached process
        subprocess.Popen([sys.executable, "main.py"])

if __name__ == "__main__":
    branch_arg = 'main'
    if len(sys.argv) > 1:
        branch_arg = sys.argv[1]
    run_update(branch=branch_arg)
