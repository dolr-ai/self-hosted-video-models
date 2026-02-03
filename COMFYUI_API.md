# ComfyUI LTX-2 Video Generation API

## Base URL
```
http://185.150.27.254:8188
```

## Authentication
All requests require a Bearer token in the Authorization header.

**Bearer Token:**
```
<YOUR_BEARER_TOKEN>
```

**Example:**
```bash
curl -H "Authorization: Bearer <YOUR_BEARER_TOKEN>" \
  http://185.150.27.254:8188/queue
```

---

## Endpoints

### 1. Submit Generation Job

**Endpoint:** `POST /prompt`

**Description:** Submit a video generation job to the queue.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "prompt": {
    "1": {
      "inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"},
      "class_type": "CheckpointLoaderSimple"
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
    "4": {
      "inputs": {
        "width": 1920,
        "height": 1088,
        "length": 121,
        "batch_size": 1
      },
      "class_type": "EmptyLTXVLatentVideo"
    },
    "5": {
      "inputs": {
        "frames_number": 121,
        "frame_rate": 24,
        "batch_size": 1,
        "audio_vae": ["3", 0]
      },
      "class_type": "LTXVEmptyLatentAudio"
    },
    "6": {
      "inputs": {
        "video_latent": ["4", 0],
        "audio_latent": ["5", 0]
      },
      "class_type": "LTXVConcatAVLatent"
    },
    "7": {
      "inputs": {
        "text": "Your video description here with audio details",
        "clip": ["2", 0]
      },
      "class_type": "CLIPTextEncode"
    },
    "8": {
      "inputs": {
        "text": "blurry, low quality, distorted, silent, no sound",
        "clip": ["2", 0]
      },
      "class_type": "CLIPTextEncode"
    },
    "9": {
      "inputs": {
        "positive": ["7", 0],
        "negative": ["8", 0],
        "frame_rate": 24
      },
      "class_type": "LTXVConditioning"
    },
    "10": {
      "inputs": {
        "seed": 42,
        "steps": 30,
        "cfg": 5.0,
        "sampler_name": "euler",
        "scheduler": "simple",
        "denoise": 1,
        "model": ["1", 0],
        "positive": ["9", 0],
        "negative": ["9", 1],
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
      "inputs": {
        "samples": ["11", 1],
        "audio_vae": ["3", 0]
      },
      "class_type": "LTXVAudioVAEDecode"
    },
    "14": {
      "inputs": {
        "fps": 24,
        "images": ["12", 0],
        "audio": ["13", 0]
      },
      "class_type": "CreateVideo"
    },
    "15": {
      "inputs": {
        "filename_prefix": "generated-video",
        "format": "mp4",
        "codec": "h264",
        "video": ["14", 0]
      },
      "class_type": "SaveVideo"
    }
  }
}
```

**Response:**
```json
{
  "prompt_id": "8923875e-b7e0-4b54-b594-f34924c9888b",
  "number": 0,
  "node_errors": {}
}
```

**Status Codes:**
- `200 OK` - Job submitted successfully
- `401 Unauthorized` - Invalid or missing bearer token
- `400 Bad Request` - Invalid workflow structure

---

### 2. Check Queue Status

**Endpoint:** `GET /queue`

**Description:** Get the current job queue status.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "queue_running": [
    ["8923875e-b7e0-4b54-b594-f34924c9888b", 0, {...}]
  ],
  "queue_pending": []
}
```

**Fields:**
- `queue_running`: Array of currently executing jobs
- `queue_pending`: Array of jobs waiting to execute

---

### 3. Get Job History

**Endpoint:** `GET /history/{prompt_id}`

**Description:** Get the execution history and results for a specific job.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "8923875e-b7e0-4b54-b594-f34924c9888b": {
    "prompt": {...},
    "outputs": {
      "15": {
        "videos": [
          {
            "filename": "generated-video_00001_.mp4",
            "subfolder": "",
            "type": "output"
          }
        ]
      }
    },
    "status": {
      "status_str": "success",
      "completed": true,
      "messages": [
        ["execution_start", {"prompt_id": "...", "timestamp": 1770134781023}],
        ["execution_success", {"prompt_id": "...", "timestamp": 1770135547358}]
      ]
    }
  }
}
```

---

### 4. Download Generated Video

**Endpoint:** `GET /view?filename={filename}&type=output&subfolder=`

**Description:** Download the generated video file.

**Headers:**
```
Authorization: Bearer <token>
```

**Example:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://185.150.27.254:8188/view?filename=generated-video_00001_.mp4&type=output&subfolder=" \
  -o video.mp4
```

