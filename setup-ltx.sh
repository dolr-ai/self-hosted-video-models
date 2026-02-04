#!/bin/bash
# Complete setup script for ComfyUI with LTX-2 on Vast.ai
# Works for both on-demand instances and as an onstart script
# Usage: bash setup-ltx.sh

set -e

echo "========================================="
echo "ComfyUI LTX-2 Setup Script"
echo "========================================="

# Configuration
COMFYUI_DIR="/workspace/ComfyUI"
MODEL_PATH="${COMFYUI_DIR}/models/checkpoints/ltx-2-19b-distilled.safetensors"
CUSTOM_NODE_SRC="/opt/custom_nodes/ComfyUI-LTXVideo"
CUSTOM_NODE_DEST="${COMFYUI_DIR}/custom_nodes/ComfyUI-LTXVideo"
MODEL_URL="https://huggingface.co/Lightricks/LTX-2/resolve/main/ltx-2-19b-distilled.safetensors"

# Check if ComfyUI exists
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "❌ ComfyUI not found at $COMFYUI_DIR"
    echo "📦 Cloning ComfyUI..."
    cd /workspace
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
    echo "📦 Installing dependencies..."
    pip install -q -r requirements.txt
    echo "✅ ComfyUI installed"
else
    echo "✅ ComfyUI found at $COMFYUI_DIR"
fi

# Check and install LTX custom nodes
NEEDS_RESTART=false
if [ ! -d "$CUSTOM_NODE_DEST" ]; then
    echo "❌ LTX custom nodes not found"
    if [ -d "$CUSTOM_NODE_SRC" ]; then
        echo "📦 Copying LTX custom nodes from image..."
        mkdir -p "${COMFYUI_DIR}/custom_nodes"
        cp -r "$CUSTOM_NODE_SRC" "$CUSTOM_NODE_DEST"
        echo "✅ LTX custom nodes installed"
        NEEDS_RESTART=true
    else
        echo "⚠️  Warning: LTX custom nodes not found in image at $CUSTOM_NODE_SRC"
        echo "📦 Cloning LTX custom nodes from GitHub..."
        mkdir -p "${COMFYUI_DIR}/custom_nodes"
        cd "${COMFYUI_DIR}/custom_nodes"
        git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
        cd ComfyUI-LTXVideo
        pip install -q -r requirements.txt
        echo "✅ LTX custom nodes installed from GitHub"
        NEEDS_RESTART=true
    fi
else
    echo "✅ LTX custom nodes found"
fi

# Check and download model
if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ LTX-2 model not found"
    echo "📥 Downloading LTX-2 model (40GB, ~10-15 min)..."
    echo "    This will be saved to the volume and only needs to be done once"

    mkdir -p "${COMFYUI_DIR}/models/checkpoints"
    cd "${COMFYUI_DIR}/models/checkpoints"

    # Try aria2c first (faster)
    if command -v aria2c &> /dev/null; then
        aria2c --max-connection-per-server=16 --split=16 --min-split-size=1M \
            --continue=true --max-tries=5 --retry-wait=3 \
            --summary-interval=10 --console-log-level=warn \
            -o ltx-2-19b-distilled.safetensors "$MODEL_URL"
    else
        # Fallback to wget
        wget -c -O ltx-2-19b-distilled.safetensors "$MODEL_URL"
    fi

    if [ -f "$MODEL_PATH" ]; then
        echo "✅ Model downloaded successfully ($(du -h "$MODEL_PATH" | cut -f1))"
    else
        echo "❌ Model download failed"
        exit 1
    fi
else
    echo "✅ LTX-2 model found ($(du -h "$MODEL_PATH" | cut -f1))"
fi

# Check and download Gemma text encoder (required for LTX-2)
GEMMA_DIR="${COMFYUI_DIR}/models/text_encoders/gemma-3-12b-it-qat-q4_0-unquantized"
GEMMA_FILE="${GEMMA_DIR}/model-00001-of-00005.safetensors"

