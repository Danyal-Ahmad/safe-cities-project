from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Set



PERMISSIONS = (
    'add_camera',
    'edit_camera',
    'delete_camera',
    'toggle_camera',
    'manage_camera_assignments',
    'live_monitor_quick_add',
    'edit_system_settings',
    'manage_alerts',
    'manage_banners',
    'manage_smtp_sms',
    'view_backups',
    'manage_backups',
    'system_health',
    'system_health_monitoring',
    'view_ai_status',
    'view_ai_performance',
    'view_ai_reports',
    'ai_confidence_config',
    'ai_model_testing',
    'ai_detection_config',
    'camera_video_upload',
    'global_search',
    'manage_faq',
    'view_faq',
    'payment_integration',
    'payment_method_config',
    'payment_gateway_config',
    'challan_template_manage',
    'pdf_template_manage',
    'pdf_settings',
    'pdf_settings_manage',
    'nadra_integration',
    'excise_integration',
    'external_api_manage',
    'blacklist_rule_manage',
    'view_own_challans',
    'pay_own_challans',
    'submit_appeals',
    'escalate_appeals',
    'edit_own_profile',
    'view_detections',
    'review_detections',
    'reject_detection',
    'flag_detection',
    'add_review_note',
    'view_flagged_detections',
    'view_challans',
    'edit_challan_fine',
    'delete_challan',
    'mark_challan_paid',
    'record_payment',
    'bulk_fine_adjust',
    'approve_high_value_challan',
    'view_appeals',
    'approve_appeal',
    'reject_appeal',
    'escalate_appeal',
    'override_appeal',
    'appeal_workflow',
    'view_cameras',
    'view_camera_health',
    'camera_feed',
    'live_tracking',
    'live_tracking_timeline',
    'view_live_monitor',
    'live_monitor',
    'vehicle_tracking',
    'view_analytics',
    'view_reports',
    'generate_reports',
    'view_revenue_dashboard',
    'view_heatmap',
    'view_case_escalation',
    'view_vehicle_search',
    'view_blacklist',
    'add_to_blacklist',
    'view_admins',
    'add_admin',
    'edit_admin',
    'toggle_admin',
    'view_users',
    'edit_user',
    'toggle_user',
    'delete_user',
    'view_audit_log',
    'export_audit_log',
    'view_operational_audit',
    'view_financial_audit',
    'view_compliance',
    'view_anomaly_alerts',
    'view_penalty_config',
    'edit_penalty_config',
    'view_shifts',
    'manage_shifts',
    'view_team_performance',
    'view_officer_feedback',
    'add_officer_feedback',
    'view_officer_kpi',
    'view_officer_activity',
    'view_regional_command',
    'manage_regional_access',
    'view_notifications',
    'change_own_password',
    'officer_pki',
    'officer_profile_manage',
)
PERMISSION_SET: frozenset = frozenset(PERMISSIONS)



_IT_PERMS = {
    'challan_studio_manage',
    'audit_template_manage',
    'view_login_events',
    'view_upload_log',
    'add_camera',
    'add_officer_feedback',
    'add_review_note',
    'add_to_blacklist',
    'ai_confidence_config',
    'ai_detection_config',
    'camera_video_upload',
    'global_search',
    'manage_faq',
    'view_faq',
    'ai_model_testing',
    'appeal_workflow',
    'approve_high_value_challan',
    'blacklist_rule_manage',
    'bulk_fine_adjust',
    'camera_feed',
    'challan_template_manage',
    'change_own_password',
    'delete_camera',
    'edit_camera',
    'edit_challan_fine',
    'edit_own_profile',
    'edit_system_settings',
    'escalate_appeal',
    'escalate_appeals',
    'excise_integration',
    'export_audit_log',
    'external_api_manage',
    'flag_detection',
    'generate_reports',
    'live_monitor',
    'live_monitor_quick_add',
    'live_tracking',
    'live_tracking_timeline',
    'manage_alerts',
    'manage_backups',
    'manage_banners',
    'manage_camera_assignments',
    'manage_regional_access',
    'manage_shifts',
    'manage_smtp_sms',
    'mark_challan_paid',
    'nadra_integration',
    'officer_pki',
    'officer_profile_manage',
    'pay_own_challans',
    'payment_gateway_config',
    'payment_integration',
    'payment_method_config',
    'pdf_settings',
    'pdf_settings_manage',
    'pdf_template_manage',
    'record_payment',
    'reject_appeal',
    'reject_detection',
    'review_detections',
    'submit_appeals',
    'system_health',
    'system_health_monitoring',
    'toggle_camera',
    'vehicle_tracking',
    'view_admins',
    'view_ai_performance',
    'view_ai_reports',
    'view_ai_status',
    'view_analytics',
    'view_anomaly_alerts',
    'view_appeals',
    'view_audit_log',
    'view_backups',
    'view_blacklist',
    'view_camera_health',
    'view_cameras',
    'view_case_escalation',
    'view_challans',
    'view_compliance',
    'view_detections',
    'view_financial_audit',
    'view_flagged_detections',
    'view_heatmap',
    'view_live_monitor',
    'view_notifications',
    'view_officer_activity',
    'view_officer_feedback',
    'view_officer_kpi',
    'view_operational_audit',
    'view_own_challans',
    'view_penalty_config',
    'view_regional_command',
    'view_reports',
    'view_revenue_dashboard',
    'view_shifts',
    'view_team_performance',
    'view_users',
    'view_vehicle_search',
}

