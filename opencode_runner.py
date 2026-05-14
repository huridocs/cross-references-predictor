import subprocess
from pathlib import Path

work_dir = Path(__file__).parent

files_to_attach = ["main.py", "models.py", "utils.py"]

cmd = [
    "opencode",
    "run",
    "--agent",
    "build",
    "--file",
    ",".join(files_to_attach),
    "Refactor @main.py using the logic in @utils.py following our AGENTS.md rules",
]

print(f"--- Starting OpenCode Refactor in {work_dir} ---")

try:
    subprocess.run(
        cmd,
        cwd=work_dir,
        # No capture_output here: this allows the AI to ask you questions!
    )
    print("\n--- Refactor Task Completed ---")
except subprocess.CalledProcessError as e:
    print(f"\n--- Error during execution: {e} ---")
except KeyboardInterrupt:
    print("\n--- Script stopped by user ---")
