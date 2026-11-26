"""Security utilities: password hashing, JWT tokens, Fernet encryption,
file validation, malware/active-content scanning, and prompt-injection defense.
"""
from __future__ import annotations

import hashlib
import io
import re
import secrets
import socket
import struct
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

# Standard EICAR antivirus test string (harmless industry standard test pattern)
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/octet-stream",  # Verified via magic bytes below
}

# Prompt-injection patterns frequently embedded in hostile CVs or job descriptions
PROMPT_INJECTION_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("ignore_previous", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.I)),
    ("override_system", re.compile(r"(override|bypass|disregard)\s+(system|developer|safety)\s+(prompt|instructions|rules)", re.I)),
    ("score_manipulation", re.compile(r"(give|assign|return|set)\s+(this|the)?\s*(candidate|cv|resume|job)?\s*(a\s+)?(100%|100\s*percent|perfect|maximum)\s*(match|score)", re.I)),
    ("role_hijack", re.compile(r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(a\s+)?(hiring\s+manager|system\s+admin|unrestricted)", re.I)),
    ("exfiltrate_secrets", re.compile(r"(reveal|print|dump|output)\s+(your\s+)?(system\s+prompt|api\s*key|secret|environment\s+variables)", re.I)),
    ("tool_call_injection", re.compile(r"<\s*/?\s*(system|assistant|tool_call|function_call)\s*>", re.I)),
    ("hidden_directive", re.compile(r"\[SYSTEM\s*:|BEGIN\s+SYSTEM\s+PROMPT|###\s*INSTRUCTION\s*OVERRIDE", re.I)),
]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(subject: str, role: str = "user", expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, role: str = "user") -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def _get_fernet() -> Fernet:
    return Fernet(get_settings().effective_fernet_key)


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _get_fernet().decrypt(token)


def encrypt_text(text: str) -> str:
    if not text:
        return ""
    return _get_fernet().encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


@dataclass
class SecurityScanResult:
    is_safe: bool
    status: str  # clean | suspicious | rejected
    detected_format: str
    sha256_hash: str
    notes: List[str] = field(default_factory=list)


def _scan_with_clamd(content: bytes, host: str, port: int) -> Optional[Tuple[bool, str]]:
    """Optional ClamAV INSTREAM scan when CLAMD_HOST is configured."""
    try:
        with socket.create_connection((host, port), timeout=5.0) as sock:
            sock.sendall(b"zINSTREAM\0")
            chunk_size = 8192
            for i in range(0, len(content), chunk_size):
                chunk = content[i : i + chunk_size]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            resp = sock.recv(4096).decode("utf-8", errors="ignore").strip("\x00\r\n ")
            if "FOUND" in resp:
                return False, f"ClamAV threat detected: {resp}"
            if "OK" in resp:
                return True, "ClamAV scan clean"
            return True, f"ClamAV response: {resp}"
    except Exception as exc:
        return None


def validate_and_scan_upload(
    filename: str,
    content_type: Optional[str],
    content: bytes,
    max_size_bytes: int,
) -> SecurityScanResult:
    """Validate extension, file size, magic bytes, archive bombs, macros, PDF active scripts, and EICAR."""
    sha256_hash = hashlib.sha256(content).hexdigest()
    notes: List[str] = []

    if not content:
        return SecurityScanResult(False, "rejected", "empty", sha256_hash, ["Uploaded file is empty."])

    if len(content) > max_size_bytes:
        return SecurityScanResult(
            False,
            "rejected",
            "oversized",
            sha256_hash,
            [f"File exceeds maximum allowed size of {max_size_bytes // (1024 * 1024)} MB."],
        )

    lower_name = (filename or "").lower().strip()
    ext = ""
    for candidate in ALLOWED_EXTENSIONS:
        if lower_name.endswith(candidate):
            ext = candidate
            break
    if not ext:
        return SecurityScanResult(
            False,
            "rejected",
            "unsupported_extension",
            sha256_hash,
            ["Only PDF, DOCX, and DOC files are supported."],
        )

    # Check EICAR test virus signature
    if EICAR_SIGNATURE in content:
        return SecurityScanResult(
            False,
            "rejected",
            ext.lstrip("."),
            sha256_hash,
            ["Malware signature detected (EICAR test pattern). File rejected."],
        )

    # Verify magic bytes
    detected_format = ext.lstrip(".")
    if ext == ".pdf":
        if not content[:8].startswith(b"%PDF-"):
            return SecurityScanResult(
                False,
                "rejected",
                "invalid_pdf",
                sha256_hash,
                ["File header does not match valid PDF magic bytes (%PDF-)."],
            )
        # Inspect PDF for dangerous active content (/JavaScript, /JS, /Launch, /OpenAction)
        dangerous_pdf_tokens = [b"/JavaScript", b"/JS ", b"/Launch", b"/RichMedia"]
        found_active = [tok.decode("ascii") for tok in dangerous_pdf_tokens if tok in content]
        if found_active:
            return SecurityScanResult(
                False,
                "rejected",
                "pdf",
                sha256_hash,
                [f"Rejected PDF containing potentially malicious active content: {', '.join(found_active)}"],
            )
    elif ext == ".docx":
        if not content[:4].startswith(b"PK\x03\x04"):
            return SecurityScanResult(
                False,
                "rejected",
                "invalid_docx",
                sha256_hash,
                ["File header does not match valid DOCX (OOXML ZIP) structure."],
            )
        # Check zip structure, zip bomb ratio, and embedded VBA macros
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = zf.namelist()
                if "word/document.xml" not in names:
                    return SecurityScanResult(
                        False,
                        "rejected",
                        "invalid_docx",
                        sha256_hash,
                        ["ZIP archive is missing word/document.xml; not a valid DOCX document."],
                    )
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 100 * 1024 * 1024 or (
                    len(content) > 0 and total_uncompressed / len(content) > 100
                ):
                    return SecurityScanResult(
                        False,
                        "rejected",
                        "docx",
                        sha256_hash,
                        ["Rejected archive due to suspicious compression ratio (potential zip bomb)."],
                    )
                for member in names:
                    ml = member.lower()
                    if "vbaproject.bin" in ml or ml.endswith(".exe") or ml.endswith(".dll") or ml.endswith(".js"):
                        return SecurityScanResult(
                            False,
                            "rejected",
                            "docx",
                            sha256_hash,
                            [f"Rejected DOCX containing active macro or executable payload: {member}"],
                        )
        except zipfile.BadZipFile:
            return SecurityScanResult(
                False,
                "rejected",
                "invalid_docx",
                sha256_hash,
                ["Corrupted DOCX archive."],
            )
    elif ext == ".doc":
        # OLE2 Compound Binary magic bytes: D0 CF 11 E0 A1 B1 1A E1 (or plain text/RTF fallback)
        if content[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and not content[:5].startswith(b"{\\rtf"):
            notes.append("Legacy .doc file did not have standard OLE2 header; text extraction may be limited.")
        if b"VBA" in content and b"AutoOpen" in content:
            return SecurityScanResult(
                False,
                "rejected",
                "doc",
                sha256_hash,
                ["Rejected legacy .doc containing AutoOpen VBA macro signature."],
            )

    # Optional ClamAV daemon check
    settings = get_settings()
    if settings.CLAMD_HOST:
        clam_res = _scan_with_clamd(content, settings.CLAMD_HOST, settings.CLAMD_PORT)
        if clam_res is not None:
            is_clean, clam_msg = clam_res
            notes.append(clam_msg)
            if not is_clean:
                return SecurityScanResult(False, "rejected", detected_format, sha256_hash, notes)

    notes.append("Structural validation and active-content security scan passed.")
    return SecurityScanResult(True, "clean", detected_format, sha256_hash, notes)


def detect_and_sanitize_prompt_injection(text: str) -> Tuple[str, List[str]]:
    """Detect and neutralize prompt-injection attempts inside untrusted CVs or job listings.

    We preserve factual text while flagging and stripping overt instruction-hijack directives.
    """
    if not text:
        return "", []

    flags: List[str] = []
    sanitized = text
    for name, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            flags.append(name)
            sanitized = pattern.sub("[FILTERED_UNTRUSTED_DIRECTIVE]", sanitized)

    # Strip invisible zero-width unicode characters commonly used to hide prompt injections
    invisible_re = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
    if invisible_re.search(sanitized):
        flags.append("invisible_unicode_stripped")
        sanitized = invisible_re.sub("", sanitized)

    return sanitized, flags


def wrap_untrusted_data(label: str, text: str) -> str:
    """Wrap untrusted external text (CV or Job Description) with a randomized nonce tag."""
    nonce = secrets.token_hex(6)
    safe_text, _ = detect_and_sanitize_prompt_injection(text)
    return (
        f"<{label}_UNTRUSTED_DATA_{nonce}>\n"
        f"{safe_text}\n"
        f"</{label}_UNTRUSTED_DATA_{nonce}>"
    )
