#!/bin/bash
export API_BASE=http://localhost:8000
export USE_IN_MEMORY_FALLBACK=True
cd /home/runner/workspace
exec streamlit run frontend/app.py \
  --server.port 5000 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.allowRunOnSave true