_DIG_PERMS = {
    'challan_template_select',
    'audit_template_select',
    'generate_audit_documents',
    'view_login_events',
    'view_upload_log',
    'view_evidence_hashes',
    'add_admin',
    'view_live_monitor',
    'add_officer_feedback',
    'add_review_note',
    'add_to_blacklist',
    'approve_appeal',
    'approve_high_value_challan',
    'bulk_fine_adjust',
    'change_own_password',
    'delete_challan',
    'delete_user',
    'edit_admin',
    'edit_challan_fine',
    'edit_own_profile',
    'edit_penalty_config',
    'edit_user',
    'escalate_appeal',
    'escalate_appeals',
    'export_audit_log',
    'flag_detection',
    'generate_reports',
    'manage_alerts',
    'manage_banners',
    'manage_regional_access',
    'manage_shifts',
    'mark_challan_paid',
    'officer_pki',
    'officer_profile_manage',
    'override_appeal',
    'pay_own_challans',
    'record_payment',
    'reject_appeal',
    'reject_detection',
    'review_detections',
    'submit_appeals',
    'toggle_admin',
    'toggle_user',
    'view_admins',
    'view_analytics',
    'view_anomaly_alerts',
    'view_appeals',
    'view_audit_log',
    'view_blacklist',
    'view_camera_health',
    'view_cameras',
    'view_case_escalation',
    'view_challans',
    'view_compliance',
    'view_detections',
    'view_financial_audit',
    'view_flagged_detections',
    'view_heatmap',
    'view_notifications',
    'view_officer_activity',
    'view_officer_feedback',
    'view_officer_kpi',
    'view_operational_audit',
    'view_own_challans',
    'view_penalty_config',
    'view_regional_command',
    'view_reports',
    'view_revenue_dashboard',
    'view_shifts',
    'view_team_performance',
    'view_users',
    'view_vehicle_search',
}

_SSP_PERMS = {
    'view_login_events',
    'view_evidence_hashes',
    'add_officer_feedback',
    'view_live_monitor',
    'add_review_note',
    'add_to_blacklist',
    'approve_appeal',
    'approve_high_value_challan',
    'change_own_password',
    'edit_own_profile',
    'escalate_appeal',
    'escalate_appeals',
    'export_audit_log',
    'flag_detection',
    'generate_reports',
    'override_appeal',
    'pay_own_challans',
    'reject_appeal',
    'submit_appeals',
    'view_analytics',
    'view_anomaly_alerts',
    'view_appeals',
    'view_audit_log',
    'view_blacklist',
    'view_camera_health',
    'view_cameras',
    'view_challans',
    'view_compliance',
    'view_financial_audit',
    'view_flagged_detections',
    'view_notifications',
    'view_officer_activity',
    'view_officer_feedback',
    'view_officer_kpi',
    'view_operational_audit',
    'view_own_challans',
    'view_reports',
    'view_shifts',
    'view_team_performance',
    'view_vehicle_search',
}

