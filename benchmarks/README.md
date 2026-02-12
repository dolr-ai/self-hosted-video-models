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
Style: cinematic drama movie scene shows a closeup of a blonde woman wearing a red sweater hanging out of the open door of a moving train, looking outside and smiling. the camera is fixed to the train's side as the train moves forward on the track. the woman seems excited and says: \" I think we're almost there!\". we hear the train's engine in the background. then, a little boy with brown hair pops his head out of the train along with the woman, looking at her in excitement. he then asks her: \"This is Nana's old village, isn't it?\". she nodes and embraces him joyfully.
```

**CLIP Text Encode (Negative) Prompt:**
```
blurry, low quality, overexposed, underexposed, duplicate faces, mirrored image, split screen, watermark, text overlay, subtitles, still frame, frozen, pixelated, grainy noise, distorted limbs, extra fingers, deformed hands, unnatural skin, plastic look
```
