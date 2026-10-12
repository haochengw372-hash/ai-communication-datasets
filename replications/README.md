# Literature-derived analyses

These are **new-sample method adaptations**, not reproductions of either paper's
original estimates. Both articles were read for the protocol; the original
interaction data, coding matrix, and complete analysis implementations were not
available in the reviewed material. The exact deviations appear in
`deviation_matrix.csv`.

## AI discourse: hashtag and linked-host incidence

Kaiser, J., & Green, C. (2026). *Artificial intelligence in the networked public
sphere: An analysis of the AI discourse on Twitter*. First Monday, 31(4).
https://doi.org/10.5210/fm.v31i4.14436

We adapt the descriptive hashtag/domain rankings and hashtag co-occurrence
analysis (methods on PDF file pages 5–6; Tables 2–3 on page 7). The retained
corpus comes from bounded Latest searches of AI and ChatGPT over prespecified
weekly UTC windows. These are convenience strata; they do not estimate the
complete AI conversation or its population prevalence.

The canonical input fields are `id`, `post_role`, `post_type`, `language`,
`created_at_utc`, `hashtags`, `outbound_urls`, and `observation_role`.
Across lexicographically ordered scopes, the first saved analysis observation per ID is retained;
context observations are excluded. Primary tables exclude native reposts.
`all_retained_*` tables repeat term/edge analyses including reposts.
Missing language is a separate category; `lang:en` in a search does not prove
that all returned records are English. Empty lists mean no retained entities,
not independently verified absence of hashtags/links from the platform.

Each distinct hashtag counts once per post. Case-sensitive counts preserve
spelling; casefold counts merge case variants. The network uses casefold tags,
removes `ai` and `artificialintelligence`, and counts each unordered pair once
per post. No community or sentiment labels are inferred. A node's weighted
degree sums edge incidences before publication suppression; it is not a count
of unique posts.

URL processing uses structured `outbound_urls`, never guesses destinations
from post text and never follows links. Hostnames are lowercased and trailing
dots removed; `www` remains distinct. Hostnames are not registrable domains.
Unexpanded `t.co` links and URLs containing userinfo are excluded and counted.
Repeated links to one hostname count once per post.

## Organization–public conversation structure

Hara, N., Kim, E., Akter, S., & Miyazaki, K. (2025). *Exploring the dynamics of
interaction about generative artificial intelligence between experts and the
public on social media*. Journal of Science Communication, 24(01), A02.
https://doi.org/10.22323/2.24010202

We adapt only the organization of root–reply observations and the requirement
for at least three retained replies before possible manual coding (collection
and sampling: PDF file page 6; original role scheme: Table 5, file page 10).
The original study sampled people whose profiles indicated expert roles.
Our roots are from named institutions: this is an **organization–public
adaptation**, and institutions have not been relabelled scientists or experts.

The controller freezes the institutional root candidate frame before choosing
roots. For each institution, the rule selects the earliest and latest retained
September original main post with displayed reply count at least three.
Displayed counts screen candidate roots but do not establish retained-reply
eligibility. An actual resolved parent chain to a retained root is required
for the analysis's at-least-three-reply eligibility measure.

The analysis follows canonical `in_reply_to_id` pointers with cycle detection.
Retained context ancestors can resolve a chain but do not enter reply denominators.
Missing parents, absent roots, and contradictory `conversation_id` are
reported separately; no depth is guessed. Author relationships are
`root_author`, `other_author`, or `unknown`. Other authors are not assumed
laypeople. All retained reply counts and resolved-reply counts are distinct.
This is a bounded observation of available branches, not the entire thread.

The annotation template contains column headers only. It supplies no inferred
semantic role, excerpt, or publicly paired post/author metadata. Biterm topics,
manual role percentages, and negative-binomial role effects are not reproduced.

## Re-run and disclosure

Run against a locally retained or newly collected pyXcom canonical corpus:

```sh
python3 scripts/analyze.py --release-root . --collections /your/local/collections
python3 -m unittest discover -s tests -p test_analysis.py -v
```

The portable command runs in a cloned release repository and reads `config/sampling.json`
and `references/methods.json`; it does not require private governance files. The
methods reference is an **original protocol archive**, not a claim that all its
proposed steps were executed; executed scope is defined by the deviation matrix
and run manifests. For the original governed project, the compatible command is
`python3 release/scripts/analyze.py --project . --collections private_verified/collections`.

When the controller designates a replacement collection directory, explicitly
pass that directory. Do not merge legacy failed scopes with the replacement.
The frozen `selected_roots.json` beside the chosen `collections/` directory uses a list of objects with
`post_id`; conversation directories must match `conversation_<post_id>`.
The script verifies canonical and table hashes before reading. Inputs remain
private and unchanged. The release's ID files alone cannot reproduce text or
entity analyses without authorized re-collection, and changed/deleted records
can prevent exact reruns.

Public term/edge CSV rows require incidence ≥3 and safe token/hostname syntax;
other aggregate CSV cells below three are suppressed. The manifests retain
original denominators and category counts for methodological inspection, with
no per-user or per-post links. Suppression does not constitute a formal
anonymity guarantee. No raw text, author IDs, or root–reply pairs are exported.
`analysis_outputs.json` hashes produced files. No sample size, original finding,
or successful completion should be inferred from a protocol alone: consult
each executed manifest's status, counts, and coverage.