_SUPERVISOR_PERMS = {
    'view_evidence_hashes',
    'add_officer_feedback',
    'change_own_password',
    'edit_own_profile',
    'escalate_appeals',
    'generate_reports',
    'manage_shifts',
    'pay_own_challans',
    'submit_appeals',
    'view_blacklist',
    'view_challans',
    'view_detections',
    'view_analytics',
    'view_appeals',
    'view_live_monitor',
    'view_notifications',
    'view_officer_activity',
    'view_officer_feedback',
    'view_officer_kpi',
    'view_own_challans',
    'view_reports',
    'view_shifts',
    'view_team_performance',
    'view_vehicle_search',
}

_OFFICER_PERMS = {
    'add_review_note',
    'appeal_workflow',
    'camera_feed',
    'change_own_password',
    'edit_own_profile',
    'escalate_appeals',
    'flag_detection',
    'live_tracking',
    'live_tracking_timeline',
    'officer_pki',
    'officer_profile_manage',
    'pay_own_challans',
    'reject_detection',
    'review_detections',
    'submit_appeals',
    'vehicle_tracking',
    'view_appeals',
    'view_challans',
    'view_detections',
    'view_flagged_detections',
    'view_notifications',
    'view_own_challans',
    'view_team_performance',
}

_AUDIT_PERMS = {
    'generate_audit_documents',
    'view_login_events',
    'view_upload_log',
    'view_evidence_hashes',
    'view_detections',
    'view_regional_command',
    'change_own_password',
    'edit_own_profile',
    'escalate_appeals',
    'export_audit_log',
    'generate_reports',
    'pay_own_challans',
    'submit_appeals',
    'view_admins',
    'view_analytics',
    'view_anomaly_alerts',
    'view_appeals',
    'view_audit_log',
    'view_blacklist',
    'view_camera_health',
    'view_cameras',
    'view_case_escalation',
    'view_challans',
    'view_compliance',
    'view_financial_audit',
    'view_flagged_detections',
    'view_heatmap',
    'view_notifications',
    'view_officer_activity',
    'view_officer_feedback',
    'view_officer_kpi',
    'view_operational_audit',
    'view_own_challans',
    'view_penalty_config',
    'view_reports',
    'view_revenue_dashboard',
    'view_shifts',
    'view_team_performance',
    'view_users',
    'view_vehicle_search',
}

_CITIZEN_PERMS = {
    'change_own_password',
    'edit_own_profile',
    'escalate_appeals',
    'pay_own_challans',
    'submit_appeals',
    'view_notifications',
    'view_own_challans',
}

ROLE_PERMISSION_MATRIX: 'OrderedDict[str, frozenset]' = OrderedDict([
    ('IT',      _IT_PERMS),
    ('DIG',     _DIG_PERMS),
    ('SSP',     _SSP_PERMS),
    ('SUPV',    _SUPERVISOR_PERMS),
    ('OFFICER', _OFFICER_PERMS),
    ('AUDIT',   _AUDIT_PERMS),
    ('USER',    _CITIZEN_PERMS),
])

ROLE_HIERARCHY = OrderedDict([
    ('DIG', {
        'label': 'DIG (Super Admin)',
        'level': 100,
        'description': 'Directorate-level super admin - full system control',
        'color': '#6D28D9',
        'reports_to': None,
        'manages': ('SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT'),
        'can_override': ('SSP', 'SUPV', 'OFFICER', 'AUDIT', 'IT'),
        'dashboard_url': '/portal/dig/',
        'login_url': '/auth/admin/login/',
    }),
    ('SSP', {
        'label': 'SSP | Senior Superintendent',
        'level': 80,
        'description': 'Regional command - approvals, appeals, analytics',
        'color': '#BE123C',
        'reports_to': 'DIG',
        'manages': ('SUPV', 'OFFICER'),
        'can_override': ('SUPV', 'OFFICER'),
        'dashboard_url': '/portal/ssp/',
        'login_url': '/auth/admin/login/',
    }),
    ('SUPV', {
        'label': 'Supervisor',
        'level': 60,
        'description': 'Team lead - shifts, team performance, challan ops',
        'color': '#0369A1',
        'reports_to': 'SSP',
        'manages': ('OFFICER',),
        'can_override': ('OFFICER',),
        'dashboard_url': '/portal/supervisor/',
        'login_url': '/auth/admin/login/',
    }),
    ('OFFICER', {
        'label': 'Officer',
        'level': 40,
        'description': 'Field officer - review queue, live tracking (1 camera)',
        'color': '#1E40AF',
        'reports_to': 'SUPV',
        'manages': (),
        'can_override': (),
        'dashboard_url': '/portal/officer/',
        'login_url': '/auth/admin/login/',
    }),
    ('AUDIT', {
        'label': 'Audit Officer',
        'level': 50,
        'description': 'Financial & operational audit, compliance',
        'color': '#B45309',
        'reports_to': 'DIG',
        'manages': (),
        'can_override': (),
        'dashboard_url': '/portal/audit/',
        'login_url': '/auth/admin/login/',
    }),
    ('IT', {
        'label': 'IT Support',
        'level': 55,
        'description': 'Cameras, payments, system settings, live tracking',
        'color': '#0F766E',
        'reports_to': 'DIG',
        'manages': (),
        'can_override': (),
        'dashboard_url': '/portal/it/',
        'login_url': '/auth/admin/login/',
    }),
    ('USER', {
        'label': 'Registered Citizen',
        'level': 10,
        'description': 'Citizen portal - own challans, payments, appeals',
        'color': '#475569',
        'reports_to': None,
        'manages': (),
        'can_override': (),
        'dashboard_url': '/portal/citizen/',
        'login_url': '/auth/citizen/login/',
    }),
])


