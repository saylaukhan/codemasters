"""Access of panel users (ADR-008): ``require(permission)``, scope, RLS, audit.

A panel endpoint declares ``Depends(require("<permission>"))``; the permission matrix is
``permissions.py``, the row-level scope ``rls.py``, the audit log ``audit.py``.
"""

from app.auth.deps import AuthUser, current_user, require

__all__ = ["AuthUser", "current_user", "require"]
