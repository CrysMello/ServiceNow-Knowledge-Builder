"""Application configuration schema (CFG-001 through CFG-006, RNF-023).

Lives in ``shared`` rather than ``infrastructure`` so both the
application layer (which depends on it through
``ConfigurationProviderPort``) and infrastructure adapters (which load
it from disk) can import it without creating a forbidden
``application -> infrastructure`` dependency.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CapturePolicyModel(BaseModel):
    """Policy controlling what the Recorder is allowed to capture (RS-011,
    RF-038)."""

    model_config = ConfigDict(frozen=True)

    capture_field_values: bool = False
    mask_sensitive_fields: bool = True
    capture_screenshots: bool = True
    full_page_screenshots: bool = False
    capture_authenticated_user: bool = False


class LoginDetectionPolicyModel(BaseModel):
    """Policy controlling how the Browser Manager decides that the manual
    Microsoft login finished and the ServiceNow instance loaded (SRS,
    section 3.3; RF-004).

    RF-004 requires the detection to rely on at least two independent,
    configurable signals rather than a single selector, precisely
    because corporate instances may customize their login/landing
    pages.
    """

    model_config = ConfigDict(frozen=True)

    stability_seconds: float = Field(default=2.0, ge=0)
    poll_interval_seconds: float = Field(default=1.0, gt=0)
    timeout_seconds: float = Field(default=600.0, gt=0)
    microsoft_login_hostnames: tuple[str, ...] = (
        "login.microsoftonline.com",
        "login.microsoft.com",
        "login.live.com",
    )
    service_now_marker_selector: str | None = None
    expected_title_substring: str | None = None


class AppConfig(BaseModel):
    """Root configuration model, validated at startup (CFG-001).

    Default values follow the "most secure default" rule (CFG-002,
    RNF-011): no field values captured, sensitive fields masked, no
    authenticated user name recorded.
    """

    model_config = ConfigDict(frozen=True)

    instance_url: str
    output_directory: Path
    browser_timeout_seconds: float = Field(default=30.0, gt=0)
    headless: bool = False
    resolution_width: int = Field(default=1920, gt=0)
    resolution_height: int = Field(default=1080, gt=0)
    user_agent: str | None = None
    downloads_enabled: bool = False

    language: str = "pt-BR"
    log_level: str = "info"
    log_retention_days: int = Field(default=30, ge=1)
    max_journal_loss_seconds: float = Field(default=10.0, ge=0)

    capture_policy: CapturePolicyModel = Field(default_factory=CapturePolicyModel)
    login_detection: LoginDetectionPolicyModel = Field(default_factory=LoginDetectionPolicyModel)

    @field_validator("instance_url")
    @classmethod
    def _instance_url_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("instance_url must not be blank.")
        return value