def get_role_permissions(role: str) -> Set[str]:
    return set(ROLE_PERMISSION_MATRIX.get(role, frozenset()))


def user_has_permission(user, permission: str) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return permission in get_role_permissions(user.role)


def user_has_any_permission(user, permissions: Iterable[str]) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    user_perms = get_role_permissions(user.role)
    return any(p in user_perms for p in permissions)


def user_has_all_permissions(user, permissions: Iterable[str]) -> bool:
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    user_perms = get_role_permissions(user.role)
    return all(p in user_perms for p in permissions)


def get_role_info(role: str) -> dict:
    return ROLE_HIERARCHY.get(role, {})


def get_reports_to(role: str) -> str | None:
    info = ROLE_HIERARCHY.get(role, {})
    return info.get('reports_to')


def get_manages(role: str) -> tuple:
    info = ROLE_HIERARCHY.get(role, {})
    return info.get('manages', ())


def can_override_role(actor_role: str, target_role: str) -> bool:
    info = ROLE_HIERARCHY.get(actor_role, {})
    return target_role in info.get('can_override', ())


def can_override_user(actor_user, target_user) -> bool:
    if actor_user is None or target_user is None:
        return False
    if not getattr(actor_user, 'is_authenticated', False):
        return False
    if getattr(actor_user, 'is_superuser', False):
        return True
    actor_info = ROLE_HIERARCHY.get(actor_user.role, {})
    target_info = ROLE_HIERARCHY.get(target_user.role, {})
    actor_level = actor_info.get('level', -1)
    target_level = target_info.get('level', -1)
    if actor_level <= 0 or target_level < 0:
        return False
    return actor_level > target_level


APPEAL_ESCALATION_CHAIN: tuple = ('OFFICER', 'SUPV', 'SSP', 'DIG')


def get_appeal_escalation_chain() -> tuple:
    return APPEAL_ESCALATION_CHAIN


def get_next_escalation_role(current_role: str) -> str | None:
    chain = APPEAL_ESCALATION_CHAIN
    if current_role not in chain:
        return None
    idx = chain.index(current_role)
    if idx + 1 >= len(chain):
        return None
    return chain[idx + 1]


def get_all_roles() -> list:
    return list(ROLE_HIERARCHY.keys())


def get_role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, {}).get('level', -1)


def summarize_role(role: str) -> dict:
    perms = get_role_permissions(role)
    info = ROLE_HIERARCHY.get(role, {})
    return {
        'role': role,
        'label': info.get('label', role),
        'level': info.get('level', -1),
        'description': info.get('description', ''),
        'color': info.get('color', '#1d4f7c'),
        'reports_to': info.get('reports_to'),
        'manages': info.get('manages', ()),
        'can_override': info.get('can_override', ()),
        'permissions': sorted(perms),
        'permission_count': len(perms),
        'dashboard_url': info.get('dashboard_url', '/'),
        'login_url': info.get('login_url', '/auth/admin/login/'),
    }


def summarize_all_roles() -> list:
    return [summarize_role(r) for r in ROLE_HIERARCHY.keys()]


