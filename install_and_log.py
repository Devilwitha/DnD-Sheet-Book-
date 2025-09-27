import os
import subprocess
import time
import sys

# --- Configuration ---
PLATFORM_TOOLS_DIR = "platform-tools"
ADB_EXECUTABLE = "adb.exe" if sys.platform == "win32" else "adb"
ADB_PATH = os.path.join(PLATFORM_TOOLS_DIR, ADB_EXECUTABLE)
LOG_FILE = "android_log.txt"
# Find the APK file automatically in the root directory
APK_DIR = "."
APK_FILE = None

def find_apk():
    """Finds the first .apk file in the current directory."""
    for file in os.listdir(APK_DIR):
        if file.endswith(".apk"):
            return os.path.join(APK_DIR, file)
    return None

def main():
    """
    Main function to run the installation and logging process.
    """
    global APK_FILE
    APK_FILE = find_apk()

    # 1. Check for prerequisites
    if not os.path.exists(ADB_PATH):
        print(f"ERROR: '{ADB_PATH}' not found.")
        print("Please make sure the 'platform-tools' directory with adb is in the root of the project.")
        sys.exit(1)

    if not APK_FILE:
        print(f"ERROR: No .apk file found in the '{APK_DIR}' directory.")
        print("Please make sure you have built the app and the .apk is in the root directory.")
        sys.exit(1)

    print(f"Found APK: {APK_FILE}")
    print(f"Using ADB: {ADB_PATH}")
    print(f"Logging to: {LOG_FILE}")

    logcat_process = None
    try:
        # 2. Start logcat
        print("\nStarting logcat...")
        with open(LOG_FILE, 'w') as logfile:
            logcat_process = subprocess.Popen(
                [ADB_PATH, "logcat", "-c"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logcat_process.wait() # Clear old logs

            logcat_process = subprocess.Popen(
                [ADB_PATH, "logcat", "*:S", "python:D"],
                stdout=logfile,
                stderr=logfile
            )

        print(f"Logcat started, PID: {logcat_process.pid}. Waiting a moment...")
        time.sleep(3) # Give logcat a moment to start up

        # 3. Install the APK
        print(f"\nInstalling '{APK_FILE}'...")
        install_process = subprocess.run(
            [ADB_PATH, "install", "-r", APK_FILE],
            capture_output=True,
            text=True
        )

        if install_process.returncode == 0:
            print("Installation successful!")
            print(install_process.stdout)
        else:
            print("--- Installation Failed ---")
            print(install_process.stdout)
            print(install_process.stderr)
            print("---------------------------")
            print(f"Please check the log file '{LOG_FILE}' for more details.")
            return # Exit if installation fails

        print("\nProcess finished. You can now run the app on your device.")
        print(f"Logs are being saved to '{LOG_FILE}'. Press Ctrl+C to stop logging.")

        # Keep the script running to continue logging
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Stopping logcat.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if logcat_process:
            print("Terminating logcat process...")
            logcat_process.terminate()
            logcat_process.wait()
            print("Logcat stopped.")

if __name__ == "__main__":
    main()
