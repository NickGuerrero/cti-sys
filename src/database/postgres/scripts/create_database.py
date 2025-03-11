from src.database.postgres.core import *

# Create database from the current model set-up
# Use alembic scripts to upgrade between deployment TODO
Base.metadata.create_all(engine)

# Load the Alembic configuration and generate the
# version table, "stamping" it with the most recent rev:
# From the cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch

# Temporarily disable alembic until errors resolved
'''
from alembic.config import Config
from alembic import command
alembic_cfg = Config("/../../alembic.ini")
command.stamp(alembic_cfg, "head")
'''