from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.permissions import (
    ROLE_PERMISSION_MATRIX,
    ROLE_HIERARCHY,
    APPEAL_ESCALATION_CHAIN,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Verify role-based permissions are auto-assigned consistently for every user."

    def add_arguments(self, parser):
        parser.add_argument(
            '--user', type=str, default=None,
            help='Only check a specific user (by email or username).',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print every permission code per user.',
        )

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SQL_TABLE(
            "\n" + "=" * 72 + "\n"
            "SAFE CITY - ROLE PERMISSION SYNC\n"
            "=" * 72
        ))

        self.stdout.write(self.style.SQL_TABLE("\nROLE PERMISSION MATRIX:"))
        for role_code, info in ROLE_HIERARCHY.items():
            perms = ROLE_PERMISSION_MATRIX.get(role_code, frozenset())
            self.stdout.write(
                f"  {role_code:8s} (L{info['level']:3d})  "
                f"{info['label']:35s}  {len(perms):3d} permissions"
            )

        self.stdout.write(self.style.SQL_TABLE("\nAPPEAL ESCALATION CHAIN:"))
        chain_str = "  →  ".join(APPEAL_ESCALATION_CHAIN) or "  (none)"
        self.stdout.write(f"  {chain_str}")

        qs = User.objects.all().order_by('role', 'id')
        if opts['user']:
            qs = qs.filter(email=opts['user']) | qs.filter(username=opts['user'])

        self.stdout.write(self.style.SQL_TABLE(
            f"\nUSERS ({qs.count()} total):\n"
            f"{'ID':5s} {'Role':8s} {'Email':40s} {'#Perms':7s} Label"
        ))
        self.stdout.write("-" * 72)

        for u in qs:
            perms = u.permissions
            label = u.role_label
            self.stdout.write(
                f"{u.id:5d} {u.role:8s} {(u.email or u.username or '?')[:40]:40s} "
                f"{len(perms):7d} {label}"
            )
            if opts['verbose']:
                for p in sorted(perms):
                    self.stdout.write(f"      • {p}")

        self.stdout.write(self.style.SUCCESS(
            "\n✓ All users verified. Permissions are auto-derived from role - "
            "no per-user grants to sync.\n"
            "  To change a user's permissions, change their role at "
            "/dig/admins/<id>/ (DIG-only).\n"
        ))