**Response:** Binary video file (MP4)

---

### 5. Cancel Job

**Endpoint:** `POST /interrupt`

**Description:** Cancel the currently running job.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{}
```

---

### 6. Clear Queue

**Endpoint:** `POST /queue`

**Description:** Clear all pending jobs from the queue.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "clear": true
}
```

---

## Workflow Parameters

### Key Configurable Parameters

#### Video Resolution & Length
```json
"4": {
  "inputs": {
    "width": 1920,      // Width in pixels (must be multiple of 32)
    "height": 1088,     // Height in pixels (must be multiple of 32)
    "length": 121,      // Number of frames (121 = ~5 seconds at 24fps)
    "batch_size": 1     // Number of videos to generate simultaneously
  }
}
```

**Common Resolutions:**
- `1920x1088` - 1080p (high quality, ~15 min generation)
- `1280x720` - 720p (balanced, ~10 min generation)
- `768x512` - SD (fast, ~5 min generation)

#### Text Prompts
```json
"7": {
  "inputs": {
    "text": "Detailed description of video content including visual and audio elements"
  }
},
"8": {
  "inputs": {
    "text": "Negative prompt: things to avoid (blurry, low quality, etc.)"
  }
}
```

#### Generation Quality
```json
"10": {
  "inputs": {
    "seed": 42,           // Random seed (change for variations)
    "steps": 30,          // More steps = better quality (20-50 recommended)
    "cfg": 5.0,          // Prompt adherence (3.0-7.0, higher = stronger)
    "sampler_name": "euler",
    "scheduler": "simple",
    "denoise": 1
  }
}
```

**Quality Settings:**
- **Fast:** steps=20, cfg=4.0
- **Balanced:** steps=30, cfg=5.0
- **High Quality:** steps=40, cfg=6.0

#### Audio Settings
```json
"5": {
  "inputs": {
    "frames_number": 121,  // Must match video length
    "frame_rate": 24,      // Audio sync (24 or 25 fps)
    "batch_size": 1
  }
}
```

#### Output Settings
```json
"15": {
  "inputs": {
    "filename_prefix": "my-video",  // Output filename prefix
    "format": "mp4",                // Video format
    "codec": "h264"                 // Video codec
  }
}
```

---

## Complete Example Workflows

### Example 1: Simple 720p Video with Audio

```bash
curl -H "Authorization: Bearer <YOUR_BEARER_TOKEN>" \
  -H "Content-Type: application/json" \
  -X POST http://185.150.27.254:8188/prompt \
  -d @- << 'EOF'
{
  "prompt": {
    "1": {"inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"}, "class_type": "CheckpointLoaderSimple"},
    "2": {"inputs": {"gemma_path": "gemma-3-12b-it-qat-q4_0-unquantized/model-00001-of-00005.safetensors", "ltxv_path": "ltx-2-19b-distilled.safetensors", "max_length": 1024}, "class_type": "LTXVGemmaCLIPModelLoader"},
    "3": {"inputs": {"ckpt_name": "ltx-2-19b-distilled.safetensors"}, "class_type": "LTXVAudioVAELoader"},
    "4": {"inputs": {"width": 1280, "height": 720, "length": 121, "batch_size": 1}, "class_type": "EmptyLTXVLatentVideo"},
    "5": {"inputs": {"frames_number": 121, "frame_rate": 24, "batch_size": 1, "audio_vae": ["3", 0]}, "class_type": "LTXVEmptyLatentAudio"},
    "6": {"inputs": {"video_latent": ["4", 0], "audio_latent": ["5", 0]}, "class_type": "LTXVConcatAVLatent"},
    "7": {"inputs": {"text": "A cat playing piano in a cozy living room. The cat's paws press the keys creating a gentle melody. Soft piano music fills the room.", "clip": ["2", 0]}, "class_type": "CLIPTextEncode"},
    "8": {"inputs": {"text": "blurry, low quality, silent, no sound", "clip": ["2", 0]}, "class_type": "CLIPTextEncode"},
    "9": {"inputs": {"positive": ["7", 0], "negative": ["8", 0], "frame_rate": 24}, "class_type": "LTXVConditioning"},
    "10": {"inputs": {"seed": 12345, "steps": 25, "cfg": 4.5, "sampler_name": "euler", "scheduler": "simple", "denoise": 1, "model": ["1", 0], "positive": ["9", 0], "negative": ["9", 1], "latent_image": ["6", 0]}, "class_type": "KSampler"},
    "11": {"inputs": {"av_latent": ["10", 0]}, "class_type": "LTXVSeparateAVLatent"},
    "12": {"inputs": {"samples": ["11", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
    "13": {"inputs": {"samples": ["11", 1], "audio_vae": ["3", 0]}, "class_type": "LTXVAudioVAEDecode"},
    "14": {"inputs": {"fps": 24, "images": ["12", 0], "audio": ["13", 0]}, "class_type": "CreateVideo"},
    "15": {"inputs": {"filename_prefix": "cat-piano", "format": "mp4", "codec": "h264", "video": ["14", 0]}, "class_type": "SaveVideo"}
  }
}
EOF
```

