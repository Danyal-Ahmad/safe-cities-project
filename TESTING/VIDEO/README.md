# SAFE CITIES PROJECT - Fresh Pipeline Dry-Run (2026-11-07)

This folder holds the current test videos and the recorded results of the
official enforcement-pipeline dry run:

**DETECTION -> FRAME TRACKING -> EVIDENCE (5 hard security checks) -> CHALLAN**

Everything below was produced by the real stack: ONNX plate detector +
side classifier, Tesseract OCR (multi-pass, 96px upscale), the strict
3-frame evidence collector, the 5-check security gate and the challan PDF
service. No values are hand-written.

## Videos

| File | Purpose | Details |
| --- | --- | --- |
| `positive_violation_KHI-7788_1080p30.mp4` | **Positive test** - must end in an auto-issued challan | 1920x1080, 30fps, 8s. Car rear with a fully visible plate `KHI-7788` (Karachi registered series) approaching a `violation_side=back` camera (wrong-way). |
| `negative_cutplate_1080p30.mp4` | **Strictness test** - must NOT produce a challan | Same scene, but the plate sits on the right frame edge and is half cut. The strict full-plate rule must refuse issuance and park the detections in the officer review queue. |

## Dry-Run Procedure

1. Camera `CAM-E2E-01` (Fresh Dry-Run Overpass, Lahore) enrolled with
   `violation_side=back`, `legal_direction=N`, `capture_interval=1s`.
2. Both videos uploaded through the video-processor channel
   (`/portal/officer/video-upload/` flow) as the IT-Support account.
3. The processor samples one frame per second and captures a 2-frame
   sequential burst on every plate hit (3-frame evidence per detection).
4. Every detection runs the 5 hard security checks; only a full pass
   auto-issues a challan, everything else is queued for officer review.

## Recorded Results - 2026-11-07

### Positive test - `positive_violation_KHI-7788_1080p30.mp4`

```
frames sampled    : 8 (one per second)
plates detected   : 8/8
plate             : KHI-7788  (valid PK format, known Karachi series)
side              : back (classifier confidence 0.90-0.96)
OCR               : KHI-7788 in every sampled frame (Tesseract multi-pass, conf 0.70)
track             : TRK-5-KHI-0007, consistency 1.00, 3/3 corroborated frames

security checks (all recorded on Detection #7):
  1. plate_readability   PASSED  plate=KHI-7788 pk_format=ok known_series=yes ocr_conf=0.70 (min 0.60)
  2. frame_consistency   PASSED  corroborated_track frames=3/3 per_frame_1by1=ok consistency=1.00 (min 0.80)
  3. violation_logic     PASSED  side=back/1.00 legal_dir=n moving_dir=n vehicle_class=car car_gate=passed
  4. image_evidence      PASSED  raw_image + plate_crop present, plate complete (no half/cut plates)
  5. chain_integrity     PASSED  chain_hash=511b4f17b5c0d989... duplicate_24h=no

challan           : ticket 202600007, PKR 750, wrong-way, auto-issued
PDF               : single A4 page, evidence image + SHA-256 chain hash + QR + bank barcode
                    (results/fresh_challan_202600007.pdf)
duplicates        : the 7 later frames of the same plate were correctly refused a second
                    challan by the 24h duplicate rule and parked in the review queue
```

### Strictness test - `negative_cutplate_1080p30.mp4`

```
frames sampled    : 8
plates detected   : 8/8 (the plate region is visible)
OCR plate         : refused in every frame (half-cut plate cannot produce a full read)
violations        : 0
challans          : 0
detections        : 8 parked in the officer review queue
                    (results/fresh_evidence_frame_negative_cutplate.jpg)
```

## Artifacts

| File | What it is |
| --- | --- |
| `results/fresh_challan_202600007.pdf` | The auto-generated challan PDF (1 A4 page, QR + evidence + chain hash + bank barcode) |
| `results/fresh_evidence_frame_positive.jpg` | Full evidence frame for the confirmed violation |
| `results/fresh_plate_crop_KHI-7788.jpg` | The plate crop used for OCR |
| `results/fresh_evidence_frame_negative_cutplate.jpg` | Sample refused frame (plate cut at the edge) |

## Recorded Walkthrough - `system_walkthrough_2026-11-07.mp4`

A 118-second screen recording of the live system (all actions real, nothing staged):

1. Public portal: challan search by plate + CNIC -> ticket 202600007 (KHI-7788) found
2. Citizen portal (CNIC login): dashboard KPIs, e-challan ledger, appeal tracker
3. SSP portal: command dashboard, mistake-challan appeals queue, live APPROVE decision
   on appeal #3 -> challan 202600007 auto-voided during the recording
4. DIG portal: command dashboard, evidence-integrity board (5 security checks per
   detection), analytics, login-events usage board
5. Officer portal: dashboard + review queue (the refused cut-plate detections)
6. IT-Support portal: dashboard, payment-transaction monitor, camera heartbeat board
