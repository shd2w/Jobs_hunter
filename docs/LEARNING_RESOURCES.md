# Free reading and manual practice

Open **Skill priorities**, expand **Optional reading & practice**, or run `python run_local.py learning`. The CLI/API keep the existing counts, source excerpts and contextual order, and add `resource_catalog` plus each priority's `learning_options`.

## When practice is shown

- Required/preferred cues: an optional reference and authored practice exercise are offered after reviewing the original listing and your own evidence.
- Negated-only: no resource or exercise is selected as a study recommendation.
- Mixed-only, ambiguous, plain or unclassified/stale context: clarify first; no practice is selected. A skill with required/preferred evidence in other vacancies can still receive optional practice, with all context buckets visible.
- Unknown skill or invalid catalog: explicit unsupported/unavailable message, never a generated URL or exercise. No matched guidance means no assigned tasks even though the bundled catalog has entries.

A mention gap is not proof of inability or a mandatory qualification. Practice never changes scores, exclusions, candidate evidence, statuses, packs, CVs or source approvals. Reading, opening a link or refreshing guidance does not record completion. **Phase 6f adds separate manual progress records; see [manual progress](LEARNING_PROGRESS.md).** Saving, status changes and completion require explicit actions; no automatic completion or candidate-fact promotion occurs.

## What is included

Seventeen English reading references cover the compact default technical/transferable lexicon. Each has a publisher, exact URL, topic list, checked date, observed topic excerpt and access/cost notes in `jobhunter_app/learning_catalog.json`. All target reading pages were retrieved and topic-reviewed on **2026-10-29** without supplying credentials. Verification is a dated readable-page/topic check, not a promise of future uptime, complete-course quality, enrollment, certificates or downstream links. The resource list below is the source record, not a claim that publishers endorse JobHunter.

| Skill | Public reading checked | Publisher |
|---|---|---|
| Python | [The Python Tutorial](https://docs.python.org/3/tutorial/index.html) | Python Software Foundation |
| SQL | [PostgreSQL Tutorial](https://www.postgresql.org/docs/current/tutorial.html) | PostgreSQL Global Development Group |
| JavaScript | [JavaScript Guide](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide) | MDN Web Docs / Mozilla contributors |
| TypeScript | [The TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html) | TypeScript / Microsoft |
| Machine learning | [Getting Started](https://scikit-learn.org/stable/getting_started.html) | scikit-learn developers |
| Data analysis | [Getting started tutorials](https://pandas.pydata.org/docs/getting_started/intro_tutorials/index.html) | pandas development team |
| Communication | [Effective communication in the workplace](https://www.open.edu/openlearn/mod/oucontent/view.php?id=97118) | The Open University / OpenLearn |
| Project management | [Project management: the start of the project journey](https://www.open.edu/openlearn/money-business/leadership-management/project-management-the-start-the-project-journey/content-section-0?intro=1) | The Open University / OpenLearn |
| Docker | [What is a container?](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/) | Docker |
| AWS | [AWS Cloud Essentials](https://aws.amazon.com/getting-started/cloud-essentials/) | Amazon Web Services |
| Git | [Pro Git, second edition](https://git-scm.com/book/en/v2) | Git project / Scott Chacon and Ben Straub |
| Excel | [Overview of formulas in Excel](https://support.microsoft.com/en-us/excel/get-started/overview-of-formulas-in-excel) | Microsoft Support |
| React | [React Quick Start](https://react.dev/learn) | React documentation team |
| Java | [General Tutorials / Learn Java](https://dev.java/learn/) | Dev.java / Oracle Java team |
| C++ | [Welcome back to C++ — Modern C++](https://learn.microsoft.com/en-us/cpp/cpp/welcome-back-to-cpp-modern-cpp?view=msvc-170) | Microsoft Learn |
| RAG | [Understand retrieval-augmented generation](https://learn.microsoft.com/en-us/training/modules/rag-fundamentals/2-understand-rag) | Microsoft Learn |
| Leadership | [Leadership and followership](https://www.open.edu/openlearn/mod/oucontent/view.php?id=147525) | The Open University / OpenLearn |

Each skill also has a **JobHunter-authored exercise**, not a publisher assignment: prerequisites, objective, author-estimated time, three concrete steps, a deliverable, three self-checks and setup/cost boundaries. Rubrics support self-review, not automated grading, qualifications or independent evidence verification. Exercises were authored and structurally tested; course/lab completion and executing every learner solution are not claimed.

Examples: a SQL LEFT JOIN must preserve a zero-count employer; Python validation preserves inputs and separates bad rows; Git resolves a local disposable conflict without publishing private files; cloud/container exercises offer a no-deployment paper/design route. RAG practice covers only retrieval/source-grounding design and explicitly does not test an LLM, embeddings or generation quality.

## Free reading is not a free service guarantee

- AWS/cloud labs can require accounts, payment details and billable services. This exercise creates no resources and requires no cloud account. Free Tier is not a guarantee of zero cost.
- Docker installation, image downloads and Desktop licensing are separate. The included practice can be completed as a text design without Docker.
- Excel software can require a license or account; paper formula tracing is the no-cost default. Compatible tools are not claimed to be identical to Excel.
- OpenLearn content can be read freely; enrolling, badges or saved provider progress may require an account. No enrollment was tested or performed.
- Optional programming exercises can require manually obtaining free local tools/packages. No dependency is added to the core app, no GPU is required, and no installation or download starts automatically.
- Do not upload CVs, candidate facts, private job records, credentials or employer materials to learning sites/sandboxes. Exercises use fictional or synthetic material.

## Review dates and safe offline behavior

Every report discloses the catalog's recorded check date and current UTC calendar day. `dated_check` means the packaged check is at most 90 days old, **not a live URL check**. Older checks show `review_due`; the recorded date is never refreshed by opening the dashboard. Future or malformed dates, missing/oversized/corrupt catalogs and invalid resource URLs disable the catalog safely while preserving context guidance. Known HTTPS publisher hosts are allowed; no runtime requests, affiliate links, models, course downloads or background link checks are made. Following a publisher link is an explicit browser action outside JobHunter.

`capabilities.verified_resources` and `exercise_catalog` describe the available **dated bundled catalog**, not live guarantees or learned competence; inspect `resource_catalog.status` and the dates. `learning_progress` now describes the separate manual-record workflow; private records and notes are never included in this guidance response. The asset is bounded to 150 KB, validated before use and copied into each response so callers cannot mutate later reports. Unavailable data is not silently replaced with fabricated content.

## Compatibility and backup

No schema/dependency/matcher/parser version change. Legacy frequency-sorted `priorities`, denominator and counts are unchanged. The UI still uses separate `contextual_order`. Existing source/cover/pack/manual-review/status workflows are retained. Install normally from the core lock; no new package is needed. Extract this release into a new private folder; original records/configuration remain bundled. Continue backing up filesystem packs/review events separately from SQLite.
