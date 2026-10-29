# Reproduce the Kestrel MVP

Use the build/run commands in the [README](../README.md). `tools/ci.sh build Debug`
performs build, all 32 CTest entries, seven live scenario checks, cppcheck,
source/report provenance, the M5 trace gate and a local console export. Use a
separate directory for Release: `tools/ci.sh build-release Release`.

GitHub Actions runs that script on Ubuntu 24.04 for Debug and Release on every
push and pull request. The exact commit's run and downloadable artifacts are the
hosted evidence. A console export is not hosted website publication.

## Live demo GIF

[The 30-second GIF](assets/kestrel-demo.gif) records actual UI commands and decoded
UDP telemetry at 1440×900, scaled for the README. Its sequence is boot, confirmed
NOMINAL, a five-second Command task stall, SAFE, FAULT CLEARED, then confirmed
NOMINAL recovery. The console never sends startup or retry commands by itself.

To re-record, install Playwright in a separate tools environment and make it
available to Node (for example via NODE_PATH), and install ffmpeg. Start the local
console, then run `node tools/record_console_demo.cjs`. Optional environment
variables: CONSOLE_URL (default http://127.0.0.1:8765) and CHROME_PATH (an installed
Chrome executable). The script uses UI actions, saves frames to output/demo, and
stops only its console flight. Create the GIF:

```sh
ffmpeg -y -f concat -safe 0 -i output/demo/frames.txt \
  -filter_complex "fps=4,scale=1080:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a" \
  -t 30 -loop 0 docs/assets/kestrel-demo.gif
```

Archived checkpoint playback is retained in `dashboard/archive`; it is not loaded
by the console. The independent automated mission reference remains under
`docs/verification/m5-demo`. To produce a fresh packet/CSV recording:

```sh
python3 tools/record_m5.py --output build/release/demo
```

Inspection records bind reviewed source and evidence with SHA256 hashes. Re-review
changed implementation before refreshing those records. POSIX tests do not prove
hardware deadlines or recovery from permanent scheduler failure.
