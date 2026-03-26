# Scripts

## Diagnostics
- `collect_diagnostics.sh` - System diagnostics for troubleshooting
- `test_pipewire_v4l2loopback.sh` - Tests `/dev/videoX` loopback via PipeWire (`pipewiresrc`)

## OBS Testing (Firefox Compatibility)

### Quick Test
```bash
./test_obs_quick.py
```
Automated readiness check (~2 seconds):
- Verifies OBS installed
- Checks v4l2loopback device available
- Tests all dependencies

### Full Test
```bash
./test_obs_full.sh
```
Interactive workflow test (~5 minutes):
- Starts camfx
- Opens OBS
- Guides through configuration
- Verifies virtual camera creation

## More Info
See `docs/firefox-compatibility-investigation.md` for full details on Firefox/browser compatibility and why we recommend OBS Studio as a bridge.

