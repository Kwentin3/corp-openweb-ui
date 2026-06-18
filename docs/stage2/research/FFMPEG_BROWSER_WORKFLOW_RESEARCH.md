# FFMPEG Browser Workflow Research

## 1. Question

How should the existing browser ffmpeg workflow be embedded into the OpenWebUI contour?

## 2. Why it matters for PRD-1

PRD-1 treats the workflow as a technical asset, not an unknown experiment.

## 3. Current assumptions

- Existing project is stable on desktop and mobile.
- Research question is integration shape, not whether ffmpeg can work.
- API keys must not be sent to browser.

## 4. What to verify

- Module boundary.
- Browser memory limits.
- Supported browsers.
- Mobile behavior.
- Progress/cancel events.
- Audio blob format.
- Server-side fallback.

## 5. Sources to check

- Existing transcription project.
- OpenWebUI extension/customization options.
- Browser support and runtime constraints.

## 6. Test plan / proof plan

Run controlled proof with audio extraction from video, long file, mobile device, cancellation and retry.

## 7. Risks

- UI lockups.
- Large files.
- Browser compatibility.
- OpenWebUI upgrade friction.

## 8. Decision options

- External module.
- Isolated transcription module.
- Minimal fork-slice.
- Server-side fallback.

## 9. Recommended next step

Document existing workflow API and required integration points.

## 10. Status

Planned, existing asset not inspected in this repo.
