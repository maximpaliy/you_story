"""Dedicated schema migration process; owner URL never reaches HTTP settings."""

import os

from you_story.migrations.runner import migrate

migrate(os.environ["MIGRATION_DATABASE_URL"])
