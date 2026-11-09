import os
import tempfile

from django.test import TestCase

from accounts.models import User
from cameras.models import Camera
from challans.models import Challan
from detections.models import Detection
from video_processor.models import VideoUpload


class VideoPipelineDryRunTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.it_user = User.objects.create(
            username='itvideo@t.fyp', email='itvideo@t.fyp', role='IT', is_active=True)
        cls.it_user.set_password('Passw0rd!Long123')
        cls.it_user.save()
        cls.camera = Camera.objects.create(
            camera_id='CAM-VID', location='Video Road', legal_direction='N',
            violation_side='back', auto_confirm_threshold=0.70,
            is_active=True, is_enrolled=True, health_status='online')

    @staticmethod
    def _make_video(path, frames=30, fps=10):
        import cv2
        import numpy as np
        w, h = 640, 480
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
        for i in range(frames):
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :, 0] = 40 + (i * 5) % 200
            frame[200:260, 260:420] = 255
            cv2.putText(frame, 'LEA-1100', (250, 230),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            writer.write(frame)
        writer.release()

    def test_video_upload_processing_dry_run(self):
        from cameras.video_processing import process_video_upload
        tmp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        tmp.close()
        self._make_video(tmp.name, frames=30, fps=10)
        from django.core.files import File as DjFile
        upload = VideoUpload.objects.create(
            camera=self.camera,
            video_file=DjFile(open(tmp.name, 'rb'), name='dryrun.mp4'),
            original_filename='dryrun.mp4',
            uploaded_by=self.it_user,
            camera_location=self.camera.location,
        )
        os.unlink(tmp.name)
        process_video_upload(upload.pk)
        upload.refresh_from_db()
        self.assertEqual(upload.status, VideoUpload.STATUS_COMPLETED)
        self.assertGreater(upload.total_frames_extracted, 0)

        detections = Detection.objects.filter(source_video_upload=upload)
        self.assertTrue(detections.exists())
        for d in detections:
            self.assertIn(d.status, (Detection.CONFIRMED, Detection.PENDING, Detection.REJECTED))
            self.assertIsNotNone(d.evidence_checks or None)
        issued = [d for d in detections if d.status == Detection.CONFIRMED]
        for d in issued:
            self.assertEqual(len(d.evidence_checks), 5)
            self.assertTrue(all(c['passed'] for c in d.evidence_checks))
            self.assertIsNotNone(d.evidence_hash)
            challans = Challan.objects.filter(detection=d)
            self.assertEqual(challans.count(), 1)
            for ch in challans:
                self.assertTrue(ch.pdf_file.name)

    def test_upload_view_scopes_officer_cameras(self):
        from django.test import Client
        officer = User.objects.create(
            username='offvid@t.fyp', email='offvid@t.fyp', role='OFFICER', is_active=True)
        officer.set_password('Passw0rd!Long123')
        officer.save()
        c = Client()
        c.force_login(officer)
        r = c.get('/video/upload/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('CAM-VID', r.content.decode())

    def test_upload_list_is_it_only(self):
        from django.test import Client
        c = Client()
        c.force_login(self.it_user)
        self.assertEqual(c.get('/video/uploads/').status_code, 200)
        c2 = Client()
        c2.force_login(self.officer_admin_stub())
        r = c2.get('/video/uploads/')
        self.assertEqual(r.status_code, 302)

    @staticmethod
    def officer_admin_stub():
        u = User.objects.filter(role='OFFICER').first()
        if u is None:
            u = User.objects.create(
                username='offstub@t.fyp', email='offstub@t.fyp', role='OFFICER', is_active=True)
        return u