# Get HF token from environment or cached file
HF_TOKEN="${HF_TOKEN:-$(cat ~/.cache/huggingface/token 2>/dev/null || echo '')}"

if [ ! -f "$GEMMA_FILE" ]; then
    echo "❌ Gemma text encoder not found"

    if [ -z "$HF_TOKEN" ]; then
        echo "⚠️  Warning: No HuggingFace token found. Gemma is a gated model."
        echo "   Set HF_TOKEN env var or run: huggingface-cli login"
    fi

    echo "📥 Downloading Gemma 3 12B text encoder (~23GB)..."

    mkdir -p "$GEMMA_DIR"
    cd "$GEMMA_DIR"

    # Download all 5 shards
    BASE_URL="https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-unquantized/resolve/main"

    for i in 1 2 3 4 5; do
        SHARD="model-0000${i}-of-00005.safetensors"
        if [ ! -f "$SHARD" ]; then
            echo "📥 Downloading shard ${i}/5..."
            if command -v aria2c &> /dev/null; then
                ARIA_OPTS="--max-connection-per-server=16 --split=16 --min-split-size=1M --continue=true --max-tries=5 --retry-wait=3 --console-log-level=warn"
                if [ -n "$HF_TOKEN" ]; then
                    aria2c $ARIA_OPTS --header="Authorization: Bearer $HF_TOKEN" -o "$SHARD" "${BASE_URL}/${SHARD}"
                else
                    aria2c $ARIA_OPTS -o "$SHARD" "${BASE_URL}/${SHARD}"
                fi
            else
                if [ -n "$HF_TOKEN" ]; then
                    wget -c --header="Authorization: Bearer $HF_TOKEN" -O "$SHARD" "${BASE_URL}/${SHARD}"
                else
                    wget -c -O "$SHARD" "${BASE_URL}/${SHARD}"
                fi
            fi
        else
            echo "✅ Shard ${i}/5 already exists"
        fi
    done

    # Also download config files (all required for LTXVGemmaCLIPModelLoader)
    CONFIG_FILES="config.json tokenizer.json tokenizer_config.json tokenizer.model special_tokens_map.json generation_config.json preprocessor_config.json model.safetensors.index.json added_tokens.json"
    for config_file in $CONFIG_FILES; do
        if [ ! -f "$config_file" ]; then
            echo "  Downloading $config_file..."
            if [ -n "$HF_TOKEN" ]; then
                wget -q --header="Authorization: Bearer $HF_TOKEN" -O "$config_file" "${BASE_URL}/${config_file}" 2>/dev/null || true
            else
                wget -q -O "$config_file" "${BASE_URL}/${config_file}" 2>/dev/null || true
            fi
        fi
    done

    echo "✅ Gemma text encoder downloaded"
else
    echo "✅ Gemma text encoder found"
fi

# Check if ComfyUI is running via supervisor
if command -v supervisorctl &> /dev/null; then
    echo ""

    # Check if ComfyUI is currently running
    COMFYUI_RUNNING=false
    if supervisorctl status comfyui 2>/dev/null | grep -q RUNNING; then
        COMFYUI_RUNNING=true
    fi

    # Restart if needed or if not running
    if [ "$NEEDS_RESTART" = true ] || [ "$COMFYUI_RUNNING" = false ]; then
        if [ "$NEEDS_RESTART" = true ]; then
            echo "🔄 Restarting ComfyUI to load new custom nodes..."
        else
            echo "🚀 Starting ComfyUI..."
        fi

        supervisorctl restart comfyui 2>/dev/null || supervisorctl start comfyui 2>/dev/null || true
        sleep 5

        # Verify ComfyUI started successfully
        if supervisorctl status comfyui 2>/dev/null | grep -q RUNNING; then
            echo "✅ ComfyUI is running"

            # Check logs for LTX nodes
            sleep 2
            if tail -30 /var/log/portal/comfyui.log 2>/dev/null | grep -q "ComfyUI-LTXVideo"; then
                echo "✅ LTX custom nodes loaded successfully"
            fi
        else
            echo "❌ Failed to start ComfyUI"
            echo "Check logs: tail -50 /var/log/portal/comfyui.log"
            exit 1
        fi
    else
        echo "✅ ComfyUI is already running (no restart needed)"
    fi

    # Check API wrapper
    if supervisorctl status comfyui-api-wrapper 2>/dev/null | grep -q RUNNING; then
        echo "✅ ComfyUI API wrapper is running on port 8288"
    else
        echo "⚠️  API wrapper not running, starting..."
        supervisorctl start comfyui-api-wrapper 2>/dev/null || true
    fi
