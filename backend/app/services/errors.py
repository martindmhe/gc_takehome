"""Exceptions raised by services and mapped to HTTP responses in `app.main`."""


class NotFoundError(Exception):
    """The record doesn't exist or is outside the caller's scope (404, no existence leak)."""


class ForbiddenError(Exception):
    """The caller may not perform this action (403)."""
