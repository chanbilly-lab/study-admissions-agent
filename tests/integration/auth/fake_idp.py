"""In-memory IdP with independent real RSA signing and S256 verification."""

import base64
from hashlib import sha256
import json
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class FakeIdP:
    """No HTTP server: only httpx.MockTransport is permitted to call this object."""

    def __init__(self, settings, clock):
        self.settings = settings
        self.clock = clock
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "T05_SIGNING_KEY"
        self.codes = {}
        self.requests = []
        self.claim_changes = {}
        self.claim_removals = set()
        self.header_changes = {}
        self.wrong_signature = False
        self.token_status = 200
        self.token_payload_override = None
        self.jwks_payload_override = None
        self.token_redirect = None
        self.jwks_redirect = None
        self.timeout = False
        self.last_token = None
        self.before_request = None
        self.transport = httpx.MockTransport(self.handle)

    def issue_code(self, nonce, challenge, subject="T05_SYNTHETIC_STUDENT_A"):
        code = "T05_CODE_" + uuid4().hex
        self.codes[code] = {"nonce": nonce, "challenge": challenge, "subject": subject, "used": False}
        return code

    def issue_from_authorization(self, authorization_url, subject="T05_SYNTHETIC_STUDENT_A"):
        query = parse_qs(httpx.URL(authorization_url).query.decode("ascii"), strict_parsing=True)
        assert query["response_type"] == ["code"] and query["scope"] == ["openid"]
        assert query["code_challenge_method"] == ["S256"]
        return self.issue_code(query["nonce"][0], query["code_challenge"][0], subject), query["state"][0]

    def public_jwk(self):
        numbers = self.private_key.public_key().public_numbers()
        encode = lambda number: base64url(number.to_bytes((number.bit_length() + 7) // 8, "big"))
        return {"kty": "RSA", "kid": self.kid, "use": "sig", "alg": "RS256",
                "n": encode(numbers.n), "e": encode(numbers.e)}

    def sign(self, claims):
        header = {"alg": "RS256", "kid": self.kid, "typ": "JWT", **self.header_changes}
        parts = [base64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))
                 for value in (header, claims)]
        message = ".".join(parts).encode("ascii")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if self.wrong_signature else self.private_key
        signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return message.decode("ascii") + "." + base64url(signature)

    def handle(self, request):
        self.requests.append((request.method, str(request.url)))
        if self.before_request is not None:
            self.before_request(request)
        if self.timeout:
            raise httpx.ReadTimeout("T05_SENSITIVE_PROVIDER_FAILURE", request=request)
        provider = self.settings.provider
        if str(request.url) == provider.jwks_uri and request.method == "GET":
            if self.jwks_redirect:
                return httpx.Response(302, headers={"Location": self.jwks_redirect})
            return httpx.Response(200, json=self.jwks_payload_override if self.jwks_payload_override is not None
                                  else {"keys": [self.public_jwk()]})
        if str(request.url) != provider.token_endpoint or request.method != "POST":
            raise AssertionError("IdP was contacted outside its pinned endpoints")
        if self.token_redirect:
            return httpx.Response(302, headers={"Location": self.token_redirect})
        if self.token_status != 200:
            return httpx.Response(self.token_status, json={"error": "T05_SENSITIVE_PROVIDER_FAILURE"})
        if self.token_payload_override is not None:
            return httpx.Response(200, json=self.token_payload_override)
        expected_auth = "Basic " + base64.b64encode(
            (provider.client_id + ":" + provider.client_secret.get_secret_value()).encode("utf-8")
        ).decode("ascii")
        if request.headers.get("authorization") != expected_auth:
            return httpx.Response(401, json={"error": "invalid_client"})
        form = parse_qs(request.content.decode("ascii"), keep_blank_values=True, strict_parsing=True)
        if set(form) != {"code", "grant_type", "redirect_uri", "code_verifier"} or any(len(value) != 1 for value in form.values()):
            return httpx.Response(400, json={"error": "invalid_request"})
        proof = self.codes.get(form["code"][0])
        if (proof is None or proof["used"] or form["grant_type"] != ["authorization_code"]
            or form["redirect_uri"] != [self.settings.redirect_uri]
            or base64url(sha256(form["code_verifier"][0].encode("ascii")).digest()) != proof["challenge"]):
            return httpx.Response(400, json={"error": "invalid_grant"})
        proof["used"] = True
        epoch = int(self.clock().timestamp())
        claims = {"iss": provider.issuer, "sub": proof["subject"], "aud": provider.client_id,
                  "nonce": proof["nonce"], "iat": epoch, "exp": epoch + 120, **self.claim_changes}
        for name in self.claim_removals:
            claims.pop(name, None)
        self.last_token = self.sign(claims)
        return httpx.Response(200, json={"id_token": self.last_token, "access_token": "T05_SENSITIVE_ACCESS_TOKEN",
                                        "token_type": "Bearer", "expires_in": 120})
