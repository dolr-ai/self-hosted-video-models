# LTX-2 GPU Benchmark Results

## Benchmark Results (5s 1080p Portrait Video)

| GPU | VRAM | Workflow | Without Optimizations | With Optimizations |
|-----|------|----------|-----------------------|--------------------|
| A100 80GB | 80GB | Distilled | ~300s | ~140s |
| A100 80GB | 80GB | Full | ~800s | ~250s |
| H100 80GB | 80GB | Distilled | ~80-100s | ~30-50s |
| H100 80GB | 80GB | Full | ~200s | ~90-100s |
| H100 80GB (custom) | 80GB | Distilled | - | ~15-20s |
| B200 192GB | 192GB | Distilled | ~60-80s | ~20-35s |
| B200 192GB | 192GB | Full | ~150s | ~70-80s |

## Benchmark Test Config

### Test: 1080p Native Portrait (LTX-2 Recommended Workflow)

**Optimizations (on top of recommended workflow):**
- torch.compile with inductor backend (TorchCompileModel + TorchCompileVAE nodes)
- SageAttention (`--use-sage-attention`, ~2-3x faster attention)
- Persistent compile cache at `/workspace/torch_cache` (TORCHINDUCTOR_CACHE_DIR)
- PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

## Benchmark Prompts

**Positive Prompt:**
```
Style: cinematic with warm golden-hour lighting. A medium close-up shot of a weathered old fisherman standing at the bow of a small wooden boat on a calm lake at dawn. He wears a faded olive rain jacket and a knit beanie, his gray stubble catching the soft amber light. He holds a fishing rod in one hand, the line taut and trembling as something pulls beneath the surface. His eyes widen with quiet surprise and he steadies his footing on the rocking deck. He mutters under his breath in a low gravelly voice: "Well I'll be... haven't felt a pull like that in thirty years." He slowly reels the line in, muscles tensing in his forearm, water droplets flicking off the line and catching the light. Behind him, mist drifts across the glassy lake surface, and birds call faintly in the distance. The camera holds steady on his hands and face, drifting slightly closer as the tension builds.
```

**CLIP Text Encode (Negative) Prompt:**
```
blurry, low quality, overexposed, underexposed, duplicate faces, mirrored image, split screen, watermark, text overlay, subtitles, still frame, frozen, pixelated, grainy noise, distorted limbs, extra fingers, deformed hands, unnatural skin, plastic look
```