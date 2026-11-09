# Safe City - Architecture Notes

This document preserves the design rationale that used to live as inline comments
in the source files. The codebase itself is kept comment-free by policy.

## Web stack (wrongway_system/settings.py)

- PostgreSQL is the only supported database. At import time the settings probe the
  configured server; if unreachable, the process exits with a clear message instead
  of failing later inside a request.
- WhiteNoise serves `/static/` from the `staticfiles/` manifest with immutable
  cache headers for fingerprinted assets. `_GracefulManifestStaticFilesStorage`
  degrades to plain storage when a manifest entry is missing instead of raising.
- CSP is applied in `SecurityHeadersMiddleware`: `default-src 'self'` plus
  `img-src 'self' data:` and the exact CDN origins used by the theme
  (Bootstrap Icons, Leaflet, Chart.js). Inline script/style is allowed because
  several templates embed per-page JSON payloads; tightening this requires
  moving those payloads to static JS files with nonce support.
- Argon2 is the password hasher; sessions use signed cookies; CSRF cookie is
  `SameSite=Lax`.

## Realtime layer (realtime/)

- `realtime_events.py` is the single publish API (`emit_portal_notification`,
  `emit_detection`, ...). Views never touch Socket.IO directly.
- The Socket.IO server (ASGI, uvicorn) is optional at runtime: when the client
  cannot connect, every page falls back to polling the REST endpoints under
  `/realtime/api/`. This is why all emitters are wrapped in defensive try/except
  blocks - a dead socket server must never break a view.
- The same JSON shapes are used by both transports, so the dashboard JS is
  transport-agnostic.

## Challan PDF service (challans/pdf_service.py)

- Every challan renders as exactly one A4 page. Page count is verified with
  `pypdf`; on overflow the render is retried with the compact template and
  finally with the ReportLab single-page fallback.
- Exactly one large evidence image is rendered: the annotated full-frame capture
  (violation box, plate box, direction arrow) from `Detection.annotated_image`,
  falling back to the raw frame.
- Payment channels are rendered as SVG icons, never text.
- The bank barcode is a short Code128 payload on a white background so branch
  scanners read it reliably.

## Enforcement pipeline (detections/)

- Order: DETECTION (ONNX plate detector + side classifier) -> FRAME TRACKING
  (3 sequential frames, same full plate) -> EVIDENCE (5 hard security checks:
  plate_readability, frame_consistency, violation_logic, image_evidence,
  chain_integrity with SHA-256 chaining and 24h duplicate suppression) ->
  CHALLAN auto-issuance into the active PDF template.
- Any failed check parks the detection in the officer review queue instead of
  issuing a challan.
- `run_auto_blacklist` fires after each auto-issued challan: plates at or above
  the configured unpaid-challan threshold are blacklisted automatically.

## Appeals flow (appeals/)

- Single-stage: citizen submits -> SSP decides (approve voids the challan,
  reject leaves it active). DIG, supervisors and audit roles have read-only
  visibility. There is no escalation stage.
