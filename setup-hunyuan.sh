#!/bin/bash
# Complete setup script for ComfyUI with HunyuanVideo 1.5 + Hunyuan Foley on Vast.ai
# Installs 720p T2V, 720p I2V, 1080p SR, and Foley audio generation
# Usage: bash setup-hunyuan.sh

set -e

# Resolve script directory before any cd commands
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "ComfyUI HunyuanVideo 1.5 + Foley Setup"
echo "========================================="

# Configuration
COMFYUI_DIR="/workspace/ComfyUI"
HF_BASE="https://huggingface.co/Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files"
FOLEY_HF_BASE="https://huggingface.co/phazei/HunyuanVideo-Foley/resolve/main"

# Check if ComfyUI exists
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "ComfyUI not found at $COMFYUI_DIR"
    echo "Cloning ComfyUI..."
    cd /workspace
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
    pip install -q -r requirements.txt
    echo "ComfyUI installed"
else
    echo "ComfyUI found at $COMFYUI_DIR"
fi

NEEDS_RESTART=false

# Install Hunyuan Foley custom node
FOLEY_NODE_DIR="${COMFYUI_DIR}/custom_nodes/ComfyUI-HunyuanVideo-Foley"
if [ ! -d "$FOLEY_NODE_DIR" ]; then
    echo "Installing ComfyUI-HunyuanVideo-Foley..."
    cd "${COMFYUI_DIR}/custom_nodes"
    git clone https://github.com/phazei/ComfyUI-HunyuanVideo-Foley.git
    cd ComfyUI-HunyuanVideo-Foley
    if [ -f "/venv/main/bin/pip" ]; then
        /venv/main/bin/pip install -q -r requirements.txt 2>/dev/null || true
    else
        pip install -q -r requirements.txt 2>/dev/null || true
    fi
    echo "ComfyUI-HunyuanVideo-Foley installed"
    NEEDS_RESTART=true
else
    echo "ComfyUI-HunyuanVideo-Foley found"
fi

# Install VideoHelperSuite (required for Foley workflow video loading/combining)
VHS_NODE_DIR="${COMFYUI_DIR}/custom_nodes/ComfyUI-VideoHelperSuite"
if [ ! -d "$VHS_NODE_DIR" ]; then
    echo "Installing ComfyUI-VideoHelperSuite..."
    cd "${COMFYUI_DIR}/custom_nodes"
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
    cd ComfyUI-VideoHelperSuite
    if [ -f "/venv/main/bin/pip" ]; then
        /venv/main/bin/pip install -q -r requirements.txt 2>/dev/null || true
    else
        pip install -q -r requirements.txt 2>/dev/null || true
    fi
    echo "ComfyUI-VideoHelperSuite installed"
    NEEDS_RESTART=true
else
    echo "ComfyUI-VideoHelperSuite found"
fi

# Install SageAttention (may already exist from LTX setup)
echo "Checking SageAttention..."
if ! python3 -c "import sageattention" 2>/dev/null; then
    echo "Installing SageAttention..."
    if [ -f "/venv/main/bin/pip" ]; then
        /venv/main/bin/pip install sageattention --no-build-isolation 2>/dev/null || true
    else
        pip install sageattention --no-build-isolation 2>/dev/null || true
    fi
    echo "SageAttention installed"
else
    echo "SageAttention found"
fi

# Helper function for downloading models
download_model() {
    local url="$1"
    local dest_dir="$2"
    local filename="$3"
    local filepath="${dest_dir}/${filename}"

    if [ -f "$filepath" ]; then
        echo "  Found: $filename ($(du -h "$filepath" | cut -f1))"
        return 0
    fi

    echo "  Downloading: $filename..."
    mkdir -p "$dest_dir"

    if command -v aria2c &> /dev/null; then
        aria2c --max-connection-per-server=16 --split=16 --min-split-size=1M \
            --continue=true --max-tries=5 --retry-wait=3 \
            --summary-interval=10 --console-log-level=warn \
            -d "$dest_dir" -o "$filename" "$url"
    else
        wget -c -O "$filepath" "$url"
    fi

    if [ -f "$filepath" ]; then
        echo "  Downloaded: $filename ($(du -h "$filepath" | cut -f1))"
    else
        echo "  FAILED: $filename"
        return 1
    fi
}

