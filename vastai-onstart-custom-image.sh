#!/bin/bash
# Simplified onstart script for custom image with LTX-2 dependencies pre-installed
# This script only downloads the model - dependencies are already in the image

export SERVERLESS=true
export BACKEND=comfyui-json
export COMFYUI_API_BASE="http://localhost:18188"
export MODEL_LOG=/var/log/portal/comfyui.log

# Start ComfyUI in background
entrypoint.sh &

sleep 10

# Copy pre-installed LTX-2 custom nodes from image to workspace
mkdir -p /workspace/ComfyUI/custom_nodes && cp -rn /opt/custom_nodes/ComfyUI-LTXVideo /workspace/ComfyUI/custom_nodes/ 2>/dev/null || true

# Copy pre-downloaded LTX-2 model from image to workspace
echo "Copying LTX-2 model from image..."
mkdir -p /workspace/ComfyUI/models/checkpoints
if [ ! -f "/workspace/ComfyUI/models/checkpoints/ltx-2-19b-dev.safetensors" ]; then
  if [ -f "/opt/models/ltx-2-19b-dev.safetensors" ]; then
    cp /opt/models/ltx-2-19b-dev.safetensors /workspace/ComfyUI/models/checkpoints/
    echo "Model copied from image (instant startup)"
  else
    echo "Model not found in image, downloading..."
    cd /workspace/ComfyUI/models/checkpoints
    aria2c --max-connection-per-server=16 --split=16 --min-split-size=1M --continue=true --max-tries=5 --retry-wait=3 --timeout=60 --connect-timeout=30 --summary-interval=10 --console-log-level=warn -o ltx-2-19b-dev.safetensors https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev.safetensors
  fi
else
  echo "Model already exists in workspace"
fi

# Periodic cleanup script (runs in background)
cat > /tmp/cleanup.sh << 'EOF'
#!/bin/bash
while true; do
  # Delete videos older than 10 minutes
  find /workspace/ComfyUI/output -name "*.mp4" -mmin +10 -delete 2>/dev/null
  find /workspace/ComfyUI/temp -name "*.mp4" -mmin +10 -delete 2>/dev/null

  # Sleep for 5 minutes, then check again
  sleep 300
done
EOF

chmod +x /tmp/cleanup.sh
/tmp/cleanup.sh &

# Signal provisioning complete by removing the marker file BEFORE starting pyworker
rm -f /.provisioning

# Start pyworker (serverless handler)
cd /workspace
wget -O - "https://raw.githubusercontent.com/vast-ai/pyworker/main/start_server.sh" | bash
