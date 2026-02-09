# LTX-2 GPU Benchmark Results

## Benchmark Results (5s 1080p Portrait Video)

| GPU | VRAM | Workflow | Without Optimizations | With Optimizations |
|-----|------|----------|-----------------------|--------------------|
| A100 80GB | 80GB | T2V Distilled | ~300s | ~140s |
| A100 80GB | 80GB | T2V Full | ~800s | ~250s |
| A100 80GB | 80GB | I2V Full | ~850s | ~300s |

## Benchmark Test Config

### Test: 1080p Native Portrait (LTX-2 Recommended Workflow)

Uses the official 2-stage pipeline with spatial upscaler (`LTX-2_T2V_Distilled_wLora.json`).

**Pipeline:**
1. Generate at 540x960 (half res)
2. Spatial upscale in latent space (LTXVLatentUpsampler + ltx-2-spatial-upscaler-x2)
3. Refine at full resolution
4. Tiled VAE decode to 1080x1920

**Config:**
| Parameter | Stage 1 | Stage 2 |
|-----------|---------|---------|
| Resolution | 540x960 | 1080x1920 |
| Sampler | dpmpp_2m (DPM++ 2M) | dpmpp_2m (DPM++ 2M) |
| Sigmas | `1, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0` (8 steps) | `0.909375, 0.421875, 0.0` (2 steps) |
| CFG | 1.0 | 1.0 |

**Model Stack:**
- **Checkpoint**: ltx-2-19b-dev.safetensors
- **LoRA (optional)**: ltx-2-19b-distilled-lora-384.safetensors (strength 1.0)
- **Spatial Upscaler**: ltx-2-spatial-upscaler-x2-1.0.safetensors
- **Text Encoder**: Gemma 3 12B (gemma-3-12b-it-qat-q4_0-unquantized)
- **Audio VAE**: ltx-2-19b-distilled.safetensors

**Video Settings:**
- Frames: 153 (length) / 121 (fallback)
- Frame Rate: 30 fps
- Duration: ~5s
- Output: 1080x1920 portrait

**VAE Decode:**
- Mode: SpatioTemporalTiled
- Spatial tiles: 4, overlap: 4
- Temporal tile length: 16, overlap: 4

**Our Optimizations (on top of recommended workflow):**
- torch.compile with inductor backend (TorchCompileModel + TorchCompileVAE nodes)
- SageAttention (`--use-sage-attention`, ~2-3x faster attention)
- WaveSpeed First Block Cache (skip redundant transformer blocks, ~1.5-2x speedup)
- TF32 matmul precision (TORCH_FLOAT32_MATMUL_PRECISION=high)
- Reduced Stage 2 refinement from 3 to 2 steps
- DPM++ 2M sampler (better quality-per-step, good torch.compile compatibility)
- Persistent compile cache at `/workspace/torch_cache` (TORCHINDUCTOR_CACHE_DIR)
- PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
- WebSocket timeout increased to 300s (for first compile run)
- Video TTL cleanup (auto-delete outputs after 10m)

## Benchmark Prompts

**Positive Prompt:**
```
Style: cinematic with warm golden-hour lighting. A medium close-up shot of a weathered old fisherman standing at the bow of a small wooden boat on a calm lake at dawn. He wears a faded olive rain jacket and a knit beanie, his gray stubble catching the soft amber light. He holds a fishing rod in one hand, the line taut and trembling as something pulls beneath the surface. His eyes widen with quiet surprise and he steadies his footing on the rocking deck. He mutters under his breath in a low gravelly voice: "Well I'll be... haven't felt a pull like that in thirty years." He slowly reels the line in, muscles tensing in his forearm, water droplets flicking off the line and catching the light. Behind him, mist drifts across the glassy lake surface, and birds call faintly in the distance. The camera holds steady on his hands and face, drifting slightly closer as the tension builds.
```

**CLIP Text Encode (Negative) Prompt:**
```
blurry, low quality, overexposed, underexposed, duplicate faces, mirrored image, split screen, watermark, text overlay, subtitles, still frame, frozen, pixelated, grainy noise, distorted limbs, extra fingers, deformed hands, unnatural skin, plastic look
```

### Image-to-Video (Ghibli / No-Face)

**Positive Prompt:**
```
Style: Studio Ghibli hand-drawn animation. The masked dark spirit figure standing still in the rain slowly extends one arm forward, pale open hand offering a small glowing gold nugget. Rain streaks down its dark translucent body as it sways gently side to side. Its white mask face tilts slightly, mouth opening just a crack. It lets out a soft low breathy murmur: "ah... ah..." Water drips off its long arms and pools at its feet on the stone path. Behind it, warm orange lantern light flickers from a bathhouse doorway, casting long shadows. Raindrops tap steadily on wooden rooftops and splash in shallow puddles. The camera stays fixed in a medium shot, slowly drifting closer as the hand reaches further out.
```

**CLIP Text Encode (Negative) Prompt:**
```
blurry, low quality, photorealistic, 3d render, CGI, duplicate, mirrored image, split screen, watermark, text overlay, subtitles, still frame, frozen, pixelated, distorted face, extra limbs, inconsistent art style, flickering, frame skip
```

---
*Last Updated: 2026-02-09*
