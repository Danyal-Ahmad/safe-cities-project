# SAFE CITIES PROJECT - Testing Video Assets & Dry-Run Results

This folder stores the official test videos used to validate the complete
enforcement pipeline **DETECTION → FRAME TRACKING → EVIDENCE (5-step secure
check) → CHALLAN**, plus the recorded results of each dry run.

## Videos

| File | Purpose | Details |
| --- | --- | --- |
| `safecity_pipeline_test_1080p30.mp4` | **Positive test** - full pipeline must end in an auto-issued challan | 1920x1080, 30fps, 8s. Car rear with a fully visible Pakistani plate `LEA-1234` approaching the camera (wrong-way / rear view violation). |
| `real_traffic_1080p30.mp4` | **Negative / strictness test** - real city traffic | 1920x1080, 30fps, 59s. Mixed traffic; the only readable plate (`ACR-59`) is half cut by the frame edge, so the strict full-plate rule must refuse a challan. |

## Dry-Run Procedure

1. IT Support uploads the video at `/portal/officer/video-upload/` (or via
   the video processor API) linked to an enrolled camera with
   `violation_side=back` and a legal direction set.
2. The processor samples frames every `capture_interval` seconds.
3. On a candidate violation frame the processor captures a **90fps-density
   burst** of consecutive frames and verifies the plate **one-by-one** in at
   least **3 frames**.
4. The 5 hard security checks run:
   1. `plate_readability` - Pakistan plate format `AAA-1234` + HD OCR confidence ≥ 0.60
   2. `frame_consistency` - 3-frame evidence, same full plate in every frame, consistency ≥ 0.80
   3. `violation_logic` - wrong-way direction + strict **car-only gate**
   4. `image_evidence` - full plate crop (no half/cut plates), usable resolution
   5. `chain_integrity` - SHA-256 tamper-evident chain, no 24h duplicates
5. All 5 pass → challan issued automatically; otherwise the detection is
   parked in the Officer Portal review queue.

## Recorded Results

### Positive test - `safecity_pipeline_test_1080p30.mp4`

```
plate              : LEA-1234  (valid PK format, known registered series)
side               : back (confidence 0.99)
plate detector     : confidence 0.95, plate complete (not clipped)
OCR (HD)           : LEA-1234, confidence 0.98–1.00 (EasyOCR, 96px upscaled multi-pass)
3-frame evidence   : frames at 0.000s / 0.033s / 0.067s, all plates match, all complete
checks             : 5/5 PASSED
challan            : ticket 202600007, PKR 500, wrong-way, auto-issued
PDF                : generated with the active template + QR + evidence images + chain hash
```

### Strictness test - `real_traffic_1080p30.mp4`

```
frames sampled     : 12
plates detected    : 3
best read          : ACR-59 (OCR conf 0.62) at t=50s
full-plate check   : FAILED - plate half cut by the right frame edge
result             : detection parked in the officer review queue (no challan) - the strict
                     "no half / cut plates" rule behaved exactly as required
side classifier    : back (0.999) - replaced defective INT8 export, see note
```

## Side-classifier replacement note

The repository's original `car_side_Classifier_model_int8.onnx` produced a
constant `0.0` output for every input (defective INT8 quantized export -
`onnx.infer: onnxruntime.quant`). It was replaced with a freshly trained
CNN (MobileNet-style, ~99% train accuracy, holdout-verified) exported with
the identical runtime signature (`input` [N,224,224,3] in [-1,1] → `dense`
[N,1] sigmoid back-probability). No pipeline code changes were required.

## Flow re-test 2026-11-05 - full pipeline, live database

Re-ran the complete pipeline on the development database with a synthetic
1080x720 12fps clip (`flow_retest_720p12.mp4`, plate `LEA-1001`, registered
owner linked from the local vehicle registry):

```
upload status      : COMPLETED
frames extracted   : > 0, burst evidence collected
detection          : confirmed, vehicle class car-only gate PASS
evidence checks    : 5/5 PASSED (plate_readability, frame_consistency,
                    violation_logic, image_evidence, chain_integrity)
evidence hash      : SHA-256 recorded on the detection
challan            : ticket 202600002, PKR 500, wrong-way, auto-issued
owner              : linked from registration (name, CNIC, phone, make, color)
PSID               : generated
PDF                : built with the active template
artifacts          : results/flow_retest_challan_202600002.pdf
                    results/flow_retest_plate_2.jpg
```

All 16 checks passed. The public search (`/?plate=LEA-1001&cnic=...`) finds
the challan, the detail page masks owner identity for guests, the guest pay
flow routes through the gateway, and invalid signed links render the
expired-link page with HTTP 403.

## Reproducing

```bash
python manage.py test detections challans auth_portal accounts admin.audit_portal
```

The unit suite includes the strict-policy tests (2-frame evidence must fail,
mismatched frame plates must fail, non-PK plates must fail, non-car vehicles
must be rejected, half plates must fail image evidence).
