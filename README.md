# AI Communication Datasets

Version 0.1.0 · collected 12 October 2026 · Haocheng Wang, Communication University of China

Small, auditable X datasets for studying AI communication, with special attention
to personal agents: **Meta Muse, OpenAI Dots, and Grok Bot**. Collection, pagination,
relationship reconstruction, validation, and ID export use [pyXcom](https://github.com/haochengw372-hash/pyXcom).

The public download contains **post IDs, aggregate tables, protocols, and runnable
code**. Post text and ordinary-user profile data are not redistributed. You can
request currently available content with your own authenticated session. These
are bounded search candidates, not exhaustive or human-validated topic corpora.

## Datasets

| Directory | Retained unique IDs | Period / sampling |
| --- | ---: | --- |
| `data/personal_meta_muse` | 360 | Six weekly strata, 1 September–13 October 2026 |
| `data/personal_openai_dots` | 167 | Same weekly strata |
| `data/personal_grok_bot` | 360 | Same weekly strata |
| `data/institution_voices` | 313 | Four institutions × July, August, September 2026 |
| `data/ai_discourse` | 318 | AI / ChatGPT, four September weeks, English queries |
| `data/institution_conversations` | 449 | 8 selected roots + 441 observed replies |

**The personal-agent union has 862 IDs.** The product totals sum to 887 because
some posts match more than one product. The final weekly interval ends at
2026-10-13T00:00:00Z; only content available by the collection time was observable.
Dates are inclusive at the start and exclusive at the end, in UTC.

Each search stratum stops after two pages (general AI) or three pages (personal
agents), normally requesting 20 records per page. All search scopes here stopped
at a page limit. Counts measure retained records, not posting volume or product
popularity. Exact queries and selection rules are in [config](config/).

## Personal-agent relevance

`dot` refers here to **OpenAI Dots**, not New Computer's Dot. Muse excludes query
matches naming the Spark/Image/Audio models, and Grok Bot includes agent-related
context terms. The platform can still return same-name or broadly matched posts.

An AI-assisted diagnostic review sampled 20 records per product with a fixed seed:

| Product | Clearly personal-agent related | Clearly unrelated | Uncertain |
| --- | ---: | ---: | ---: |
| Meta Muse | 13 | 4 | 3 |
| OpenAI Dots | 10 | 8 | 2 |
| Grok Bot | 17 | 0 | 3 |

This is a single-AI textual review, not human gold-standard annotation or a
held-out accuracy estimate. The released query is revision 2; the broad initial
query and its failed disambiguation were kept locally as audit evidence. Review
relevance before using these IDs as a substantive coding sample. No sentiment,
occupation, demographic, or communicative-role labels are supplied.

Official product definitions: [Meta Muse](https://ai.meta.com/muse/),
[OpenAI Dots](https://openai.com/index/introducing-dots/),
[Grok Bot](https://docs.x.ai/grok-bot/overview).

## Get and check the data

```sh
pip install pyXcom==1.2.0
python scripts/validate_release.py --root .
pyxcom validate-ids data/personal_meta_muse/strata/personal_meta_muse_2026-09-01
```

`post_ids.csv` is a UTF-8, one-column CSV with header `post_id`; keep IDs as
strings. Group files are the deduplicated union of their source strata.
`manifest.json` records counts, source fingerprints, file hashes, and incomplete
coverage. Conversation IDs are released as one union without per-root membership.
All distributions and derived tables have checksums in `SHA256.json`.

Sign in to X yourself before collecting or rehydrating. pyXcom does not automate
browser login or publish browser credentials.

```sh
python scripts/rehydrate.py \
  data/personal_meta_muse/strata/personal_meta_muse_2026-09-01 \
  --profile Default --output /your/private/rehydrated --max-batches 1
```

This example requests at most 50 IDs. Unreturned posts are recorded separately;
a failed request or missing response is not proof of deletion. Network responses,
availability, engagement values and returned sets can change between runs.

## Recollect the specified samples

Raw output must be outside this repository:

```sh
python scripts/collect_personal_agents.py --profiles Default 'Profile 3' \
  --private-dir /your/private/personal_agents
python scripts/collect.py --stage search --profiles Default 'Profile 3' \
  --private-dir /your/private/general_ai
python scripts/collect.py --stage conversations --profiles Default \
  --private-dir /your/private/general_ai
python scripts/analyze.py --release-root . \
  --collections /your/private/general_ai/collections
```

Use a fresh directory for a new sampling run. Reopening the same queue resumes
its jobs, so another run can exceed the first-edition page budget. The release's
general-AI institutional and conversation sources were collected first; keyword
sources were recollected after a package UTC-query correction. Invalid early
keyword results were retained privately and excluded from released IDs and analysis.

The scripts use only the Python standard library and pyXcom. No paid model call
is required. Tests run with `python -m unittest discover -s tests -q`.

## Literature-derived analyses

Two accessible communication studies informed the examples:

1. **Kaiser & Green (2026), First Monday**: hashtag post-incidence, linked hostnames,
   and hashtag co-occurrence; [paper](https://doi.org/10.5210/fm.v31i4.14436).
2. **Hara et al. (2025), Journal of Science Communication**: observed root/reply
   structure, adapted here to institutional accounts;
   [paper](https://doi.org/10.22323/2.24010202).

These are **partial method adaptations on new data**. Original raw/annotated data
were not obtained, so original findings have not been computationally reproduced.
The second example substitutes organizations for the original expert frame; it
does not implement expert screening, role coding, BTM, or role regressions.
`references/methods.json` archives the initial protocol and original-method notes;
executed steps and deviations are recorded in [replications](replications/).

The AI search sample contains 318 unique posts, only nine with retained hashtags.
Under the prespecified publication threshold of three occurrences, no hashtag
nodes or edges remain publishable. Empty edge files are an observed result. The
conversation sample has 440 direct replies and one deeper reply; 5 were authored
by the root author and 436 by other accounts. These describe observed branches,
not complete conversations or representative public attitudes.

## Sharing, use and citation

Read [DATA_USE.md](DATA_USE.md) and [DATA_CARD.md](DATA_CARD.md). The Apache-2.0
license covers the code; it grants no rights to underlying X posts. This project
is not affiliated with Meta, OpenAI, SpaceXAI, or X. Please report the version and
sampling limits when citing this release; see [CITATION.cff](CITATION.cff).

For an ID removal/correction request, open a repository issue specifying only the
post ID and request. Do not copy personal details or deleted post text into issues.
