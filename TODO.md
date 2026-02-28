# voice_clone_studio TODO

## Current
- Fill in real local paths and RVC values inside `config/settings.json`
- Run the first real `XTTS` synthesis in the user's terminal so model weights can download and cache
- Replace the passthrough RVC script with a real local RVC runtime
- Test the new local web UI end-to-end with a real reference voice
- Test a real user video upload after the new ffmpeg retry/error reporting changes
- Run the first real XTTS web generation after saving the Coqui TOS marker
- Repair the local env back to `numpy==1.22.0` and `transformers==4.41.2`, then rerun XTTS generation
- Verify real XTTS generation after the `torch.load(weights_only=False)` compatibility patch
- Verify real XTTS generation after the `torchaudio.load -> soundfile` fallback patch
## Next Task Format
- Feature:
- Target file(s):
- Notes:

## Done Recently
- Created a local starter project structure for `XTTS + RVC`
- Added CLI flow for reference voice registration and synthesis commands
- Added a default `config/settings.json` so local values can be filled in directly
- Added `serve-web` and a simple Flask UI on top of the pipeline
- Added a concrete local `tools/rvc_passthrough.py` runtime so `convert` can run end-to-end before real RVC is installed
- Added multi-file dataset upload in the web UI for audio and video files
- Added per-profile training dataset storage and manifest tracking
- Added automatic `ffmpeg` video-to-audio extraction during dataset upload when available
- Added clearer ffmpeg retry/error reporting for failed video extraction
- Added explicit Coqui XTTS TOS acceptance flow for web and CLI
- Pinned `transformers<5` in project requirements for XTTS compatibility
- Added project memory and setup notes for this PC
- Added a recent outputs section in the web UI with inline audio playback, latest-file highlighting, and download links
- Added automatic XTTS reference prep (`reference_xtts.wav`) and stronger text chunking for more stable pronunciation
- Installed `ffmpeg` in the `voiceclone310` env so `.m4a` references can be converted for XTTS
- Tuned reference prep and relaxed text chunking after the first pass sounded too distorted/robotic
- Switched Korean XTTS away from the outer English sentence splitter and onto XTTS's own text splitting while reverting unstable custom decode overrides
- Switched XTTS to use multi-reference conditioning (`reference.wav` + extra training clips) to improve pronunciation stability
- Tuned current Korean prosody baseline to `temperature 0.32` and `speed 0.94` after pronunciation became stable
