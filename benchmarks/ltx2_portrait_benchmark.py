#!/usr/bin/env python3

import argparse
import base64
import json
import time
import statistics
import requests
import uuid
import websocket
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import io

# Generation resolution (must be divisible by 32)
# Using 576x1024 - tested to avoid mirroring/duplication artifacts
GEN_WIDTH = 576
GEN_HEIGHT = 1024

# Output resolution (upscaled to 1080p portrait, same 9:16 aspect ratio)
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
FPS = 24

# Benchmark run configuration
# torch.compile compiles kernels for each unique tensor shape (resolution + frames)
# First run compiles, subsequent runs use cached kernels
WARMUP_RUNS = 3  # Warmup runs per config to ensure torch.compile cache is warm
TIMED_RUNS = 3   # Timed runs after warmup for statistical measurement

# =============================================================================
# GEMMA SYSTEM PROMPTS (from Lightricks/LTX-2 official prompts)
# These instruct the model on how to interpret and expand prompts
# =============================================================================

# System prompt for Text-to-Video (T2V) mode
# Instructs Gemma to expand raw prompts into detailed video generation prompts
GEMMA_T2V_SYSTEM_PROMPT = """You are a Creative Assistant that generates detailed video prompts.

Core Requirements:
- Strictly follow all aspects of the user's raw input
- Invent concrete details when the input is vague
- Use active, present-progressive language with chronological flow
- Describe complete soundscapes integrated with actions
- Include exact dialogue with voice characteristics only when speech is requested

Formatting:
- Output as a single continuous paragraph in natural language
- Optional style declaration at beginning (default: cinematic-realistic)
- No timestamps, titles, or markdown formatting
- Start directly with style and scene description

Constraints:
- Exclude POV subject descriptions in first-person perspectives
- Don't invent camera motion unless requested
- Avoid exaggerated language; use mild, natural phrasing
- Don't modify user-provided dialogue or invent speech without explicit request
- Omit non-visual/auditory sensations"""

# System prompt for Image-to-Video (I2V/TI2V) mode
# Instructs Gemma to analyze images and describe only changes/motion
GEMMA_I2V_SYSTEM_PROMPT = """You are a Creative Assistant that generates concise, action-focused image-to-video prompts.

Core Requirements:
- Analyze images for subject, setting, elements, style, and mood
- Follow user requests while maintaining visual consistency with the source image
- Describe only changes from the initial image using active, present-progressive language
- Integrate audio descriptions throughout (not at the end), aligned with action intensity
- Include exact dialogue only when requested, with character voice characteristics

Constraints:
- DO NOT invent camera motion/movement unless requested by the user
- DO NOT modify or alter the user's provided character dialogue
- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation
- Avoid timestamps, scene cuts, emotional interpretation
- Output as single paragraph without markdown, headings, or code fences
- Limit sensory details to sight and sound only"""

# =============================================================================
# TEST PROMPTS (following LTX-2 best practices)
# Structure: Shot type → Scene/atmosphere → Subject + action → Camera → Audio
# =============================================================================

# T2V: Full scene description with all elements
T2V_PROMPT = """Cinematic portrait, shallow depth of field. A softly lit indoor setting with warm golden hour light streaming through a window, casting gentle shadows. A young woman with flowing dark hair stands in three-quarter profile, her expression contemplative and serene. She slowly turns her head toward the camera, her hair catching the light as it moves, eyes meeting the lens with quiet intensity. The camera remains steady on a tripod, framing her from shoulders up. Soft ambient room tone with the faint rustle of fabric as she moves."""

# TI2V: Focus on motion/changes from the source image
TI2V_PROMPT = """The subject's hair begins to drift gently as if touched by a soft breeze, individual strands catching the existing light. Her head turns slowly and smoothly toward the camera, chin lifting slightly. Eyes blink naturally, lips part subtly. The ambient lighting shifts almost imperceptibly as she moves. Soft rustling of hair and fabric, quiet breathing."""

# Negative prompt following best practices (avoid artifacts, maintain quality)
NEGATIVE_PROMPT = "blurry, low quality, distorted, artifacts, static, frozen, text, watermark, oversaturated, underexposed, grainy, pixelated, unnatural motion, jittery"


