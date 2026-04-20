---
name: bilibili
description: Run the full ai_vanvan Bilibili pipeline (Instagram download → merge → upload to Bilibili)
allowed-tools: Bash
---

Run the full ai_vanvan pipeline in the background and stream its output.

Steps:
1. Use Bash to run: `cd /Users/yanglan/Code/social-media-hub && python3 -u main.py --ai_vanvan`
   - Set timeout to 3600000ms (1 hour) since upload + review wait can take a long time
   - Run in background: false (wait for completion)
2. Parse the output and report:
   - How many videos were downloaded
   - Whether merge succeeded
   - Upload status (success / skipped / failed)
   - Video title if set
   - Whether chapter comment was posted and pinned
3. If the command fails or times out, report the error clearly.
