# Story complexity and models

## How complexity is decided

Complexity depends on **what the story touches**, not on its size. The number of files or modules decides nothing.

| `high` if it touches at least one of | Examples |
|---|---|
| A migration or database schema | new column, index, constraint, data move |
| Money | payments, subscriptions, refunds, prices, in-app currency |
| A transaction with a lock that a second actor races for | booking a slot, rescheduling, seat counters |
| A published contract | OpenAPI, an error code, a permission slug, what an operation promises a client |

Everything else is `normal`. The spec line: `**Complexity:** high - migration: new column users.locale`
or `**Complexity:** normal - no item touched`.

## Which model at which stage

In skill prose models are roles: **"heavy"** and **"default"**. In a spec the `**Dev model:**` line is the
**literal model name** (`opus` | `sonnet`): projects' tests and metrics scripts parse it. The mapping is profile
keys: "heavy" = `models.heavy` (default `opus`), "default" = `models.default` (default `sonnet`).

| Stage | Model |
|---|---|
| Epic specs | heavy |
| Implementing a `high` story | heavy (a subagent of the session that drives the pipeline) |
| Implementing a `normal` story | default |
| The session driving the pipeline; all review layers | default |
| Roundtable over specs, retrospectives, documents | default |

- On a subscription without the heavy model, only `normal` stories run.
- **Underestimation is corrected by the run:** a `normal` story whose CI is red twice because of its own code, or
  whose review found a behavior defect, is redone by the heavy model from the same spec; the record says which
  attempt it is and what went wrong.

## Size and splitting

- Limit: at most 300 diff lines and 5 code files; tests and fixtures excluded.
- Split with letters: `3-2` becomes `3-2a`, `3-2b`. A sub-story `3-2a` is not split into `3-2a1`; renumber instead:
  `3-2a`, `3-2b`, `3-2c`...
- Generated copies (plugin builds, codegen) do not count toward the limit, but the PR says so.

## Why it is built this way

- Small stories: review and CI are cheaper and a revert is precise; large stories produced red CI and three
  review rounds each.
- A key with a digit after the letter: a planner once cut an epic into 73 stories like `18-1b1`; the queue
  skipped them silently and it was found only from a warning in the log.