# =========================================
# HunyuanVideo 1.5 Models
# =========================================
echo ""
echo "--- HunyuanVideo 1.5 Models ---"

# Text encoders (shared by T2V and I2V)
echo ""
echo "Text Encoders:"
download_model \
    "${HF_BASE}/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "${COMFYUI_DIR}/models/text_encoders" \
    "qwen_2.5_vl_7b_fp8_scaled.safetensors"

download_model \
    "${HF_BASE}/text_encoders/byt5_small_glyphxl_fp16.safetensors" \
    "${COMFYUI_DIR}/models/text_encoders" \
    "byt5_small_glyphxl_fp16.safetensors"

# CLIP Vision (needed for I2V and SR)
echo ""
echo "CLIP Vision:"
download_model \
    "https://huggingface.co/Comfy-Org/sigclip_vision_384/resolve/main/sigclip_vision_patch14_384.safetensors" \
    "${COMFYUI_DIR}/models/clip_vision" \
    "sigclip_vision_patch14_384.safetensors"

# VAE (shared)
echo ""
echo "VAE:"
download_model \
    "${HF_BASE}/vae/hunyuanvideo15_vae_fp16.safetensors" \
    "${COMFYUI_DIR}/models/vae" \
    "hunyuanvideo15_vae_fp16.safetensors"

# Diffusion models (large downloads)
echo ""
echo "Diffusion Models (this will take a while):"
download_model \
    "${HF_BASE}/diffusion_models/hunyuanvideo1.5_720p_t2v_fp16.safetensors" \
    "${COMFYUI_DIR}/models/diffusion_models" \
    "hunyuanvideo1.5_720p_t2v_fp16.safetensors"

download_model \
    "${HF_BASE}/diffusion_models/hunyuanvideo1.5_720p_i2v_fp16.safetensors" \
    "${COMFYUI_DIR}/models/diffusion_models" \
    "hunyuanvideo1.5_720p_i2v_fp16.safetensors"

download_model \
    "${HF_BASE}/diffusion_models/hunyuanvideo1.5_1080p_sr_distilled_fp16.safetensors" \
    "${COMFYUI_DIR}/models/diffusion_models" \
    "hunyuanvideo1.5_1080p_sr_distilled_fp16.safetensors"

# Latent upscaler (for 1080p SR)
echo ""
echo "Latent Upscaler:"
download_model \
    "${HF_BASE}/latent_upscale_models/hunyuanvideo15_latent_upsampler_1080p.safetensors" \
    "${COMFYUI_DIR}/models/latent_upscale_models" \
    "hunyuanvideo15_latent_upsampler_1080p.safetensors"

# =========================================
# Hunyuan Foley Models
# =========================================
echo ""
echo "--- Hunyuan Foley Models ---"

# Foley models directory
FOLEY_MODEL_DIR="${COMFYUI_DIR}/models/foley"
mkdir -p "$FOLEY_MODEL_DIR"

download_model \
    "${FOLEY_HF_BASE}/hunyuanvideo_foley_fp8_e4m3fn.safetensors" \
    "$FOLEY_MODEL_DIR" \
    "hunyuanvideo_foley_fp8_e4m3fn.safetensors"

download_model \
    "${FOLEY_HF_BASE}/synchformer_state_dict_fp16.safetensors" \
    "$FOLEY_MODEL_DIR" \
    "synchformer_state_dict_fp16.safetensors"

download_model \
    "${FOLEY_HF_BASE}/vae_128d_48k_fp16.safetensors" \
    "$FOLEY_MODEL_DIR" \
    "vae_128d_48k_fp16.safetensors"

# =========================================
# Copy Workflows
# =========================================
echo ""
echo "--- Workflows ---"

USER_WORKFLOWS="${COMFYUI_DIR}/user/default/workflows"
mkdir -p "$USER_WORKFLOWS"

WORKFLOW_DIR="${SCRIPT_DIR}/workflows"

for wf in HunyuanVideo15_720p_T2V.json HunyuanVideo15_720p_I2V.json HunyuanFoley_V2A.json HunyuanVideo15_T2V_Foley.json; do
    if [ -f "${WORKFLOW_DIR}/${wf}" ]; then
        cp "${WORKFLOW_DIR}/${wf}" "${USER_WORKFLOWS}/${wf}"
        echo "  Copied: $wf"
    else
        echo "  SKIP: $wf not found in ${WORKFLOW_DIR}"
    fi
