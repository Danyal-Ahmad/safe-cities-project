import os
import tempfile

from django.test import TestCase
from PIL import Image
import numpy as np

from accounts.models import User
from cameras.models import Camera
from challans.models import Challan
from detections.models import Detection, DetectionReviewNote
from detections.pipeline import (
    process_detection,
    build_evidence,
    frame_tracking,
)


class PipelineBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.camera = Camera.objects.create(
            camera_id='CAM-T1', location='Test Road', legal_direction='N',
            violation_side='back', auto_confirm_threshold=0.70,
            is_active=True, is_enrolled=True, health_status='online',
        )

    @staticmethod
    def _image_file(seed=1, size=(640, 480)):
        arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        arr[:, :, seed % 3] = 120
        arr[100:140, 250:400] = 255
        img = Image.fromarray(arr)
        tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        img.save(tmp, format='JPEG', quality=90)
        tmp.close()
        return open(tmp.name, 'rb')

    def _make_detection(self, plate='LEA-1100', ocr=0.92, side_conf=0.9,
                        plate_conf=0.93, violation=True, camera=None,
                        frame_evidence=None):
        raw = {
            'side_confidence': side_conf,
            'plate_confidence': plate_conf,
            'ocr_confidence': ocr,
            'vehicle_class': 'car',
            'plate_complete': True,
            'plate_format_ok': True,
            'plate_detections': [{'bbox': [10, 10, 100, 40], 'confidence': plate_conf}],
        }
        if frame_evidence is None:
            frame_evidence = [
                {'plate': plate, 'confidence': plate_conf, 'ocr_confidence': ocr,
                 'timestamp': f'{i}.00{s}', 'plate_complete': True}
                for i, s in enumerate(('100', '133', '167'), start=1)
            ]
        if frame_evidence:
            raw['frame_evidence'] = frame_evidence
        d = Detection(
            camera=camera or self.camera,
            ai_plate_text=plate,
            ai_side_classification='back',
            ai_confidence=plate_conf,
            ai_detected_violation=violation,
            ai_raw_response=raw,
            status=Detection.PENDING,
        )
        fh = self._image_file()
        d.raw_image.save('t.jpg', fh, save=False)
        d.plate_crop_image.save('t_crop.jpg', fh, save=False)
        fh.close()
        os.unlink(fh.name)
        d.save()
        return d

    def _run(self, d, **kw):
        return process_detection(
            d,
            {'detected_violation': kw.get('violation', True),
             'confidence': kw.get('conf', d.ai_confidence),
             'raw_ai_response': d.ai_raw_response},
            camera=kw.get('camera', self.camera),
        )


class HappyPathTests(PipelineBase):
    def test_all_five_checks_pass_issues_challan(self):
        d = self._make_detection()
        det, challan, action = self._run(d)
        self.assertEqual(action, 'challan_issued')
        self.assertEqual(det.status, Detection.CONFIRMED)
        self.assertIsNotNone(challan)
        self.assertEqual(len(det.evidence_checks), 5)
        self.assertTrue(all(c['passed'] for c in det.evidence_checks))
        self.assertGreaterEqual(det.track_frames, 3)
        self.assertTrue(det.evidence_hash and len(det.evidence_hash) == 64)
        self.assertEqual(Challan.objects.filter(detection=det).count(), 1)

    def test_evidence_summary_property(self):
        d = self._make_detection()
        det, _, _ = self._run(d)
        s = det.evidence_summary
        self.assertEqual(s['passed'], 5)
        self.assertEqual(s['total'], 5)
        self.assertTrue(s['all_passed'])
        self.assertEqual(det.failed_evidence_checks, [])


class EvidenceCheckTests(PipelineBase):
    def test_bad_ocr_queues_review(self):
        d = self._make_detection(plate='Z9', ocr=0.2)
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        self.assertEqual(det.status, Detection.PENDING)
        self.assertIsNone(challan)
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('plate_readability', failed)

    def test_unconfirmed_track_queues_review(self):
        d = self._make_detection(plate_conf=0.62, ocr=0.62, frame_evidence=[])
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        self.assertIsNone(challan)
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('frame_consistency', failed)

    def test_no_violation_flag_blocks_challan(self):
        d = self._make_detection(violation=False)
        d.ai_detected_violation = False
        det, challan, action = self._run(d, violation=False)
        self.assertIn(action, ('queued_review', 'ignored'))
        self.assertIsNone(challan)

    def test_duplicate_plate_within_24h_is_blocked(self):
        d1 = self._make_detection(plate='DUP-100')
        det1, ch1, a1 = self._run(d1)
        self.assertEqual(a1, 'challan_issued')
        d2 = self._make_detection(plate='DUP-100')
        det2, ch2, a2 = self._run(d2)
        self.assertEqual(a2, 'queued_review')
        self.assertIsNone(ch2)
        chain = [c for c in det2.evidence_checks if c['check'] == 'chain_integrity'][0]
        self.assertFalse(chain['passed'])
        self.assertIn('duplicate', chain['detail'])

    def test_corroborated_track_two_frames(self):
        d1 = self._make_detection(plate='TRK-200', frame_evidence=[])
        self._run(d1)
        d2 = self._make_detection(plate='TRK-200', frame_evidence=[])
        det2, _, a2 = self._run(d2)
        self.assertEqual(det2.track_frames, 2)
        self.assertGreaterEqual(det2.track_consistency, 0.5)

    def test_burst_evidence_counts_frames(self):
        d = self._make_detection(plate='LES-500')
        det, _, action = self._run(d)
        self.assertEqual(det.track_frames, 3)
        self.assertEqual(action, 'challan_issued')

    def test_track_window_excludes_old_frames(self):
        from django.utils import timezone
        import datetime
        old = self._make_detection(plate='OLD-300', frame_evidence=[])
        Detection.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - datetime.timedelta(seconds=120))
        fresh = self._make_detection(plate='OLD-300', frame_evidence=[])
        det, ch, action = self._run(fresh, conf=0.8)
        self.assertEqual(det.track_frames, 1)


