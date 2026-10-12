# Dataset card

## Purpose and scope

This first edition supports teaching, sampling design, method adaptation, and
research on public AI communication. The personal-agent component centers Meta
Muse, OpenAI Dots and Grok Bot. It includes posts selected by explicitly bounded
Latest search queries, not a representative population sample.

## Units and fields

- Public `post_ids.csv`: one positive decimal X post ID per row, sorted numerically,
  deduplicated, represented as text.
- Group manifests: retained counts, per-stratum counts, SHA256 fingerprints,
  incomplete coverage and ID union hash. Conversation manifests use anonymous
  stratum labels; individual root-to-reply membership is not published.
- Per-stratum exports: pyXcom's strict `post_ids.csv` / `manifest.json` format;
  source `analysis` and `seed` records are eligible, `context` records are excluded.
- Aggregates: literal hashtag incidence, hostname incidence, unordered hashtag
  co-occurrence counts and observed conversation structure. A term or CSV category
  is published only at count ≥3; denominator and suppression counts remain visible.

No source text, usernames of ordinary participants, profiles, observer account
identity, tokens, timestamps per individual post, or per-post engagement values
are included in the public ID files. Rehydration can recover currently available
public fields subject to the recipient's access; IDs are **not anonymized data**.

## Sampling and preprocessing

Institution voices: OpenAI, AnthropicAI, GoogleDeepMind and MistralAI; three
calendar-month strata in July–September 2026; two pages each. Native search can
return authored replies, which are retained with their role in the private data.

General discourse: `AI lang:en -filter:retweets` and
`ChatGPT lang:en -filter:retweets`, four weekly September strata; two pages each.
Duplicate post IDs across the two queries are counted once in analysis.

Personal agents: revision-2 product-context queries in config/personal_agents.json,
six weekly strata, three pages each. No language restriction or automatic
translation. Case-insensitive product matching is delegated to the native search;
its results still require relevance screening. Fixed query revision and bounds
are disclosed rather than claiming perfect filtering.

Conversations: for each institution, select the earliest and latest retained
September original main post with observed platform reply_count ≥3. The complete
candidate frame is kept locally. Collect up to 60 replies and depth 2, at most
three pages. Seven roots stopped at comment_limit; one stopped at page_limit.
Actual retained resolved replies—not the displayed reply count—determine the
analysis's ≥3-reply eligibility.

## Data quality and limits

All retained scopes passed pyXcom validation. All personal-agent dates fall in
their declared half-open UTC intervals. Passing integrity checks does not establish
exhaustive coverage. Deleted, inaccessible, hidden, delayed or unreturned records
are absent. Quoted/context records are distinguished from primary observations.

An AI diagnostic review found unrelated and uncertain personal-agent matches;
see README. Labels were not assigned to the full corpus. Product totals differ in
query specificity, publication history, and candidate relevance, so do not compare
them as popularity measures. Users replying are described as other accounts,
not automatically as laypeople or non-experts.

## Reproducibility and provenance

Collection uses pyXcom with existing manually authenticated browser sessions.
New explicit date parameters include precise UTC epoch query bounds and local
half-open filtering. Legacy institutional samples retained their original date
expression; invalid early broad-query samples were excluded and recollected.
Code, exact queries, limits, input/output fingerprints and result manifests are
included. Private raw responses and observer bindings remain local.

The two literature examples reimplement selected descriptive operations on a
new sample. Full original-result replication is not established. Sparse hashtag
results and unimplemented semantic analyses are reported explicitly.