def get_permission_groups() -> 'OrderedDict[str, list]':
    groups = OrderedDict()
    groups['Camera Infrastructure (IT Support only)'] = [
        'add_camera',
        'edit_camera',
        'delete_camera',
        'toggle_camera',
        'manage_camera_assignments',
        'live_monitor_quick_add',
        ]

    groups['System Configuration (IT only)'] = [
        'edit_system_settings',
        'manage_alerts',
        'manage_banners',
        'manage_smtp_sms',
    ]

    groups['Backups & Maintenance'] = [
        'view_backups',
        'manage_backups',
    ]

    groups['System Health & Monitoring'] = [
        'system_health',
        'system_health_monitoring',
    ]

    groups['AI/ML System (Technical)'] = [
        'view_ai_status',
        'view_ai_performance',
        'view_ai_reports',
        'ai_confidence_config',
        'ai_model_testing',
        'ai_detection_config',
    'camera_video_upload',
    'global_search',
    'manage_faq',
    'view_faq',
    ]

    groups['Payment Integration (IT only)'] = [
        'payment_integration',
        'payment_method_config',
        'payment_gateway_config',
    ]

    groups['PDF & Templates (IT only)'] = [
        'challan_template_manage',
        'pdf_template_manage',
        'pdf_settings',
        'pdf_settings_manage',
    ]

    groups['External API Integration'] = [
        'nadra_integration',
        'excise_integration',
        'external_api_manage',
    ]

    groups['Blacklist Rules (IT only)'] = [
        'blacklist_rule_manage',
    ]

    groups['Citizen Self-Service'] = [
        'view_own_challans',
        'pay_own_challans',
        'submit_appeals',
        'escalate_appeals',
        'edit_own_profile',
    ]

    groups['Detection Review (Officer)'] = [
        'view_detections',
        'review_detections',
            'reject_detection',
        'flag_detection',
        'add_review_note',
        'view_flagged_detections',
        ]

    groups['Challan Management'] = [
        'view_challans',
            'edit_challan_fine',
        'delete_challan',
        'mark_challan_paid',
        'record_payment',
        'bulk_fine_adjust',
        'approve_high_value_challan',
    ]

    groups['Appeal Workflow'] = [
        'view_appeals',
        'approve_appeal',
        'reject_appeal',
        'escalate_appeal',
        'override_appeal',
        'appeal_workflow',
    ]

    groups['Camera Operations (Read-Only)'] = [
        'view_cameras',
        'view_camera_health',
        'camera_feed',
    ]

    groups['Live Tracking'] = [
        'live_tracking',
        'live_tracking_timeline',
        'view_live_monitor',
    ]

    groups['Vehicle Tracking'] = [
        'vehicle_tracking',
    ]

    groups['Analytics & Reports'] = [
        'view_analytics',
        'view_reports',
        'generate_reports',
        'view_revenue_dashboard',
        'view_heatmap',
        'view_case_escalation',
        'view_vehicle_search',
        ]

    groups['Blacklist Management'] = [
        'view_blacklist',
        'add_to_blacklist',
    ]

    groups['Admin Management'] = [
        'view_admins',
        'add_admin',
        'edit_admin',
        'toggle_admin',
        'view_users',
        'edit_user',
        'toggle_user',
        'delete_user',
    ]

    groups['Audit & Compliance'] = [
        'view_audit_log',
        'export_audit_log',
        'view_operational_audit',
        'view_financial_audit',
        'view_compliance',
        'view_anomaly_alerts',
    ]

    groups['Penalty Configuration'] = [
        'view_penalty_config',
        'edit_penalty_config',
    ]

    groups['Shifts & Team'] = [
        'view_shifts',
        'manage_shifts',
        'view_team_performance',
        'view_officer_feedback',
        'add_officer_feedback',
        'view_officer_kpi',
        'view_officer_activity',
    ]

    groups['Regional Command'] = [
        'view_regional_command',
        'manage_regional_access',
    ]

    groups['FAQ'] = [
            ]

    groups['Notifications & Profile'] = [
        'view_notifications',
        'change_own_password',
    ]

    groups['Live Monitor'] = [
        'live_monitor',
    ]

    groups['Officer Tools'] = [
        'officer_pki',
        'officer_profile_manage',
        'view_team_performance',
    ]

    groups['Banner/Alerts (DIG + IT)'] = [
        'manage_alerts',
        'manage_banners',
    ]

    return groups
