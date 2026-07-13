#!/bin/bash
export USE_IN_MEMORY_FALLBACK=True
export API_HOST=0.0.0.0
export API_PORT=8000
cd /home/runner/workspace
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
