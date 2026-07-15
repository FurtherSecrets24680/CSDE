# ChemSearch DataEdit

Small desktop editor for the ChemSearch offline Chemical Database assets.

## Run

```bash
python3 app.py
```

By default it opens:

```text
~/AndroidStudioProjects/chemsearch/app/src/main/assets/chemical_database
```

Use **Browse** if the ChemSearch project lives somewhere else.

## What It Edits

- `substances.json`
- `ions.json`
- `functional_groups.json`
- `reactions.json`

Each save writes the same split JSON format used by the Android app. Existing
files are copied to `*.bak` before being overwritten.

## Editing Notes

- List fields use one item per line.
- IDs are auto-filled from the entry name if you leave them blank.
- Use **Validate** before rebuilding ChemSearch to catch missing names or
  duplicate IDs.