class StrictPolicyTests(PipelineBase):

    def test_two_frame_evidence_is_not_enough(self):
        ev2 = [{'plate': 'LEA-1100', 'confidence': 0.9, 'ocr_confidence': 0.9,
                'timestamp': '1.0', 'plate_complete': True}] * 2
        d = self._make_detection(plate='LEA-1100', frame_evidence=ev2)
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        self.assertIsNone(challan)
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('frame_consistency', failed)

    def test_mismatched_frame_plates_fail(self):
        ev = [{'plate': 'LEA-1100', 'confidence': 0.9, 'ocr_confidence': 0.9,
               'timestamp': '1.0', 'plate_complete': True},
              {'plate': 'LEA-9999', 'confidence': 0.9, 'ocr_confidence': 0.9,
               'timestamp': '2.0', 'plate_complete': True},
              {'plate': 'LEA-1100', 'confidence': 0.9, 'ocr_confidence': 0.9,
               'timestamp': '3.0', 'plate_complete': True}]
        d = self._make_detection(plate='LEA-1100', frame_evidence=ev)
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('frame_consistency', failed)

    def test_non_pk_plate_format_fails_readability(self):
        d = self._make_detection(plate='ABCD-12')
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('plate_readability', failed)

    def test_non_car_vehicle_is_rejected(self):
        d = self._make_detection()
        raw = dict(d.ai_raw_response)
        raw['vehicle_class'] = 'truck'
        d.ai_raw_response = raw
        d.save()
        det, challan, action = self._run(d)
        self.assertEqual(action, 'ignored')
        self.assertEqual(det.status, Detection.REJECTED)
        self.assertIn('car', det.review_notes)

    def test_half_cut_plate_fails_image_evidence(self):
        d = self._make_detection()
        raw = dict(d.ai_raw_response)
        raw['plate_complete'] = False
        raw['plate_edge_clipped'] = True
        d.ai_raw_response = raw
        d.save()
        det, challan, action = self._run(d)
        self.assertEqual(action, 'queued_review')
        failed = {c['check'] for c in det.evidence_checks if not c['passed']}
        self.assertIn('image_evidence', failed)


class TamperEvidenceTests(PipelineBase):
    def test_hash_is_deterministic(self):
        d = self._make_detection(plate='HSH-400')
        d.save()
        checks, h1 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        _, h2 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        self.assertEqual(h1, h2)

    def test_hash_changes_when_plate_changes(self):
        d = self._make_detection(plate='AAA-111')
        d.save()
        _, h1 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        d.ai_plate_text = 'BBB-222'
        _, h2 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        self.assertNotEqual(h1, h2)

    def test_hash_changes_when_image_changes(self):
        d = self._make_detection(plate='IMG-500')
        d.save()
        _, h1 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        fh = self._image_file(seed=3)
        d.raw_image.save('t2.jpg', fh, save=False)
        fh.close()
        os.unlink(fh.name)
        _, h2 = build_evidence(d, frame_tracking(d, self.camera), self.camera)
        self.assertNotEqual(h1, h2)


class RemovedFeatureTests(PipelineBase):
    def test_annotation_model_is_gone(self):
        from detections.models import Detection as D
        self.assertFalse(hasattr(D(), 'manual_plate_text'))
        self.assertFalse(hasattr(D(), 'is_manually_annotated'))
        import detections.models as dm
        self.assertFalse(hasattr(dm, 'Annotation'))

    def test_no_challan_without_pipeline(self):
        d = self._make_detection(plate='NOP-600', ocr=0.2, side_conf=0.2, plate_conf=0.3)
        det, challan, action = self._run(d, conf=0.3)
        self.assertEqual(action, 'queued_review')
        self.assertEqual(Challan.objects.filter(detection=det).count(), 0)


class ReviewNoteTests(PipelineBase):
    def test_review_note_model(self):
        u = User.objects.create_user(username='noteuser', password='x' * 16)
        d = self._make_detection()
        DetectionReviewNote.objects.create(detection=d, author=u, note='test note')
        self.assertEqual(d.review_notes_list.count(), 1)
