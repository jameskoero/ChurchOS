# ChurchOS database backups

Every night at 03:30 Kenya time (00:30 UTC) the **Database backup** workflow copies the whole
database with `pg_dump`, encrypts it with AES-256 using your passphrase, and keeps it for 14 days
as a workflow artifact. The plain copy is deleted on the runner before anything is stored.
The repository is public, so only the encrypted file is ever uploaded.

## One-time setup (repository secrets)
GitHub > ChurchOS > Settings > Secrets and variables > Actions > New repository secret:

- `BACKUP_DATABASE_URL`: the Neon connection string (the same value as Render's `DATABASE_URL`).
- `BACKUP_PASSPHRASE`: 20 or more random characters. Store it somewhere safe outside GitHub:
  without it no backup can be opened.

Then Actions > Database backup > Run workflow, and check it ends green.

## Restore (test this once a month)
1. Actions > Database backup > open a run > download the artifact (a zip holding the `.dump.gpg`).
2. Decrypt: `gpg --decrypt churchos-YYYYMMDD-HHMM.dump.gpg > db.dump`
3. Restore into a **new, empty** database first (for example a new Neon branch), never straight over the live one:
   `pg_restore --no-owner --no-privileges -d "NEW_DATABASE_URL" db.dump`
4. Point a test copy of the app at it, sign in, and check members and finance totals.
5. Delete `db.dump` when done.

Neon also keeps its own restore history; how far back depends on your Neon plan (see Restore in the Neon console).
