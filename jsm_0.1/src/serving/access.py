"""Local by default; authenticated operator access when explicitly configured."""

import base64
import binascii
import ipaddress
import os
import secrets

from starlette.responses import JSONResponse


def validate_access_config():
    if os.environ.get("JSM_ENV") == "production":
        for name in ("JSM_ACCESS_PASSWORD", "JSM_ADMIN_PASSWORD"):
            if len(os.environ.get(name, "")) < 16:
                raise RuntimeError(f"Production requires {name} with at least 16 characters.")


class AccessBoundary:
    def __init__(self, app):
        self.app = app
        self.username = os.environ.get("JSM_ACCESS_USERNAME", "operator")
        self.password = os.environ.get("JSM_ACCESS_PASSWORD", "")
        self.admin_password = os.environ.get("JSM_ADMIN_PASSWORD", self.password)
        self.origins = set(filter(None, os.environ.get("JSM_ALLOWED_ORIGINS", "").split(",")))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        path = scope["path"]
        peer = (scope.get("client") or ("", 0))[0]
        try:
            local = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            local = peer == "testclient"
        admin = path == "/admin" or path.startswith("/admin/")
        password = self.admin_password if admin else self.password
        if not local and (not self.password or not self.admin_password):
            return await JSONResponse({"detail": "Remote access requires configured operator credentials."}, 403)(scope, receive, send)
        if password:
            try:
                scheme, token = headers.get(b"authorization", b"").decode().split(" ", 1)
                user, supplied = base64.b64decode(token, validate=True).decode().split(":", 1)
                candidates = [password] if admin else [password, self.admin_password]
                password_matches = any(secrets.compare_digest(supplied.encode(), item.encode()) for item in candidates if item)
                valid = (scheme.lower() == "basic" and secrets.compare_digest(user.encode(), self.username.encode())
                         and password_matches)
            except (ValueError, UnicodeError, binascii.Error):
                valid = False
            if not valid:
                return await JSONResponse({"detail": "Operator sign-in required."}, 401,
                    headers={"WWW-Authenticate": 'Basic realm="JSM", charset="UTF-8"'})(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            origin = headers.get(b"origin", b"").decode("latin1")
            allowed = {f"{scope['scheme']}://{host}", *self.origins}
            if local and not password:
                allowed.update(f"http://{name}:{port}" for name in ("localhost", "127.0.0.1") for port in (3000, 3001, 3012, 8000))
            if origin and origin not in allowed:
                return await JSONResponse({"detail": "Cross-origin request rejected."}, 403)(scope, receive, send)
            maximum = 4_100_000 if path == "/api/voice/turn" else 100_000
            body = bytearray()
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > maximum:
                    return await JSONResponse({"detail": "Request is too large."}, 413)(scope, receive, send)
                if not event.get("more_body"):
                    break
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()
        else:
            bounded_receive = receive

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"same-origin"),
                    (b"permissions-policy", b"microphone=(self), camera=()")]
                if path.startswith(("/api/", "/admin/")):
                    message["headers"].append((b"cache-control", b"no-store"))
            await send(message)

        return await self.app(scope, bounded_receive, secure_send)
