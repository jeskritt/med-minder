# Phase spec template

Copy this directory when starting a new phase:

```
specs/_template  →  specs/<YYYY-MM-DD>-phase-<N>-<name>/
```

The three files (`requirements.md`, `plan.md`, `validation.md`) are
required for every phase. They map to:

- **requirements.md** — *what* and *why*. Scope, decisions table,
  out-of-scope, security considerations.
- **plan.md** — *how*. Numbered task groups, each ending with
  something committable.
- **validation.md** — *done means done*. Concrete, mechanical checks
  that decide whether the phase can merge.

Don't rename the files. Reviewers and CI both rely on these names.
The structure of each file is documented in its own template — keep
the headings, fill in the content.

A phase is reviewable when:
- Every section in `requirements.md` has either content or an
  explicit "(none)".
- `plan.md` has at least one numbered group per scope item in
  `requirements.md`.
- `validation.md` has at least one check per acceptance criterion or
  decision in `requirements.md`.
