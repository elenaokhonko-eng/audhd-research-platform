from platform_api.app import create_app
from platform_api.settings import Settings
from platform_api.shared.logging import configure_logging

_settings = Settings()
configure_logging(_settings.service_name)
app = create_app(_settings)
