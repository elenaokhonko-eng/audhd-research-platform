CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS literature;
CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS publishing;

COMMENT ON SCHEMA clinical IS
  'Restricted zone for pseudonymous clinical observations; direct identifiers are prohibited.';