### Example 2: Batch Generation (2 Variations)

Change these parameters:
- `"batch_size": 2` in nodes 4 and 5
- Different `"seed"` values will create variations

### Example 3: Monitor and Download

```bash
#!/bin/bash

TOKEN="<YOUR_BEARER_TOKEN>"
BASE_URL="http://185.150.27.254:8188"

# Submit job
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "$BASE_URL/prompt" \
  -d @workflow.json)

PROMPT_ID=$(echo "$RESPONSE" | jq -r '.prompt_id')
echo "Job ID: $PROMPT_ID"

# Monitor until complete
while true; do
  QUEUE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/queue")
  RUNNING=$(echo "$QUEUE" | jq '.queue_running | length')

  if [ "$RUNNING" = "0" ]; then
    break
  fi

  echo "Still generating..."
  sleep 10
done

# Get result filename
HISTORY=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/history/$PROMPT_ID")
FILENAME=$(echo "$HISTORY" | jq -r ".\"$PROMPT_ID\".outputs.\"15\".videos[0].filename")

echo "Generated: $FILENAME"

# Download video
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/view?filename=$FILENAME&type=output&subfolder=" \
  -o "$FILENAME"

echo "Downloaded to: $FILENAME"
```

---

## Generation Times

**Estimates on A100 40GB:**

| Resolution | Steps | Batch | Time |
|------------|-------|-------|------|
| 768x512 | 20 | 1 | ~5 min |
| 1280x720 | 30 | 1 | ~10 min |
| 1920x1088 | 30 | 1 | ~13 min |
| 1920x1088 | 40 | 1 | ~17 min |
| 1920x1088 | 30 | 2 | ~16 min |

---

## Error Handling

### Common Errors

**401 Unauthorized**
```json
{"error": "Unauthorized"}
```
Solution: Check bearer token is correct

**Node Errors**
```json
{
  "prompt_id": "...",
  "node_errors": {
    "4": {
      "errors": [{"message": "Invalid dimensions", "details": "..."}]
    }
  }
}
```
Solution: Check workflow parameters (dimensions must be multiples of 32)

**Job Failed**
Check history endpoint for error messages in the status field.

---

## Rate Limiting

- Only 1 job can run at a time (single GPU)
- Additional jobs are queued automatically
- Use `GET /queue` to check queue length

---

## Best Practices

1. **Start with lower resolutions** (720p) for testing
2. **Use batch_size=2-4** to get multiple variations in one run
3. **Monitor queue** before submitting multiple jobs
4. **Download videos immediately** - TTL cleanup script deletes videos after 10 minutes
5. **Use descriptive filename_prefix** to identify your videos
6. **Include audio descriptions in prompts** - LTX-2 generates synchronized audio

---

## Models Available

- **Video Model:** `ltx-2-19b-distilled.safetensors` (41GB, BF16)
- **Text Encoder:** `gemma-3-12b-it-qat-q4_0-unquantized` (23GB, quantized)
- **Audio VAE:** Built into LTX-2 checkpoint
- **Video VAE:** Built into LTX-2 checkpoint

---

## Support

For issues or questions about this API, check the ComfyUI logs:
```bash
ssh -p 30261 root@185.150.27.254 "tail -f /workspace/logs/comfyui.log"
```
