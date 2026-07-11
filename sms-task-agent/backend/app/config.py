import os


class Settings:
    """All configuration comes from environment variables (see .env.example)."""

    def __init__(self) -> None:
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.claude_model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.screenshot_bucket = os.environ.get("SCREENSHOT_BUCKET", "screenshots")

        self.twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        # Optional comma-separated allowlist of sender phone numbers (E.164).
        self.allowed_senders = [
            s.strip() for s in os.environ.get("ALLOWED_SENDERS", "").split(",") if s.strip()
        ]
        # Set to "false" only for local testing without real Twilio signatures.
        self.validate_twilio_signature = (
            os.environ.get("VALIDATE_TWILIO_SIGNATURE", "true").lower() != "false"
        )

        self.dashboard_api_key = os.environ.get("DASHBOARD_API_KEY", "")
        # Timezone used when interpreting relative due dates like "Friday".
        self.timezone = os.environ.get("USER_TIMEZONE", "America/Los_Angeles")


settings = Settings()
