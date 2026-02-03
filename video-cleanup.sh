#!/bin/bash
# Video TTL cleanup script for ComfyUI LTX-2 outputs
# Automatically deletes generated videos after a specified time

# Configuration
TTL_MINUTES=${VIDEO_TTL_MINUTES:-10}  # Default: 10 minutes
CHECK_INTERVAL=${CLEANUP_CHECK_INTERVAL:-300}  # Default: 5 minutes (300 seconds)
OUTPUT_DIR="${COMFYUI_OUTPUT_DIR:-/workspace/ComfyUI/output}"
LOG_FILE="/var/log/video-cleanup.log"

# File patterns to clean up
FILE_PATTERNS=("*.mp4" "*.avi" "*.mov" "*.webm" "*.mkv")

echo "$(date): Video cleanup script started" >> "$LOG_FILE"
echo "$(date): TTL set to $TTL_MINUTES minutes" >> "$LOG_FILE"
echo "$(date): Check interval: $CHECK_INTERVAL seconds" >> "$LOG_FILE"
echo "$(date): Output directory: $OUTPUT_DIR" >> "$LOG_FILE"

cleanup_videos() {
    local deleted_count=0
    local total_size=0

    for pattern in "${FILE_PATTERNS[@]}"; do
        # Find and delete files older than TTL_MINUTES
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
                rm -f "$file"
                if [ $? -eq 0 ]; then
                    ((deleted_count++))
                    ((total_size+=size))
                    echo "$(date): Deleted $file ($(numfmt --to=iec-i --suffix=B $size 2>/dev/null || echo "${size}B"))" >> "$LOG_FILE"
                fi
            fi
        done < <(find "$OUTPUT_DIR" -name "$pattern" -type f -mmin +$TTL_MINUTES -print0 2>/dev/null)
    done

    if [ $deleted_count -gt 0 ]; then
        local size_human=$(numfmt --to=iec-i --suffix=B $total_size 2>/dev/null || echo "${total_size}B")
        echo "$(date): Cleanup complete - deleted $deleted_count files, freed $size_human" >> "$LOG_FILE"
    fi
}

# Main loop
while true; do
    if [ -d "$OUTPUT_DIR" ]; then
        cleanup_videos
    else
        echo "$(date): Output directory $OUTPUT_DIR does not exist, skipping..." >> "$LOG_FILE"
    fi

    # Sleep for the check interval
    sleep $CHECK_INTERVAL
done
