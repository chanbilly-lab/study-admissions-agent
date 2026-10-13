"""Fixed public error vocabulary; no persistence imports or input diagnostics."""

from ..auth.config import AuthFlowError


class PrivacyError(AuthFlowError):
    def __init__(self, status_code=403):
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                 409: "CONFLICT", 503: "SERVICE_UNAVAILABLE"}
        if status_code not in codes:
            status_code = 503
        self.status_code, self.code = status_code, codes[status_code]
        ValueError.__init__(self, "Privacy processing is unavailable" if status_code == 503
                             else "Privacy request is not permitted")
