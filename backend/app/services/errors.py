"""Exceptions raised by services and mapped to HTTP responses in `app.main`."""


class NotFoundError(Exception):
    """The record doesn't exist or is outside the caller's scope (404, no existence leak)."""


class ForbiddenError(Exception):
    """The caller may not perform this action (403)."""


class ConflictError(Exception):
    """The action doesn't fit the record's current state, e.g. accepting a declined lead (409)."""


class InvalidRequestError(Exception):
    """The request refers to something invalid, e.g. an unknown target firm (422)."""


class InvalidFileError(Exception):
    """The upload isn't an acceptable file, e.g. not a PDF (415)."""


class FileTooLargeError(Exception):
    """The upload exceeds the configured size limit (413)."""
