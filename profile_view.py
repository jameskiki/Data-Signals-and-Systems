"""
profile_view.py

Launches RunSnakeRun to visualize the profile_output.prof file.
"""
import os
import subprocess
import sys

PROFILE_FILE = "profile_output.prof"

# Path to the venv Scripts directory
VENV_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts")
RUNSNAKE_EXE = os.path.join(VENV_SCRIPTS, "runsnake.exe")

if not os.path.isfile(RUNSNAKE_EXE):
    print(f"RunSnakeRun executable not found: {RUNSNAKE_EXE}")
    print("Make sure RunSnakeRun is installed in your virtual environment.")
    sys.exit(1)

if not os.path.isfile(PROFILE_FILE):
    print(f"Profile file not found: {PROFILE_FILE}")
    sys.exit(1)

try:
    subprocess.run([RUNSNAKE_EXE, PROFILE_FILE], check=True)
except subprocess.CalledProcessError as e:
    print(f"Failed to launch RunSnakeRun: {e}")
    sys.exit(e.returncode)
