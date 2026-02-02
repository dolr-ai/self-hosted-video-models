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
echo "Setting up LTX-2 custom nodes..."
mkdir -p /workspace/ComfyUI/custom_nodes
if [ ! -d "/workspace/ComfyUI/custom_nodes/ComfyUI-LTXVideo" ]; then
  cp -r /opt/custom_nodes/ComfyUI-LTXVideo /workspace/ComfyUI/custom_nodes/
  echo "LTX-2 custom nodes copied from image (dependencies already installed)"
else
  echo "LTX-2 custom nodes already present"
fi

# Download LTX-2 model with aria2c (aria2c is pre-installed in custom image)
echo "Checking for LTX-2 model..."
mkdir -p /workspace/ComfyUI/models/checkpoints
cd /workspace/ComfyUI/models/checkpoints

if [ ! -f "ltx-2-19b-dev.safetensors" ]; then
  echo "Downloading LTX-2 model..."
  aria2c --max-connection-per-server=16 --split=16 --min-split-size=1M --continue=true --max-tries=5 --retry-wait=3 --timeout=60 --connect-timeout=30 --summary-interval=10 --console-log-level=warn -o ltx-2-19b-dev.safetensors https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev.safetensors

  # Fallback to wget if aria2c fails
  if [ $? -ne 0 ]; then
    echo "aria2c failed, falling back to wget..."
    wget -c -O ltx-2-19b-dev.safetensors https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-dev.safetensors
  fi
else
  echo "Model already exists, skipping download"
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

# Start pyworker (serverless handler)
cd /workspace
wget -O - "https://raw.githubusercontent.com/vast-ai/pyworker/main/start_server.sh" | bash
