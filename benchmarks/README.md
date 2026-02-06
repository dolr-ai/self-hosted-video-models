# LTX-2 GPU Benchmark Results

## Benchmark Results

| GPU | VRAM | Gen Res | Output Res | Upscale | Steps | CFG | Compile | 5s Video (warm) | Realtime | Issues/Notes |
|-----|------|---------|------------|---------|-------|-----|---------|-----------------|----------|--------------|
| A100 40GB | 40GB | 576x1024 | 1080x1920 | lanczos | 8 | 2.0 | ~29s | ~25-30s | ~6x | Works correctly |

## Configs Tested

| GPU | Config | Gen Res | Output Res | Upscale | Time (compile) | Time (warm) | Result |
|-----|--------|---------|------------|---------|----------------|-------------|--------|
| A100 40GB | Native 1080p | 1088x1920 | 1088x1920 | none | ~371s | - | Vertical "totem pole" duplication - image repeats vertically |
| A100 40GB | 768p portrait | 768x1344 | 768x1344 | none | ~492s | - | Horizontal mirroring - duplicate faces appear side by side |
| A100 40GB | 768p + CFG 4.0 | 768x1344 | 768x1344 | none | - | - | Still has mirroring - CFG increase didn't fix |
| A100 40GB | Square | 768x768 | 768x768 | none | - | ~44s | Works but not portrait aspect ratio |
| A100 40GB | 576p (3s test) | 576x1024 | 576x1024 | none | ~686s | ~25s | Works correctly - no artifacts |
| A100 40GB | 576p + lanczos | 576x1024 | 1080x1920 | lanczos | ~29s | ~25-30s | Works correctly - no artifacts |

## Model Config
- **Model**: LTX-2 19B Distilled
- **Text Encoder**: Gemma 3 12B (CLIP only, skip Gemma inference)
- **Sampler**: DDIM
- **Scheduler**: ddim_uniform
- **torch.compile**: inductor backend, caches per tensor shape

---
*Last Updated: 2025-02-06*
