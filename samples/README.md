# Sample Documents

Drop a demo FRD and its matching manual test case document here to enable the
**Load Sample ShopSphere Files** button in the UI.

Expected filenames (override with the `SAMPLE_FRD` / `SAMPLE_TC` variables in `.env`):

| Role             | Default filename                                     |
| ---------------- | ---------------------------------------------------- |
| FRD              | `ShopSphere_Functional_Requirements_Document.docx`    |
| Manual test cases| `ShopSphere_Manual_Testcases.docx`                    |

Both files must be `.docx`.

## What happens when this folder is empty

This directory is **optional**. If the sample documents are absent, `POST
/api/stage1-parse` falls back to parsing whatever is in `input_modules/`. If that
is empty too, the API returns a `400` telling the user to upload documents.

## Expected document structure

The parser relies on document structure, not on exact wording.

**FRD** — Word `Heading` styles delimit sections. A section whose heading contains
`Requirement ID:` becomes a functional requirement; an adjacent two-column table
supplies its metadata (`Description`, `Actors`, `Trigger`, `Priority`,
`Pre-Conditions`, `Main Flow`, `Post-Conditions`, `Business Rules`,
`Exception Flows`).

**Manual test cases** — one or more tables whose first row is a header row. A
`Test Name` column is required; `Type`, `Subject`, `Description`,
`Expected Result`, and `Execution Status` are recognised when present. Test IDs
are read from the `TC-nnn` pattern in the test name.