else
    echo ""
    echo "⚠️  Supervisor not found. To start ComfyUI manually:"
    echo "    cd $COMFYUI_DIR"
    echo "    python main.py --listen 0.0.0.0 --port 8188"
fi

# Set up video cleanup script
echo ""
echo "📦 Setting up video cleanup script..."

# Download cleanup script
cat > /tmp/video-cleanup.sh << 'CLEANUP_SCRIPT'
#!/bin/bash
# Video TTL cleanup script for ComfyUI LTX-2 outputs

TTL_MINUTES=${VIDEO_TTL_MINUTES:-10}
CHECK_INTERVAL=${CLEANUP_CHECK_INTERVAL:-300}
OUTPUT_DIR="${COMFYUI_OUTPUT_DIR:-/workspace/ComfyUI/output}"
LOG_FILE="/var/log/video-cleanup.log"

FILE_PATTERNS=("*.mp4" "*.avi" "*.mov" "*.webm" "*.mkv")

echo "$(date): Video cleanup started (TTL: ${TTL_MINUTES}m)" >> "$LOG_FILE"

cleanup_videos() {
    local deleted_count=0

    for pattern in "${FILE_PATTERNS[@]}"; do
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                rm -f "$file" && ((deleted_count++))
            fi
        done < <(find "$OUTPUT_DIR" -name "$pattern" -type f -mmin +$TTL_MINUTES -print0 2>/dev/null)
    done

    [ $deleted_count -gt 0 ] && echo "$(date): Deleted $deleted_count videos" >> "$LOG_FILE"
}

while true; do
    [ -d "$OUTPUT_DIR" ] && cleanup_videos
    sleep $CHECK_INTERVAL
done
CLEANUP_SCRIPT

chmod +x /tmp/video-cleanup.sh

# Check if cleanup is already running
if pgrep -f "video-cleanup.sh" > /dev/null; then
    echo "✅ Video cleanup script already running"
else
    echo "🚀 Starting video cleanup script in background..."
    nohup /tmp/video-cleanup.sh > /dev/null 2>&1 &
    echo "✅ Video cleanup started (PID: $!)"
    echo "   - TTL: ${VIDEO_TTL_MINUTES:-10} minutes"
    echo "   - Check interval: ${CLEANUP_CHECK_INTERVAL:-5} minutes"
fi

echo ""
echo "========================================="
echo "✨ Setup Complete!"
echo "========================================="
echo "ComfyUI Location: $COMFYUI_DIR"
echo "Model Location: $MODEL_PATH"
echo "Custom Nodes: $CUSTOM_NODE_DEST"
echo "Video Cleanup: /tmp/video-cleanup.sh (TTL: ${VIDEO_TTL_MINUTES:-10}m)"
echo ""
echo "Access ComfyUI:"
echo "  - Web UI: http://localhost:8188 (via SSH tunnel)"
echo "  - API: http://localhost:8288 (if API wrapper is running)"
echo ""
echo "Next steps:"
echo "  1. Set up Cloudflare tunnel for public API access"
echo "  2. Convert instance to Reserved for 50% discount"
echo "  3. Adjust VIDEO_TTL_MINUTES env var to change cleanup time"
echo "========================================="
