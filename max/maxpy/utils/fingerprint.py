from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class ApkBuildFingerprint:
    """Android APK build fingerprint."""

    brand: str
    model: str
    device: str
    product: str
    manufacturer: str
    fingerprint: str
    sdk_version: int
    version_release: str
    version_incremental: str
    security_patch: str
    build_id: str
    build_type: str
    tags: str


# Known Android fingerprints (from PyMax)
KNOWN_FINGERPRINTS: dict[str, ApkBuildFingerprint] = {
    "android-34-google": ApkBuildFingerprint(
        brand="google",
        model="Pixel 8",
        device="shiba",
        product="shiba",
        manufacturer="Google",
        fingerprint="google/shiba/shiba:14/UP1A.231005.007/10773478:user/release-keys",
        sdk_version=34,
        version_release="14",
        version_incremental="10773478",
        security_patch="2023-10-05",
        build_id="UP1A.231005.007",
        build_type="user",
        tags="release-keys",
    ),
    "android-33-samsung": ApkBuildFingerprint(
        brand="samsung",
        model="SM-S918B",
        device="dm3q",
        product="dm3qeea",
        manufacturer="samsung",
        fingerprint="samsung/dm3qeea/dm3q:13/TP1A.220624.014/S918BXXS1AXB1:user/release-keys",
        sdk_version=33,
        version_release="13",
        version_incremental="S918BXXS1AXB1",
        security_patch="2023-01-01",
        build_id="TP1A.220624.014",
        build_type="user",
        tags="release-keys",
    ),
}


class FingerprintGenerator:
    """Generates device fingerprints for TCP authentication."""

    def __init__(
        self,
        android_version: str | None = None,
        android_build: str | None = None,
        sdk_version: int | None = None,
        locale: str = "en_US",
        timezone: str = "UTC",
    ):
        self.android_version = android_version
        self.android_build = android_build
        self.sdk_version = sdk_version or 34
        self.locale = locale
        self.timezone = timezone

        # Select fingerprint
        if android_version and android_build:
            key = f"android-{android_version}-{android_build.lower()}"
        else:
            key = "android-34-google"  # Default

        self._fingerprint = KNOWN_FINGERPRINTS.get(key, KNOWN_FINGERPRINTS["android-34-google"])

    def generate(self, device_id: str | None = None) -> bytes:
        """Generate SHA256 fingerprint."""
        if device_id is None:
            device_id = self._generate_device_id()

        # Create fingerprint string
        fp_str = (
            f"{self._fingerprint.brand}|"
            f"{self._fingerprint.model}|"
            f"{self._fingerprint.device}|"
            f"{self._fingerprint.fingerprint}|"
            f"{device_id}|"
            f"{self.sdk_version}|"
            f"{self.locale}|"
            f"{self.timezone}"
        )

        return hashlib.sha256(fp_str.encode()).digest()

    def _generate_device_id(self) -> str:
        """Generate random device ID (16 bytes hex)."""
        return "".join(f"{random.randint(0, 255):02x}" for _ in range(16))

    @property
    def fingerprint(self) -> ApkBuildFingerprint:
        return self._fingerprint

    def get_user_agent(self, app_version: str = "2.4.1", build_number: int = 100) -> dict[str, Any]:
        """Get MobileUserAgentPayload."""
        return {
            "app_version": app_version,
            "build_number": build_number,
            "device_id": self._generate_device_id(),
            "device_type": "android",
            "os_version": self._fingerprint.version_release,
            "os_build": self._fingerprint.build_id,
            "brand": self._fingerprint.brand,
            "model": self._fingerprint.model,
            "manufacturer": self._fingerprint.manufacturer,
            "fingerprint": self._fingerprint.fingerprint,
            "sdk_version": self.sdk_version,
            "locale": self.locale,
            "timezone": self.timezone,
        }


class VersionCatalog:
    """Catalog of Android versions and fingerprints."""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "maxpy" / "versions"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._catalog: dict[str, ApkBuildFingerprint] = {}

    def get_fingerprint(self, version: str, build: str) -> ApkBuildFingerprint:
        """Get fingerprint for version/build."""
        key = f"android-{version}-{build.lower()}"
        if key in self._catalog:
            return self._catalog[key]
        if key in KNOWN_FINGERPRINTS:
            return KNOWN_FINGERPRINTS[key]
        return KNOWN_FINGERPRINTS["android-34-google"]

    def list_versions(self) -> list[str]:
        """List available versions."""
        return list(KNOWN_FINGERPRINTS.keys())