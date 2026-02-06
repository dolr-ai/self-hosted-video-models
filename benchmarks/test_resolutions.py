#!/usr/bin/env python3
"""Quick test script to find resolution/CFG that avoids mirroring artifacts"""

import json
import time
import requests
import uuid
import websocket
import sys

# Test configurations to try
CONFIGS = [
    {"name": "576x1024_cfg2", "width": 576, "height": 1024, "cfg": 2.0},
    {"name": "768x768_cfg2", "width": 768, "height": 768, "cfg": 2.0},
    {"name": "768x1344_cfg4", "width": 768, "height": 1344, "cfg": 4.0},
]

FPS = 24
FRAMES = 73  # 3 seconds for quick test
STEPS = 8

T2V_PROMPT = """Cinematic portrait, shallow depth of field. A softly lit indoor setting with warm golden hour light streaming through a window, casting gentle shadows. A young woman with flowing dark hair stands in three-quarter profile, her expression contemplative and serene. She slowly turns her head toward the camera, her hair catching the light as it moves, eyes meeting the lens with quiet intensity. The camera remains steady on a tripod, framing her from shoulders up. Soft ambient room tone with the faint rustle of fabric as she moves."""

NEGATIVE_PROMPT = "blurry, low quality, distorted, artifacts, static, frozen, text, watermark, oversaturated, underexposed, grainy, pixelated, unnatural motion, jittery, duplicate, mirror, reflection, split, multiple people, two faces"


def build_workflow(width: int, height: int, cfg: float, name: str) -> dict:
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
                    "frames_number": FRAMES,
                    "frame_rate": FPS,
                    "batch_size": 1,
                    "audio_vae": ["3", 0]
                },
                "class_type": "LTXVEmptyLatentAudio"
            },
            "7": {
                "inputs": {"text": T2V_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {"text": NEGATIVE_PROMPT, "clip": ["2", 0]},
                "class_type": "CLIPTextEncode"
            },
            "9": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "length": FRAMES,
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
                    "video_latent": ["9", 0],
                    "audio_latent": ["5", 0]
                },
                "class_type": "LTXVConcatAVLatent"
            },
            "10": {
                "inputs": {
                    "seed": 42,
                    "steps": STEPS,
                    "cfg": cfg,
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
            "13": {
                "inputs": {"samples": ["11", 1], "audio_vae": ["3", 0]},
                "class_type": "LTXVAudioVAEDecode"
            },
            "14": {
                "inputs": {"fps": FPS, "images": ["12", 0], "audio": ["13", 0]},
                "class_type": "CreateVideo"
            },
            "15": {
                "inputs": {
                    "filename_prefix": f"test_{name}",
                    "format": "mp4",
                    "codec": "h264",
                    "video": ["14", 0]
                },
                "class_type": "SaveVideo"
            }
        }
    }


def run_test(server: str, config: dict) -> float:
    """Run a single test and return execution time"""
    workflow = build_workflow(config["width"], config["height"], config["cfg"], config["name"])

    client_id = str(uuid.uuid4())
    response = requests.post(
        f"{server}/prompt",
        json={"prompt": workflow["prompt"], "client_id": client_id}
    )
    response.raise_for_status()
    prompt_id = response.json()["prompt_id"]

    # Wait for completion
    ws_url = server.replace("http://", "ws://")
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
                        return time.perf_counter() - start_time
                    elif node is not None:
                        executing = True

                elif msg_type == "execution_error":
                    error = data.get("data", {}).get("exception_message", "Unknown error")
                    raise RuntimeError(f"Execution error: {error}")
    finally:
        ws.close()


def main():
    server = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18188"

    print(f"Testing resolutions on {server}")
    print(f"Frames: {FRAMES} ({FRAMES/FPS:.1f}s @ {FPS}fps)")
    print(f"Steps: {STEPS}")
    print("=" * 60)

    # Check connectivity
    try:
        response = requests.get(f"{server}/system_stats", timeout=5)
        response.raise_for_status()
        print("Connected to ComfyUI\n")
    except Exception as e:
        print(f"ERROR: Cannot connect to ComfyUI: {e}")
        sys.exit(1)

    for config in CONFIGS:
        print(f"\n[TEST] {config['name']}")
        print(f"  Resolution: {config['width']}x{config['height']}")
        print(f"  CFG: {config['cfg']}")

        try:
            exec_time = run_test(server, config)
            print(f"  Time: {exec_time:.2f}s")
            print(f"  Output: test_{config['name']}_00001_.mp4")
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\n" + "=" * 60)
    print("Done! Download videos to compare:")
    for config in CONFIGS:
        print(f"  - test_{config['name']}_00001_.mp4")


if __name__ == "__main__":
    main()
