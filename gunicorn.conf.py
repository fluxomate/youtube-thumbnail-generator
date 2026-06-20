# gunicorn settings (auto-loaded from the working directory).
# ONE worker is required: the app keeps job state in-process, so multiple
# workers would split it. Threads give concurrency for polling/uploads.
workers = 1
threads = 8
timeout = 300
