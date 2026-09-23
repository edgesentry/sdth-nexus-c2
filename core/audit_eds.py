"""edgesentry-rs audit sealing via ctypes write + ``eds audit verify-chain``.

Canonical record hash is ``blake3(postcard(record))`` inside Rust. This module
never reimplements postcard — chaining uses ``eds_record_hash`` only.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EDS_OK = 0
DEFAULT_DEVICE_ID = "nexus-c2"
ZERO_HASH = bytes(32)

_REPO_ROOT = Path(__file__).resolve().parents[1]


class EdsError(RuntimeError):
    """Bridge or CLI failure."""


class EdsAuditRecord(ctypes.Structure):
    """Caller-allocated layout matching ``edgesentry_bridge.h``."""

    _fields_ = [
        ("sequence", ctypes.c_uint64),
        ("timestamp_ms", ctypes.c_uint64),
        ("payload_hash", ctypes.c_uint8 * 32),
        ("signature", ctypes.c_uint8 * 64),
        ("prev_record_hash", ctypes.c_uint8 * 32),
        ("device_id", ctypes.c_uint8 * 256),
        ("object_ref", ctypes.c_uint8 * 512),
    ]


def candidate_bridge_paths() -> list[Path]:
    """Ordered search paths for the shared library."""
    names = ("libedgesentry_bridge.dylib", "libedgesentry_bridge.so")
    roots: list[Path] = []
    env = os.environ.get("EDS_BRIDGE_LIB", "").strip()
    if env:
        roots.append(Path(env))
    for name in names:
        roots.append(_REPO_ROOT / ".eds" / name)
        roots.append(_REPO_ROOT.parent / "edgesentry-rs" / "target" / "release" / name)
        roots.append(_REPO_ROOT / "target" / "release" / name)
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in roots:
        rp = p.resolve() if p.exists() else p
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique


def resolve_eds_bin() -> Path | None:
    env = os.environ.get("EDS_BIN", "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    local = _REPO_ROOT / ".eds" / "eds"
    if local.is_file():
        return local
    found = shutil.which("eds")
    return Path(found) if found else None


def _decode_cstr(buf: Any) -> str:
    raw = bytes(buf)
    nul = raw.find(b"\x00")
    if nul >= 0:
        raw = raw[:nul]
    return raw.decode("utf-8", errors="replace")


def record_to_json_dict(rec: EdsAuditRecord) -> dict[str, Any]:
    """Serialize to the JSON shape ``serde_json`` uses for ``AuditRecord``."""
    return {
        "device_id": _decode_cstr(rec.device_id),
        "sequence": int(rec.sequence),
        "timestamp_ms": int(rec.timestamp_ms),
        "payload_hash": list(rec.payload_hash),
        "signature": list(rec.signature),
        "prev_record_hash": list(rec.prev_record_hash),
        "object_ref": _decode_cstr(rec.object_ref),
    }


def json_dict_to_record(data: dict[str, Any]) -> EdsAuditRecord:
    """Hydrate a ctypes struct from AuditRecord JSON (for ``eds_record_hash``)."""
    rec = EdsAuditRecord()
    rec.sequence = int(data["sequence"])
    rec.timestamp_ms = int(data["timestamp_ms"])
    for i, b in enumerate(data["payload_hash"]):
        rec.payload_hash[i] = int(b)
    for i, b in enumerate(data["signature"]):
        rec.signature[i] = int(b)
    for i, b in enumerate(data["prev_record_hash"]):
        rec.prev_record_hash[i] = int(b)
    did = str(data["device_id"]).encode("utf-8")
    oref = str(data["object_ref"]).encode("utf-8")
    if len(did) > 255 or len(oref) > 511:
        raise EdsError("device_id or object_ref exceeds fixed buffer size")
    for i, b in enumerate(did):
        rec.device_id[i] = b
    for i, b in enumerate(oref):
        rec.object_ref[i] = b
    return rec


class EdsBridge:
    """ctypes wrapper around ``libedgesentry_bridge``."""

    def __init__(self, lib: ctypes.CDLL) -> None:
        self._lib = lib
        self._configure()

    @classmethod
    def load(cls, path: Path | None = None) -> EdsBridge:
        paths = [path] if path is not None else candidate_bridge_paths()
        errors: list[str] = []
        for p in paths:
            if p is None or not p.is_file():
                continue
            try:
                lib = ctypes.CDLL(str(p))
                bridge = cls(lib)
                # Smoke-test: symbol must exist and keygen must be callable.
                _ = bridge._lib.eds_keygen
                logger.debug("Loaded edgesentry bridge from %s", p)
                return bridge
            except OSError as exc:
                errors.append(f"{p}: {exc}")
                continue
        detail = "; ".join(errors) if errors else "no candidate library found"
        raise EdsError(f"failed to load libedgesentry_bridge ({detail})")

    def _configure(self) -> None:
        lib = self._lib
        lib.eds_last_error_message.restype = ctypes.c_char_p
        lib.eds_last_error_message.argtypes = []

        lib.eds_keygen.restype = ctypes.c_int32
        lib.eds_keygen.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
        ]

        lib.eds_sign_record.restype = ctypes.c_int32
        lib.eds_sign_record.argtypes = [
            ctypes.c_char_p,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(EdsAuditRecord),
        ]

        lib.eds_record_hash.restype = ctypes.c_int32
        lib.eds_record_hash.argtypes = [
            ctypes.POINTER(EdsAuditRecord),
            ctypes.POINTER(ctypes.c_uint8),
        ]

        lib.eds_verify_chain.restype = ctypes.c_int32
        lib.eds_verify_chain.argtypes = [
            ctypes.POINTER(EdsAuditRecord),
            ctypes.c_size_t,
        ]

    def _check(self, rc: int, what: str) -> None:
        if rc < 0:
            msg = self._lib.eds_last_error_message() or b""
            raise EdsError(f"{what} failed ({rc}): {msg.decode()}")

    def keygen(self) -> tuple[bytes, bytes]:
        priv = (ctypes.c_uint8 * 32)()
        pub = (ctypes.c_uint8 * 32)()
        self._check(self._lib.eds_keygen(priv, pub), "eds_keygen")
        return bytes(priv), bytes(pub)

    def sign_record(
        self,
        *,
        device_id: str,
        sequence: int,
        timestamp_ms: int,
        payload: bytes,
        prev_record_hash: bytes | None,
        object_ref: str,
        private_key: bytes,
    ) -> EdsAuditRecord:
        if len(private_key) != 32:
            raise EdsError("private_key must be 32 bytes")
        if prev_record_hash is not None and len(prev_record_hash) != 32:
            raise EdsError("prev_record_hash must be 32 bytes")

        rec = EdsAuditRecord()
        payload_buf = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
        priv = (ctypes.c_uint8 * 32).from_buffer_copy(private_key)
        prev_ptr: Any = None
        if prev_record_hash is not None and prev_record_hash != ZERO_HASH:
            prev_arr = (ctypes.c_uint8 * 32).from_buffer_copy(prev_record_hash)
            prev_ptr = prev_arr

        self._check(
            self._lib.eds_sign_record(
                device_id.encode("utf-8"),
                sequence,
                timestamp_ms,
                payload_buf,
                len(payload),
                prev_ptr,
                object_ref.encode("utf-8"),
                priv,
                ctypes.byref(rec),
            ),
            "eds_sign_record",
        )
        return rec

    def record_hash(self, rec: EdsAuditRecord) -> bytes:
        out = (ctypes.c_uint8 * 32)()
        self._check(
            self._lib.eds_record_hash(ctypes.byref(rec), out),
            "eds_record_hash",
        )
        return bytes(out)


def try_load_bridge() -> EdsBridge | None:
    try:
        return EdsBridge.load()
    except EdsError as exc:
        logger.debug("edgesentry bridge unavailable: %s", exc)
        return None


def load_or_create_keypair(
    key_path: Path,
    *,
    bridge: EdsBridge | None = None,
) -> tuple[bytes, bytes]:
    """Return (private_key, public_key) bytes; persist hex JSON at ``key_path``."""
    env = os.environ.get("EDS_PRIVATE_KEY_HEX", "").strip()
    if env:
        priv = bytes.fromhex(env)
        if len(priv) != 32:
            raise EdsError("EDS_PRIVATE_KEY_HEX must be 32 bytes (64 hex chars)")
        if bridge is not None:
            # Derive pub via a throwaway sign is unnecessary; store only priv from env.
            # Prefer inspect via CLI when available.
            eds = resolve_eds_bin()
            if eds is not None:
                proc = subprocess.run(
                    [str(eds), "audit", "inspect-key", "--private-key-hex", env],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    return priv, bytes.fromhex(data["public_key_hex"])
        # Fallback: return zeros for pub (not needed for signing)
        return priv, bytes(32)

    if key_path.is_file():
        data = json.loads(key_path.read_text(encoding="utf-8"))
        return bytes.fromhex(data["private_key_hex"]), bytes.fromhex(data["public_key_hex"])

    if bridge is not None:
        priv, pub = bridge.keygen()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(
            json.dumps(
                {
                    "private_key_hex": priv.hex(),
                    "public_key_hex": pub.hex(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return priv, pub

    eds = resolve_eds_bin()
    if eds is None:
        raise EdsError("cannot keygen: no bridge and no eds binary")
    proc = subprocess.run(
        [str(eds), "audit", "keygen"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return bytes.fromhex(data["private_key_hex"]), bytes.fromhex(data["public_key_hex"])


@dataclass
class EdsChainWriter:
    """Append-only EDS AuditRecord JSON array (sidecar to OCSF jsonl)."""

    path: Path
    key_path: Path
    device_id: str = DEFAULT_DEVICE_ID
    _bridge: EdsBridge | None = field(default=None, repr=False)
    _private_key: bytes | None = field(default=None, repr=False)
    _prev_hash: bytes = field(default=ZERO_HASH, repr=False)
    _sequence: int = 0
    backend: str = "unavailable"

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._bridge = try_load_bridge()
        if self._bridge is not None:
            self.backend = "ctypes"
            self._private_key, _ = load_or_create_keypair(self.key_path, bridge=self._bridge)
        elif resolve_eds_bin() is not None:
            # CLI can sign, but without eds_record_hash we cannot chain — require bridge.
            self.backend = "unavailable"
            logger.warning(
                "eds CLI found but libedgesentry_bridge not loadable; "
                "EDS dual-write disabled (need ctypes for record_hash). "
                "On macOS 27+, run scripts/build_eds_bridge_dylib.sh"
            )
        self._rewind()

    @property
    def available(self) -> bool:
        return (
            self.backend == "ctypes" and self._bridge is not None and self._private_key is not None
        )

    @property
    def next_sequence(self) -> int:
        return self._sequence + 1

    def _rewind(self) -> None:
        records = self.records()
        if not records:
            self._prev_hash = ZERO_HASH
            self._sequence = 0
            return
        self._sequence = int(records[-1]["sequence"])
        if self._bridge is None:
            self._prev_hash = ZERO_HASH
            return
        rec = json_dict_to_record(records[-1])
        self._prev_hash = self._bridge.record_hash(rec)

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise EdsError(f"EDS chain file must be a JSON array: {self.path}")
        return [r for r in loaded if isinstance(r, dict)]

    def replace_records(self, records: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        self._rewind()

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self._prev_hash = ZERO_HASH
        self._sequence = 0

    def append_payload(
        self,
        payload: bytes,
        *,
        object_ref: str,
        timestamp_ms: int | None = None,
    ) -> dict[str, Any] | None:
        """Sign ``payload`` and append to the EDS chain. Returns record dict or None."""
        if not self.available or self._bridge is None or self._private_key is None:
            return None
        ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        seq = self._sequence + 1
        prev = None if self._prev_hash == ZERO_HASH else self._prev_hash
        try:
            rec = self._bridge.sign_record(
                device_id=self.device_id,
                sequence=seq,
                timestamp_ms=ts,
                payload=payload,
                prev_record_hash=prev,
                object_ref=object_ref,
                private_key=self._private_key,
            )
            self._prev_hash = self._bridge.record_hash(rec)
            self._sequence = seq
            as_dict = record_to_json_dict(rec)
            records = self.records()
            records.append(as_dict)
            self.path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            return as_dict
        except EdsError as exc:
            logger.warning("EDS sign failed; continuing with OCSF-only audit: %s", exc)
            return None


@dataclass(frozen=True, slots=True)
class EdsVerifyResult:
    """Result of out-of-process ``eds audit verify-chain``."""

    ok: bool
    total: int
    broken_links: int
    stdout: str = ""
    stderr: str = ""
    backend: str = "eds-cli"

    def summary(self) -> str:
        return f"broken links: {self.broken_links} of {self.total}"


def count_records(path: Path) -> int:
    if not path.exists():
        return 0
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    data = json.loads(raw)
    return len(data) if isinstance(data, list) else 0


def verify_eds_chain(path: Path, *, eds_bin: Path | None = None) -> EdsVerifyResult:
    """Re-verify the chain in a **separate OS process** (writer ≠ verifier)."""
    total = count_records(path)
    if total == 0:
        return EdsVerifyResult(ok=True, total=0, broken_links=0, stdout="", stderr="")

    binary = eds_bin or resolve_eds_bin()
    if binary is None:
        return EdsVerifyResult(
            ok=False,
            total=total,
            broken_links=total,
            stderr="eds binary not found",
        )

    proc = subprocess.run(
        [str(binary), "audit", "verify-chain", "--records-file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0 and "CHAIN_VALID" in (proc.stdout or "")
    # eds exits non-zero on any chain break; we report all-or-nothing as broken count.
    broken = 0 if ok else total
    return EdsVerifyResult(
        ok=ok,
        total=total,
        broken_links=broken,
        stdout=(proc.stdout or "").strip(),
        stderr=(proc.stderr or "").strip(),
    )


def bridge_available() -> bool:
    return try_load_bridge() is not None


def eds_cli_available() -> bool:
    return resolve_eds_bin() is not None
