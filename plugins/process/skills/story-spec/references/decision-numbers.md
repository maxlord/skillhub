# Decision numbers D-NNN

A decision in a plan or spec gets a number `D-NNN`, unique across the project's whole planning tree. A project
test (for example planning-records) fails if a number is defined twice - and then the whole default branch is red.

## Rules

1. **Take a number against a named tree:** write `numbers from D-nnn, epics.md at <sha>` in the spec or epic.
2. **Parallel agents use assigned ranges only.** When the coordinator starts two or more planning agents in one
   repo, it assigns non-overlapping ranges ("ONLY D-1760...D-1789, take no others") and keeps the list of issued
   ranges. An agent without a range takes no numbers.
3. **Before numbering,** look not only at the default branch but also at open PRs and branches of other sessions
   (list open PRs through your forge; `git ls-remote --heads origin`): someone's unmerged PR may already hold numbers.
4. **After every merge of the default branch into your branch,** re-read the decisions block and check for
   duplicates before the final push.
5. **Before merging a second docs PR with decisions,** run `git grep -c "D-NNNN"` over both; after the merge, run
   the project's planning-records test on the default branch (or wait for its CI).
6. Renumbering is a separate commit in the branch that merges second; references to the number are fixed there too.

## Why it is built this way

Two agents (pricing and in-app currency) each "checked the default branch and open branches" and both took
`D-1720...`. Both PRs merged, the default branch went red, and every PR and fast check failed until the fix
(renumbering `D-1720...1723` to `D-1760...1763`). A "is the number free" check against origin cannot see branches
another agent has not pushed yet, and "take, say, D-1600..." without a hard "only this range" is not followed.
