"""Shared JSON timeline feed for the Live Tracking trail.

Moved here (2026-11) from admin/officer_portal/views.py so every senior
portal (DIG / SSP / Supervisor / IT) keeps its Live Timeline feature
without importing officer-portal views. The officer portal itself no
longer links a timeline page: its camera access is limited to the two
approved capabilities (Review Queue + Live Tracking).
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .live_tracking import LiveTrackingService


def make_timeline_view(roles):
    """Factory: role-gated timeline feed bound to a portal's role set."""

    @require_GET
    @login_required
    def timeline_view(request):
        service = LiveTrackingService(
            user=request.user,
            selected_camera_id=request.GET.get('camera_id') or '',
            plate_query=request.GET.get('plate') or '',
            limit=60,
        )
        detections = service.get_recent_detections()

        camera_id = request.GET.get('camera_id')
        if camera_id and service.camera_not_found:
            return JsonResponse({'items': [], 'camera_not_found': True})

        items = service.serialize_detections(detections)
        return JsonResponse({
            'items': items,
            'count': len(items),
            'camera_not_found': service.camera_not_found,
        })

    timeline_view.__name__ = f'timeline_{"_".join(r.lower() for r in roles)}'
    return timeline_view
