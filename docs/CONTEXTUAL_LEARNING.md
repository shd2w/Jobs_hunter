# Contextual skill guidance

Open **Skill priorities**, or run `python run_local.py learning`. Configure your supported skills/facts and explicitly refresh matches first. **Refresh guidance** reads stored matches only: it does not scan, run matching, update evidence, record learning, prepare a pack or change an application.

## Counts and order

The denominator remains distinct currently stored, locally matched, non-excluded vacancies. Unmatched jobs are not included. Valid legacy mention counts (`vacancies_reviewed` and each priority's `vacancies`) and frequency-sorted `priorities` remain intact. A negated mention still counts as a mention. Excluded, invalid, unmatched and stale-context coverage is shown separately; stale stored matches can contribute legacy counts but never positive contextual evidence.

Each skill/vacancy belongs to exactly one bucket: required cue, preferred cue, mixed labels, ambiguous cue, plain mention, negated cue or unclassified. Repeated clauses with the same label do not inflate vacancy counts. Multiple different labels for the same skill in one vacancy become mixed, including required plus negated. These seven bucket counts sum to that skill's mention count; different skills' counts overlap and must not be added into a job total.

The UI uses a separate `contextual_order`: required cues, preferred cues, clarify-first (mixed/ambiguous/unclassified), plain mentions, then negated-only. Within tiers it sorts required counts, preferred counts and total mentions descending, then skill name. A skill can have positive evidence in one vacancy and negative evidence in another; the counts and rationale expose both. Negated-only cues create no study priority. Plain mentions and unknowns are not presented as requirements. This is a transparent heuristic, not market demand, a mandatory-requirement count, qualification judgement or suitability score.

## Exact source evidence

Expand **Source excerpts** for original listing links, literal quotes, classification and description offsets. At most eight samples per skill and 600 characters per excerpt are shown, balanced deterministically across available context buckets. Counts cover all included vacancies, not just samples. Samples are not exhaustive; a single vacancy may provide multiple excerpts. Shortened samples disclose the full clause end; the label came from the stored full clause, potentially with an inherited heading. Inspect the full original before acting. Links open only when a validated original HTTP(S) URL is available; report generation does not fetch them.

Context is reused only when stored matcher/language/eligibility versions and job/profile fingerprints match current inputs. Missing, stale, malformed, unverifiable or truncated context becomes unclassified rather than a positive priority. At the parser's 300-clause limit, affected vacancy guidance is conservative even if some exact samples remain usable. Invalid cached match records are explicitly omitted. **Refresh matches** is the separate manual action to rebuild derived context after profile/listing changes.

## Interpretation and limits

The existing compact skill lexicon and narrow English/German/Arabic cues are incomplete rule-based parsing, not broad language understanding. Negation, alternatives, inherited headings, long split clauses and mixed wording can be misunderstood. Current fingerprints mean current inputs, not independently verified requirements. Candidate evidence marked not recorded is not evidence of inability. A learning hint never adds candidate experience, changes a score/exclusion or edits a CV. Empty results mean no usable matched guidance or no lexical gaps, not mastery or eligibility.

Phase 6e adds dated public reading and original exercises for current required/preferred guidance; see [resource/practice guide](LEARNING_RESOURCES.md). Phase 6f adds separate [manual learning-progress records](LEARNING_PROGRESS.md); no completion records are invented automatically and context counts remain unaffected. The Phase 6d counts/context contract remains unchanged. Schema 5, dependencies, matching/parser versions, preparation/version/review behavior and original CVs are unchanged. Optional AI/real-model work remains deferred, not passed and not a blocker.
