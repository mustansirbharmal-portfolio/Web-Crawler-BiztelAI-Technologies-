import os
import subprocess
import sys

# Command to run Gunicorn with the FastAPIWorker
cmd = [
    "gunicorn",
    "wsgi:app",
    "--bind", "0.0.0.0:5000",
    "--worker-class", "gunicorn_app.FastAPIWorker",
    "--workers", "1",
    "--reload"
]

# Execute the command
try:
    subprocess.run(cmd, check=True)
except KeyboardInterrupt:
    # Handle Ctrl+C gracefully
    sys.exit(0)
except subprocess.CalledProcessError as e:
    print(f"Error running Gunicorn: {e}", file=sys.stderr)
    sys.exit(e.returncode)