done

# =========================================
# Torch Compile Cache
# =========================================
echo ""
echo "--- Optimizations ---"

TORCH_CACHE_DIR="/workspace/torch_cache"
if [ ! -d "$TORCH_CACHE_DIR" ]; then
    mkdir -p "$TORCH_CACHE_DIR"
fi
echo "Torch compile cache: $TORCH_CACHE_DIR"

# Configure ComfyUI startup
COMFYUI_SCRIPT="/opt/supervisor-scripts/comfyui.sh"
if [ -f "$COMFYUI_SCRIPT" ] && ! grep -q "TORCHINDUCTOR_CACHE_DIR" "$COMFYUI_SCRIPT" 2>/dev/null; then
    echo "Adding torch.compile optimizations..."
    sed -i '1a\
export TORCHINDUCTOR_CACHE_DIR=/workspace/torch_cache\
export TORCH_COMPILE_DEBUG=0\
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True' "$COMFYUI_SCRIPT" 2>/dev/null || true
    echo "Torch optimizations configured"
    NEEDS_RESTART=true
else
    echo "Torch optimizations already configured"
fi

# Add SageAttention flag
if [ -f "$COMFYUI_SCRIPT" ]; then
    PIP_BIN="/venv/main/bin/pip"
    [ ! -f "$PIP_BIN" ] && PIP_BIN="pip"
    if $PIP_BIN show sageattention &>/dev/null; then
        if ! grep -q "use-sage-attention" "$COMFYUI_SCRIPT" 2>/dev/null; then
            echo "Enabling SageAttention in ComfyUI startup..."
            sed -i '/^COMFYUI_ARGS=\${COMFYUI_ARGS/a COMFYUI_ARGS="${COMFYUI_ARGS} --use-sage-attention"' "$COMFYUI_SCRIPT" 2>/dev/null || true
            echo "SageAttention enabled"
            NEEDS_RESTART=true
        else
            echo "SageAttention already enabled"
        fi
    fi
fi

# =========================================
# Restart ComfyUI
# =========================================
if command -v supervisorctl &> /dev/null; then
    echo ""

    COMFYUI_RUNNING=false
    if supervisorctl status comfyui 2>/dev/null | grep -q RUNNING; then
        COMFYUI_RUNNING=true
    fi

    if [ "$NEEDS_RESTART" = true ] || [ "$COMFYUI_RUNNING" = false ]; then
        if [ "$NEEDS_RESTART" = true ]; then
            echo "Restarting ComfyUI to load new nodes..."
        else
            echo "Starting ComfyUI..."
        fi

        supervisorctl restart comfyui 2>/dev/null || supervisorctl start comfyui 2>/dev/null || true
        sleep 5

        if supervisorctl status comfyui 2>/dev/null | grep -q RUNNING; then
            echo "ComfyUI is running"
        else
            echo "Failed to start ComfyUI"
            echo "Check logs: tail -50 /var/log/portal/comfyui.log"
            exit 1
        fi
    else
        echo "ComfyUI is already running (no restart needed)"
    fi
else
    echo ""
    echo "Supervisor not found. Start ComfyUI manually:"
    echo "    cd $COMFYUI_DIR"
    echo "    python main.py --listen 0.0.0.0 --port 8188"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo "HunyuanVideo 1.5 Models: ${COMFYUI_DIR}/models/diffusion_models/"
echo "Foley Models: ${COMFYUI_DIR}/models/foley/"
echo "Foley Custom Node: ${FOLEY_NODE_DIR}"
echo ""
echo "Workflows available in ComfyUI:"
echo "  - HunyuanVideo15_T2V_Foley.json (Text-to-Video + Audio, combined)"
echo "  - HunyuanVideo15_720p_T2V.json (Text-to-Video, optional 1080p SR)"
echo "  - HunyuanVideo15_720p_I2V.json (Image-to-Video, optional 1080p SR)"
echo "  - HunyuanFoley_V2A.json (Video-to-Audio only)"
echo ""
echo "Access ComfyUI:"
echo "  - Web UI: http://localhost:8188 (via SSH tunnel)"
echo "========================================="