@dataclass
class BenchmarkResult:
    config_name: str
    mode: str  # "t2v" or "ti2v"
    resolution: str
    frames: int
    steps: int
    duration_sec: float
    warmup_times_sec: list  # All warmup run times (first includes compile)
    run_times_sec: list     # Timed runs after warmup
    avg_time_sec: float
    std_dev_sec: float
    fps_generated: float
    sec_per_frame: float
    compile_time_sec: float  # First warmup minus avg of rest (approximate compile overhead)
    timestamp: str


def generate_test_image_base64() -> str:
    """Generate a simple gradient test image as base64 PNG for TI2V benchmarks"""
    try:
        from PIL import Image

        # Create a gradient image (portrait orientation)
        img = Image.new('RGB', (GEN_WIDTH, GEN_HEIGHT))
        pixels = img.load()

        for y in range(GEN_HEIGHT):
            for x in range(GEN_WIDTH):
                # Warm gradient from dark to light
                r = int(40 + (y / GEN_HEIGHT) * 100)
                g = int(30 + (y / GEN_HEIGHT) * 80)
                b = int(50 + (x / GEN_WIDTH) * 60)
                pixels[x, y] = (r, g, b)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except ImportError:
        return None


def upload_image(server: str, image_path: str = None) -> str:
    """Upload an image to ComfyUI and return the filename, or generate a test image"""
    if image_path and Path(image_path).exists():
        # Upload user-provided image
        with open(image_path, 'rb') as f:
            files = {'image': (Path(image_path).name, f, 'image/png')}
            response = requests.post(f"{server}/upload/image", files=files)
            response.raise_for_status()
            return response.json()['name']
    else:
        # Generate and upload a test image
        base64_img = generate_test_image_base64()
        if base64_img is None:
            raise RuntimeError("PIL not available and no image provided. Install Pillow or provide --image")

        img_bytes = base64.b64decode(base64_img)
        files = {'image': ('benchmark_test.png', io.BytesIO(img_bytes), 'image/png')}
        response = requests.post(f"{server}/upload/image", files=files)
        response.raise_for_status()
        return response.json()['name']


