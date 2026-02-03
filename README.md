# Self-Hosted Video Models on Vast.ai

Infrastructure and automation for deploying video generation models (LTX-2) on Vast.ai GPU instances.

## Quick Start

### 1. Manual Setup on Vast.ai Instance

```bash
# SSH into your Vast.ai instance
ssh -p <PORT> root@<HOST>

# Download and run the setup script
wget https://raw.githubusercontent.com/<YOUR_ORG>/self-hosted-models-infra/main/setup-ltx.sh
bash setup-ltx.sh
```

This will:
- Install ComfyUI if not present
- Download LTX-2 model (41GB) to persistent volume
- Install LTX custom nodes
- Download FP8 Gemma text encoder (13GB)
- Start ComfyUI on port 8188
- Start API wrapper on port 8288
- Deploy video cleanup script with configurable TTL

### 2. Automated Setup via GitHub Actions

For recurring setups or managing multiple instances:

1. **Add SSH key to GitHub Secrets**
   - Go to repository Settings > Secrets and variables > Actions
   - Create secret: `VASTAI_SSH_KEY`
   - Paste your private SSH key that has access to Vast.ai instances

2. **Trigger the workflow**
   - Go to Actions > "Setup Vast.ai Instance" > "Run workflow"
   - Enter SSH host (e.g., `185.150.27.254`)
   - Enter SSH port (e.g., `30261`)
   - Optional: HuggingFace token for gated models
   - Optional: Video TTL (default: 10 minutes)
   - Optional: Cleanup interval (default: 300 seconds)

The workflow will:
- Check instance status and existing installations
- Copy setup scripts to the instance
- Run setup (reusing existing models if present)
- Install video cleanup script
- Verify all services are running

## Components

### LTX-2 Model
- **Size**: 41GB (ltx-2-19b-dev.safetensors)
- **Location**: `/workspace/ComfyUI/models/checkpoints/`
- **VRAM**: ~20-25GB during inference

### Text Encoder (Gemma FP8)
- **Size**: 13GB (FP8 quantized for efficiency)
- **Location**: `/workspace/ComfyUI/models/clip/LTX-2-comfy_gemma_fp8_e4m3fn/`
- **VRAM**: ~8-10GB during inference
- **Total VRAM**: ~33-35GB (fits in A100 40GB)

### Video Cleanup Script
Automatically deletes generated videos after a configurable TTL to manage disk space.

- **Default TTL**: 10 minutes
- **Check interval**: 5 minutes
- **Monitored formats**: mp4, avi, mov, webm, mkv
- **Log file**: `/var/log/video-cleanup.log`

**Configuration:**
```bash
export VIDEO_TTL_MINUTES=20  # Keep videos for 20 minutes
export CLEANUP_CHECK_INTERVAL=600  # Check every 10 minutes
```

## API Usage

### ComfyUI Web UI
```
http://<HOST>:<PORT>/
```

### API Wrapper (Port 8288)
Protected with HTTP Basic Auth using `JUPYTER_TOKEN`.

**Generate video:**
```bash
curl -X POST http://<HOST>:<PORT>/generate \
  -H "Content-Type: application/json" \
  -u ":<JUPYTER_TOKEN>" \
  -d @workflow.json
```

**Example workflow:** See working example in test jobs.

## Vast.ai Instance Recommendations

### GPU Requirements
- **Minimum VRAM**: 40GB (e.g., A100 40GB)
- **Recommended**: A100 80GB for larger batches or higher resolution

### Storage
- **Minimum volume**: 100GB
- **Recommended**: 256GB+ (models: ~60GB, outputs: variable)

### Network
- Enable ports: 8188 (ComfyUI), 8288 (API)
- Consider Cloudflare tunnel for public access

### Cost Optimization
1. Use on-demand instances with persistent volumes
2. Reuse volumes across instance recreations
3. Convert to reserved instances for 50% discount
4. Use video cleanup script to manage disk space

## Troubleshooting

### Check service status
```bash
supervisorctl status
```

### View ComfyUI logs
```bash
tail -f /var/log/portal/comfyui.log
```

### View video cleanup logs
```bash
tail -f /var/log/video-cleanup.log
```

### Check if models are loaded
```bash
ls -lh /workspace/ComfyUI/models/checkpoints/
ls -lh /workspace/ComfyUI/models/clip/LTX-2-comfy_gemma_fp8_e4m3fn/
```

### Restart services
```bash
supervisorctl restart comfyui
supervisorctl restart comfyui-api-wrapper
```

## Files

- `setup-ltx.sh` - Main setup script for ComfyUI and LTX-2
- `video-cleanup.sh` - TTL-based video cleanup daemon
- `.github/workflows/setup-vastai-instance.yml` - Automated setup CI
- `.github/workflows/build-custom-image.yml` - Docker image builder

## License

MIT
