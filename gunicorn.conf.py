import os
import multiprocessing

# The ip address and port to bind the server to
# Render provides the PORT variable automatically
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# The number of worker processes for handling requests.
# Standard formula for web workers is (2 * CPU cores) + 1.
workers = 2

# Timeout for workers before restarting (in seconds)
timeout = 120

# Log configurations to help monitor your app on Render
accesslog = "-"  # Redirects access logs straight to Render dashboard stdout
errorlog = "-"   # Redirects error logs straight to Render dashboard stderr
loglevel = "info"