def build_t2v_workflow(frames: int, steps: int, seed: int) -> dict:
    """Build text-to-video workflow for portrait 1080p

    T2V uses:
    1. LTXVGemmaCLIPModelLoader to load text encoder (required for LTX-2)
    2. Direct CLIPTextEncode (skips Gemma inference for faster generation)
    3. EmptyLTXVLatentVideo - generates empty latent, output index [0]
    4. Lanczos upscale after VAE decode to 1080p
    """
    return {
        "prompt": {
            "1": {
                "inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "1b": {
                "inputs": {"model": ["1", 0], "backend": "inductor"},
                "class_type": "TorchCompileModel"
            },
            # Load text encoder (CLIP from Gemma loader, but we skip Gemma inference)
            "2": {
                "inputs": {
                    "gemma_path": "gemma-3-12b-it-qat-q4_0-unquantized/model-00001-of-00005.safetensors",
                    "ltxv_path": "ltx-2-19b-distilled.safetensors",
                    "max_length": 1024
                },
                "class_type": "LTXVGemmaCLIPModelLoader"
            },
            "3": {
                "inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"},
                "class_type": "LTXVAudioVAELoader"
            },
            "5": {
                "inputs": {
                    "frames_number": frames,
                    "frame_rate": FPS,
                    "batch_size": 1,
                    "audio_vae": ["3", 0]
                },
                "class_type": "LTXVEmptyLatentAudio"
            },
            # T2V: Direct CLIP encoding (skip Gemma inference, use CLIP directly)
            "7": {
                "inputs": {"text": T2V_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {"text": NEGATIVE_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            # T2V: EmptyLTXVLatentVideo - output index [0]
            "9": {
                "inputs": {
                    "width": GEN_WIDTH,
                    "height": GEN_HEIGHT,
                    "length": frames,
                    "batch_size": 1
                },
                "class_type": "EmptyLTXVLatentVideo"
            },
            "9b": {
                "inputs": {
                    "positive": ["7", 0],
                    "negative": ["8", 0],
                    "frame_rate": FPS
                },
                "class_type": "LTXVConditioning"
            },
            "6": {
                "inputs": {
                    "video_latent": ["9", 0],  # T2V uses index 0
                    "audio_latent": ["5", 0]
                },
                "class_type": "LTXVConcatAVLatent"
            },
            "10": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": 2.0,
                    "sampler_name": "ddim",
                    "scheduler": "ddim_uniform",
                    "denoise": 1,
                    "model": ["1b", 0],
                    "positive": ["9b", 0],
                    "negative": ["9b", 1],
                    "latent_image": ["6", 0]
                },
                "class_type": "KSampler"
            },
            "11": {
                "inputs": {"av_latent": ["10", 0]},
                "class_type": "LTXVSeparateAVLatent"
            },
            "12": {
                "inputs": {"samples": ["11", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            # Lanczos upscale to 1080p portrait
            "12b": {
                "inputs": {
                    "upscale_method": "lanczos",
                    "width": OUT_WIDTH,
                    "height": OUT_HEIGHT,
                    "crop": "disabled",
                    "image": ["12", 0]
                },
                "class_type": "ImageScale"
            },
            "13": {
                "inputs": {"samples": ["11", 1], "audio_vae": ["3", 0]},
                "class_type": "LTXVAudioVAEDecode"
            },
            "14": {
                "inputs": {"fps": FPS, "images": ["12b", 0], "audio": ["13", 0]},
                "class_type": "CreateVideo"
            },
            "15": {
                "inputs": {
                    "filename_prefix": f"bench_t2v_{frames}f_{steps}s",
                    "format": "mp4",
                    "codec": "h264",
                    "video": ["14", 0]
                },
                "class_type": "SaveVideo"
            }
        }
    }


def build_ti2v_workflow(frames: int, steps: int, seed: int, image_name: str) -> dict:
    """Build text+image-to-video workflow for portrait 1080p

    TI2V (Image-to-Video) uses:
    1. LTXVGemmaCLIPModelLoader to load text encoder (required for LTX-2)
    2. Direct CLIPTextEncode (skips Gemma inference for faster generation)
    3. LTXVImgToVideo - Encodes image to latent, output index [2]
    4. Lanczos upscale after VAE decode to 1080p
    """
    return {
        "prompt": {
            "1": {
                "inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "1b": {
                "inputs": {"model": ["1", 0], "backend": "inductor"},
                "class_type": "TorchCompileModel"
            },
            # Load text encoder (CLIP from Gemma loader, but we skip Gemma inference)
            "2": {
                "inputs": {
                    "gemma_path": "gemma-3-12b-it-qat-q4_0-unquantized/model-00001-of-00005.safetensors",
                    "ltxv_path": "ltx-2-19b-distilled.safetensors",
                    "max_length": 1024
                },
                "class_type": "LTXVGemmaCLIPModelLoader"
            },
            "3": {
                "inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"},
                "class_type": "LTXVAudioVAELoader"
            },
            # Load input image
            "4": {
                "inputs": {"image": image_name},
                "class_type": "LoadImage"
            },
            "5": {
                "inputs": {
                    "frames_number": frames,
                    "frame_rate": FPS,
                    "batch_size": 1,
                    "audio_vae": ["3", 0]
                },
                "class_type": "LTXVEmptyLatentAudio"
            },
            # TI2V: Direct CLIP encoding (skip Gemma inference, use CLIP directly)
            "7": {
                "inputs": {"text": TI2V_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {"text": NEGATIVE_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            # TI2V: LTXVImgToVideo - output index [2] for latent
            "9": {
                "inputs": {
                    "positive": ["7", 0],
                    "negative": ["8", 0],
                    "vae": ["1", 2],
                    "image": ["4", 0],
                    "width": GEN_WIDTH,
                    "height": GEN_HEIGHT,
                    "length": frames,
                    "batch_size": 1,
                    "strength": 1.0
                },
                "class_type": "LTXVImgToVideo"
            },
            "9b": {
                "inputs": {
                    "positive": ["9", 0],  # Conditioning from LTXVImgToVideo
                    "negative": ["9", 1],
                    "frame_rate": FPS
                },
                "class_type": "LTXVConditioning"
            },
            "10a": {
                "inputs": {
                    "video_latent": ["9", 2],  # TI2V uses index 2
                    "audio_latent": ["5", 0]
                },
                "class_type": "LTXVConcatAVLatent"
            },
            "10": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": 2.0,
                    "sampler_name": "ddim",
                    "scheduler": "ddim_uniform",
                    "denoise": 1,
                    "model": ["1b", 0],
                    "positive": ["9b", 0],
                    "negative": ["9b", 1],
                    "latent_image": ["10a", 0]
                },
                "class_type": "KSampler"
            },
            "11": {
                "inputs": {"av_latent": ["10", 0]},
                "class_type": "LTXVSeparateAVLatent"
            },
            "12": {
                "inputs": {"samples": ["11", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            "12b": {
                "inputs": {"images": ["12", 0], "factor": 0.8},
                "class_type": "AdjustContrast"
            },
            # Lanczos upscale to 1080p portrait
            "12c": {
                "inputs": {
                    "upscale_method": "lanczos",
                    "width": OUT_WIDTH,
                    "height": OUT_HEIGHT,
                    "crop": "disabled",
                    "image": ["12b", 0]
                },
                "class_type": "ImageScale"
            },
            "13": {
                "inputs": {"samples": ["11", 1], "audio_vae": ["3", 0]},
                "class_type": "LTXVAudioVAEDecode"
            },
            "14": {
                "inputs": {"fps": FPS, "images": ["12c", 0], "audio": ["13", 0]},
                "class_type": "CreateVideo"
            },
            "15": {
                "inputs": {
                    "filename_prefix": f"bench_ti2v_{frames}f_{steps}s",
                    "format": "mp4",
                    "codec": "h264",
                    "video": ["14", 0]
                },
                "class_type": "SaveVideo"
            }
        }
    }


def queue_prompt(server: str, workflow: dict) -> tuple[str, str]:
    """Queue a prompt and return the prompt_id"""
    client_id = str(uuid.uuid4())
    response = requests.post(
        f"{server}/prompt",
        json={"prompt": workflow["prompt"], "client_id": client_id}
    )
    response.raise_for_status()
    return response.json()["prompt_id"], client_id


def wait_for_completion(server: str, _prompt_id: str, client_id: str) -> float:
    """Wait for prompt completion via websocket, return execution time"""
    ws_url = server.replace("http://", "ws://").replace("https://", "wss://")
    ws = websocket.create_connection(f"{ws_url}/ws?clientId={client_id}")

    start_time = time.perf_counter()
    executing = False

    try:
        while True:
            msg = ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                msg_type = data.get("type")

                if msg_type == "executing":
                    node = data.get("data", {}).get("node")
                    if node is None and executing:
                        # Execution completed
                        return time.perf_counter() - start_time
                    elif node is not None:
                        executing = True

                elif msg_type == "execution_error":
                    error = data.get("data", {}).get("exception_message", "Unknown error")
                    raise RuntimeError(f"Execution error: {error}")
    finally:
        ws.close()


def run_single_benchmark(server: str, mode: str, frames: int, steps: int,
                          is_warmup: bool, image_name: str = None) -> float:
    """Run a single benchmark and return execution time"""
    seed = 42 if is_warmup else int(time.time() * 1000) % 2**32

    if mode == "t2v":
        workflow = build_t2v_workflow(frames, steps, seed)
    else:  # ti2v
        workflow = build_ti2v_workflow(frames, steps, seed, image_name)

    prompt_id, client_id = queue_prompt(server, workflow)
    exec_time = wait_for_completion(server, prompt_id, client_id)

    return exec_time


def run_benchmark_suite(server: str, modes: list[str], image_path: str = None) -> list[BenchmarkResult]:
    """Run the full benchmark suite for specified modes"""
    results = []

    # Upload image once if needed for TI2V
    image_name = None
    if "ti2v" in modes:
        print("Uploading test image for TI2V benchmarks...")
        try:
            image_name = upload_image(server, image_path)
            print(f"  Image uploaded: {image_name}")
        except Exception as e:
            print(f"  ERROR uploading image: {e}")
            if "ti2v" in modes and len(modes) == 1:
                return results
            modes = [m for m in modes if m != "ti2v"]
            print(f"  Continuing with modes: {modes}")

    # Benchmark configurations
    configs = [
        {"name": "5s_8steps", "frames": 121, "steps": 8, "duration_sec": 5},
        {"name": "5s_10steps", "frames": 121, "steps": 10, "duration_sec": 5},
        {"name": "10s_8steps", "frames": 241, "steps": 8, "duration_sec": 10},
        {"name": "10s_10steps", "frames": 241, "steps": 10, "duration_sec": 10},
    ]

    print("\n" + "=" * 70)
    print("LTX-2 Portrait 1080p Benchmark Suite")
    print(f"Generate: {GEN_WIDTH}x{GEN_HEIGHT} -> Upscale: {OUT_WIDTH}x{OUT_HEIGHT}")
    print(f"Server: {server}")
    print(f"Modes: {', '.join(modes)}")
    print(f"Warmup runs per config: {WARMUP_RUNS}")
    print(f"Timed runs per config: {TIMED_RUNS}")
    print("=" * 70)

    for mode in modes:
        mode_label = "Text-to-Video (T2V)" if mode == "t2v" else "Text+Image-to-Video (TI2V)"
        print(f"\n{'#' * 70}")
        print(f"# MODE: {mode_label}")
        print(f"{'#' * 70}")

        for config in configs:
            config_name = f"{mode}_{config['name']}"

            print(f"\n{'='*60}")
            print(f"Config: {config_name}")
            print(f"  Mode: {mode.upper()}")
            print(f"  Generate: {GEN_WIDTH}x{GEN_HEIGHT} -> Output: {OUT_WIDTH}x{OUT_HEIGHT}")
            print(f"  Frames: {config['frames']} ({config['duration_sec']}s @ {FPS}fps)")
            print(f"  Steps: {config['steps']}")
            print("=" * 60)

            # Warmup runs (first includes torch.compile, rest warm the cache)
            warmup_times = []
            print(f"\n[WARMUP] Running {WARMUP_RUNS} warmup runs (first includes torch.compile)...")
            for i in range(WARMUP_RUNS):
                try:
                    warmup_time = run_single_benchmark(
                        server, mode, config["frames"], config["steps"],
                        is_warmup=True, image_name=image_name
                    )
                    warmup_times.append(warmup_time)
                    if i == 0:
                        print(f"  [WARMUP {i+1}/{WARMUP_RUNS}] {warmup_time:.2f}s (includes compile)")
                    else:
                        print(f"  [WARMUP {i+1}/{WARMUP_RUNS}] {warmup_time:.2f}s")
                except Exception as e:
                    print(f"  [WARMUP {i+1}/{WARMUP_RUNS}] FAILED: {e}")

            if len(warmup_times) < 2:
                print(f"[ERROR] Not enough warmup runs succeeded for {config_name}")
                continue

            # Calculate approximate compile overhead
            compile_time = warmup_times[0] - statistics.mean(warmup_times[1:]) if len(warmup_times) > 1 else 0.0

            # Timed runs (after warmup, cache is hot)
            run_times = []
            print(f"\n[TIMED] Running {TIMED_RUNS} timed runs...")
            for i in range(TIMED_RUNS):
                try:
                    run_time = run_single_benchmark(
                        server, mode, config["frames"], config["steps"],
                        is_warmup=False, image_name=image_name
                    )
                    run_times.append(run_time)
                    print(f"  [RUN {i+1}/{TIMED_RUNS}] {run_time:.2f}s")
                except Exception as e:
                    print(f"  [RUN {i+1}/{TIMED_RUNS}] FAILED: {e}")

            if not run_times:
                print(f"[ERROR] All timed runs failed for {config_name}")
                continue

            # Calculate statistics
            avg_time = statistics.mean(run_times)
            std_dev = statistics.stdev(run_times) if len(run_times) > 1 else 0.0
            fps_generated = config["frames"] / avg_time
            sec_per_frame = avg_time / config["frames"]

            result = BenchmarkResult(
                config_name=config_name,
                mode=mode,
                resolution=f"{GEN_WIDTH}x{GEN_HEIGHT}->{OUT_WIDTH}x{OUT_HEIGHT}",
                frames=config["frames"],
                steps=config["steps"],
                duration_sec=config["duration_sec"],
                warmup_times_sec=warmup_times,
                run_times_sec=run_times,
                avg_time_sec=avg_time,
                std_dev_sec=std_dev,
                fps_generated=fps_generated,
                sec_per_frame=sec_per_frame,
                compile_time_sec=max(0, compile_time),  # Don't report negative
                timestamp=datetime.now().isoformat()
            )
            results.append(result)

            # Print summary
            print(f"\n[SUMMARY] {config_name}")
            print(f"  Warmup times:    {[f'{t:.2f}s' for t in warmup_times]}")
            print(f"  Compile overhead: ~{max(0, compile_time):.2f}s")
            print(f"  Avg gen time:    {avg_time:.2f}s ± {std_dev:.2f}s")
            print(f"  Frames/sec:      {fps_generated:.2f}")
            print(f"  Sec/frame:       {sec_per_frame:.3f}s")
            print(f"  Realtime factor: {config['duration_sec'] / avg_time:.2f}x")

    return results


def print_final_report(results: list[BenchmarkResult]):
    """Print final benchmark report"""
    print("\n")
    print("=" * 110)
    print("FINAL BENCHMARK REPORT - LTX-2 Portrait 1080p")
    print("=" * 110)
    print()

    # Group by mode
    for mode in ["t2v", "ti2v"]:
        mode_results = [r for r in results if r.mode == mode]
        if not mode_results:
            continue

        mode_label = "TEXT-TO-VIDEO (T2V)" if mode == "t2v" else "TEXT+IMAGE-TO-VIDEO (TI2V)"
        print(f"\n{mode_label}")
        print("-" * 110)
        print(f"{'Config':<20} {'Frames':<8} {'Steps':<6} {'Compile':<10} {'Avg Time':<12} {'Std Dev':<10} {'FPS':<8} {'Realtime':<10}")
        print("-" * 110)

        for r in mode_results:
            realtime_factor = r.duration_sec / r.avg_time_sec
            print(f"{r.config_name:<20} {r.frames:<8} {r.steps:<6} {r.compile_time_sec:<10.2f} {r.avg_time_sec:<12.2f} {r.std_dev_sec:<10.2f} {r.fps_generated:<8.2f} {realtime_factor:<10.2f}x")

    print("\n" + "=" * 110)

    # Summary stats
    if results:
        print("\nKEY METRICS:")

        for mode in ["t2v", "ti2v"]:
            mode_results = [r for r in results if r.mode == mode]
            if not mode_results:
                continue

            mode_label = "T2V" if mode == "t2v" else "TI2V"
            fastest = min(mode_results, key=lambda r: r.avg_time_sec)
            print(f"\n  {mode_label} Fastest: {fastest.config_name}")
            print(f"    - {fastest.duration_sec}s video in {fastest.avg_time_sec:.2f}s")
            print(f"    - {fastest.duration_sec / fastest.avg_time_sec:.2f}x realtime")
            print(f"    - Compile overhead: ~{fastest.compile_time_sec:.2f}s")

            # 10s video stats
            ten_sec = [r for r in mode_results if r.duration_sec == 10]
            if ten_sec:
                best_10s = min(ten_sec, key=lambda r: r.avg_time_sec)
                print(f"  {mode_label} 10s Video: {best_10s.avg_time_sec:.2f}s ({10 / best_10s.avg_time_sec:.2f}x realtime)")


def save_results(results: list[BenchmarkResult], output_file: str):
    """Save results to JSON file"""
    with open(output_file, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="LTX-2 Portrait 1080p Benchmark (T2V & TI2V)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ltx2_portrait_benchmark.py --server http://localhost:8188 --mode t2v
  python ltx2_portrait_benchmark.py --server http://localhost:8188 --mode ti2v --image /path/to/image.png
  python ltx2_portrait_benchmark.py --server http://localhost:8188 --mode all --image /path/to/image.png
        """
    )
    parser.add_argument("--server", default="http://localhost:8188", help="ComfyUI server URL")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON file")
    parser.add_argument("--mode", choices=["t2v", "ti2v", "all"], default="all",
                       help="Benchmark mode: t2v, ti2v, or all (default: all)")
    parser.add_argument("--image", help="Path to input image for TI2V mode (optional, will generate test image if not provided)")
    args = parser.parse_args()

    # Determine modes to run
    if args.mode == "all":
        modes = ["t2v", "ti2v"]
    else:
        modes = [args.mode]

    # Check server connectivity
    try:
        response = requests.get(f"{args.server}/system_stats", timeout=5)
        response.raise_for_status()
        print(f"Connected to ComfyUI at {args.server}")
    except Exception as e:
        print(f"ERROR: Cannot connect to ComfyUI at {args.server}")
        print(f"  {e}")
        sys.exit(1)

    results = run_benchmark_suite(args.server, modes, args.image)

    if results:
        print_final_report(results)
        save_results(results, args.output)
    else:
        print("\nNo successful benchmark runs completed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
