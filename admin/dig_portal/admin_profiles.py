from accounts.models import User


ROLE_PROFILES = {
    User.DIG: {
        'designation': 'Inspector General of Police',
        'department':  'Safe City Authority',
        'region':      'Provincial HQ',
        'staff_id_prefix': 'PSC-DIG',
        'rank':        'BPS-21',
        'default_office': 'Central Police Office',
    },
    User.SSP: {
        'designation': 'Senior Superintendent of Police',
        'department':  'Traffic Police',
        'region':      'City Region',
        'staff_id_prefix': 'PSC-SSP',
        'rank':        'BPS-19',
        'default_office': 'Capital City Police Office',
    },
    User.SUPERVISOR: {
        'designation': 'Supervisor of Police',
        'department':  'Traffic Enforcement Wing',
        'region':      'Central Region',
        'staff_id_prefix': 'PSC-SUPV',
        'rank':        'BPS-17',
        'default_office': 'Town Police Office',
    },
    User.OFFICER: {
        'designation': 'Traffic Officer',
        'department':  'Field Enforcement Unit',
        'region':      'Sector-1',
        'staff_id_prefix': 'PSC-OFC',
        'rank':        'BPS-14',
        'default_office': 'Sector Office',
    },
    User.AUDIT: {
        'designation': 'Audit Officer',
        'department':  'Internal Audit & Compliance',
        'region':      'Provincial HQ',
        'staff_id_prefix': 'PSC-AUD',
        'rank':        'BPS-17',
        'default_office': 'Audit Wing, Central Police Office',
    },
    User.IT_SUPPORT: {
        'designation': 'IT Support Engineer',
        'department':  'Information Technology Wing',
        'region':      'Provincial HQ',
        'staff_id_prefix': 'PSC-IT',
        'rank':        'BPS-16',
        'default_office': 'IT Wing, Central Police Office',
    },
}


PROVINCE_CHOICES = [
    ('punjab',     'Punjab'),
    ('sindh',      'Sindh'),
    ('kp',         'Khyber Pakhtunkhwa'),
    ('balochistan','Balochistan'),
    ('islamabad',  'Islamabad Capital Territory'),
    ('gilgit',     'Gilgit-Baltistan'),
    ('ajk',        'Azad Jammu & Kashmir'),
]

DISTRICT_CHOICES = [
    ('lahore',      'Lahore'),
    ('rawalpindi',  'Rawalpindi'),
    ('faisalabad',  'Faisalabad'),
    ('multan',      'Multan'),
    ('gujranwala',  'Gujranwala'),
    ('karachi',     'Karachi'),
    ('peshawar',    'Peshawar'),
    ('quetta',      'Quetta'),
    ('islamabad',   'Islamabad'),
]

CITY_CHOICES = [
    ('lahore-cantt',    'Lahore Cantt'),
    ('lahore-city',     'Lahore City'),
    ('lahore-sadar',    'Lahore Sadar'),
    ('rawalpindi-city', 'Rawalpindi City'),
    ('islamabad-i8',    'Islamabad I-8'),
    ('islamabad-g9',    'Islamabad G-9'),
    ('faisalabad-city', 'Faisalabad City'),
]

OFFICE_CHOICES = [
    ('cpo',           'Central Police Office'),
    ('ccpo',          'Capital City Police Office'),
    ('tpo-town-A',    'Town Police Office — Town A'),
    ('tpo-town-B',    'Town Police Office — Town B'),
    ('sector-1',      'Sector Office — Sector 1'),
    ('sector-2',      'Sector Office — Sector 2'),
    ('audit-wing',    'Audit Wing, CPO'),
    ('it-wing',       'IT Wing, CPO'),
]

DEPARTMENT_CHOICES = [
    ('safecity',     'Safe City Authority'),
    ('traffic',       'Traffic Police'),
    ('enforcement',  'Traffic Enforcement Wing'),
    ('field-unit',   'Field Enforcement Unit'),
    ('audit',        'Internal Audit & Compliance'),
    ('it',           'Information Technology Wing'),
    ('appeals',      'Appeals & Grievance Cell'),
    ('operations',   'Operations & Command Center'),
]

DESIGNATION_CHOICES = [
    ('ig',           'Inspector General of Police'),
    ('dig',          'Deputy Inspector General'),
    ('ssp',          'Senior Superintendent of Police'),
    ('sp',           'Superintendent of Police'),
    ('supv',         'Supervisor of Police'),
    ('auditor',      'Audit Officer'),
    ('officer',      'Traffic Officer'),
    ('it-engineer',  'IT Support Engineer'),
    ('analyst',      'Operations Analyst'),
]

RANK_CHOICES = [
    ('BPS-21', 'BPS-21'),
    ('BPS-20', 'BPS-20'),
    ('BPS-19', 'BPS-19'),
    ('BPS-18', 'BPS-18'),
    ('BPS-17', 'BPS-17'),
    ('BPS-16', 'BPS-16'),
    ('BPS-15', 'BPS-15'),
    ('BPS-14', 'BPS-14'),
    ('BPS-12', 'BPS-12'),
]

EMPLOYMENT_TYPE_CHOICES = [
    ('permanent',  'Permanent'),
    ('contract',   'Contract'),
    ('deputation', 'Deputation'),
    ('probation',  'Probation'),
]

STATUS_CHOICES = [
    ('active',    'Active'),
    ('inactive',  'Inactive'),
    ('suspended', 'Suspended'),
    ('retired',   'Retired'),
    ('on-leave',  'On Leave'),
]

REGION_CHOICES = [
    ('provincial-hq',   'Provincial HQ'),
    ('city-region',     'City Region'),
    ('central-region',  'Central Region'),
    ('sadar-region',    'Sadar Region'),
    ('sector-1',        'Sector-1'),
    ('sector-2',        'Sector-2'),
    ('rawalpindi',      'Rawalpindi Region'),
    ('multan',          'Multan Region'),
    ('faisalabad',      'Faisalabad Region'),
]


def get_profile(role):
    return ROLE_PROFILES.get(role, {})


def generate_staff_id(role, suffix_int):
    profile = get_profile(role)
    prefix = profile.get('staff_id_prefix', 'PSC')
    return f"{prefix}-{suffix_int:03d}"


def all_dropdowns():
    return {
        'provinces':         PROVINCE_CHOICES,
        'districts':         DISTRICT_CHOICES,
        'cities':            CITY_CHOICES,
        'offices':           OFFICE_CHOICES,
        'departments':       DEPARTMENT_CHOICES,
        'designations':      DESIGNATION_CHOICES,
        'ranks':             RANK_CHOICES,
        'employment_types':  EMPLOYMENT_TYPE_CHOICES,
        'statuses':          STATUS_CHOICES,
        'regions':           REGION_CHOICES,
    }

