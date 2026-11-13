"""Application service: reads the original pipeline's data, performs on-click actions.

Everything here delegates to the ORIGINAL modules (CVTailor, CoverLetterWriter, pdf_generator,
TelegramNotifier, evaluation_store, JDCache). The original CLI scripts keep working unchanged and
produce data this layer reads. Constructing a Workspace changes the process working directory to the
project root, because the original modules use root-relative paths (config/, data/, output/, cv.md).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import ranking

STATUSES = ("new", "saved", "applied", "interview", "offer", "rejected", "archived")
GERMAN_POLICIES = ("reject_b1_plus", "reject_b2_plus_only", "reject_unless_bilingual", "accept_all")
KEY_NAMES = ("OpenRouter", "OpenRouter2", "OpenRouter3", "OpenRouter4",
             "GOOGLE_AI_API_KEY", "GOOGLE_AI_API_KEY2", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
AI_KEY_NAMES = KEY_NAMES[:6]
PROFILE_FIELDS = ("full_name", "short_name", "subtitle", "email", "phone", "location", "linkedin", "github")
CV_SECTIONS_USED = ("OBJECTIVE", "TECHNICAL SKILLS", "EXPERIENCE", "PROJECTS")
_PLACEHOLDER = re.compile(r"your-|-here|^your|second-key|third-key|fourth-key|first-key", re.I)


class ActionError(Exception):
    """A user-facing failure with a stable code and a plain-language message."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _real_key(v: str | None) -> bool:
    return bool(v) and not _PLACEHOLDER.search(v)


class Workspace:
    def __init__(self, root, *, tailor_factory=None, cover_factory=None, telegram_factory=None,
                 jd_fetcher=None, pdf_cv=None, pdf_cover=None):
        self.root = Path(root).resolve()
        os.chdir(self.root)
        load_dotenv(self.root / ".env", override=True)
        self.lock = threading.RLock()
        self._busy: set[str] = set()
        self.tailor_factory = tailor_factory
        self.cover_factory = cover_factory
        self.telegram_factory = telegram_factory
        self.jd_fetcher = jd_fetcher
        self.pdf_cv = pdf_cv
        self.pdf_cover = pdf_cover

    # ---------- paths ----------
    @property
    def p_eval(self): return self.root / "data" / "evaluations.json"
    @property
    def p_state(self): return self.root / "data" / "app_state.json"
    @property
    def p_profile(self): return self.root / "config" / "profile.yml"
    @property
    def p_cv(self): return self.root / "cv.md"
    @property
    def p_out(self): return self.root / "output"

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.root).as_posix()

    def resolve_artifact(self, value) -> Path | None:
        """Stored paths may use Windows separators and be relative; return an existing file inside root."""
        if not value:
            return None
        p = Path(str(value).replace("\\", "/"))
        p = (self.root / p) if not p.is_absolute() else p
        try:
            p = p.resolve()
            p.relative_to(self.root)
        except (OSError, ValueError):
            return None
        return p if p.is_file() else None

    def servable(self, rel_path: str) -> Path | None:
        p = self.resolve_artifact(rel_path)
        if not p:
            return None
        r = p.relative_to(self.root).parts
        if r[0] in ("output", "reports") or r in (("cv.pdf",), ("cv.md",)):
            return p
        return None

    # ---------- raw data ----------
    def _evals(self) -> list[dict]:
        from utils.evaluation_store import load_evaluations
        return load_evaluations(self.p_eval)

    def _state(self) -> dict:
        try:
            d = json.loads(self.p_state.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def profile(self) -> dict:
        try:
            d = yaml.safe_load(self.p_profile.read_text(encoding="utf-8")) or {}
            return d if isinstance(d, dict) else {}
        except (OSError, yaml.YAMLError):
            return {}

    def threshold(self) -> float:
        try:
            return float(self.profile().get("evaluation", {}).get("auto_cv_threshold", 3.5))
        except (TypeError, ValueError):
            return 3.5

    # ---------- jobs ----------
    def _artifacts(self, ev: dict) -> dict:
        def info(md_key, pdf_key, suffix):
            md, pdf = self.resolve_artifact(ev.get(md_key)), self.resolve_artifact(ev.get(pdf_key))
            if pdf and pdf.suffix.lower() != ".pdf":
                pdf = None
            kind = "tailored" if (md or pdf) and any(
                x and x.name.endswith(suffix) for x in (md, pdf)) else ("base" if md or pdf else None)
            return {"md": self.rel(md) if md else None, "pdf": self.rel(pdf) if pdf else None, "kind": kind}
        return {"cv": info("cv_path", "cv_pdf_path", "-cv.md"),
                "cover": info("cover_letter_path", "cover_letter_pdf_path", "-cover.md")}

    def _public(self, row: dict, state: dict) -> dict:
        ev, st = row["ev"], state.get(row["url"], {})
        arts = self._artifacts(ev)
        for a in arts.values():  # tailored kind must match the file name, base otherwise
            if a["pdf"] and not a["pdf"].endswith(("-cv.pdf", "-cover.pdf")):
                a["kind"] = "base"
        return {
            "id": row["id"], "rank": row["rank"], "url": row["url"], "score": row["score"],
            "original_score": row["original_score"], "tier": row["tier"],
            "company": ev.get("company") or ev.get("company_name") or "Unknown",
            "title": ev.get("title") or ev.get("job_title") or "Unknown",
            "date_posted": ev.get("date_posted") or "", "evaluated_at": ev.get("evaluated_at") or "",
            "recommendation": ev.get("recommendation") or "", "scores": ev.get("scores") or {},
            "german_required": bool(ev.get("german_required")),
            "german_level": ev.get("german_level_required") or "none",
            "summary": ev.get("summary") or "", "highlights": ev.get("match_highlights") or [],
            "gaps": ev.get("gaps") or [], "reasoning": ev.get("reasoning") or "",
            "model": ev.get("model_used") or "", "status": st.get("status", "new"),
            "note": st.get("note", ""), "artifacts": arts,
        }

    def list_jobs(self, *, weights=None, min_score=0.0, rec=None, q="", status="",
                  hide_german=True, only_ready=False) -> dict:
        w = ranking.parse_weights(weights) if weights else dict(ranking.DEFAULT_WEIGHTS)
        thr = self.threshold()
        rows = ranking.rank(self._evals(), w, thr)
        state = self._state()
        out, total = [], len(rows)
        ql = (q or "").strip().lower()
        for r in rows:
            j = self._public(r, state)
            if hide_german and j["recommendation"] == "skip_german":
                continue
            if j["score"] < min_score:
                continue
            if rec and j["recommendation"] not in rec:
                continue
            if status and j["status"] != status:
                continue
            if only_ready and not (j["artifacts"]["cv"]["pdf"]):
                continue
            if ql and ql not in f'{j["company"]} {j["title"]} {j["summary"]}'.lower():
                continue
            out.append(j)
        return {"jobs": out, "total": total, "shown": len(out), "threshold": thr,
                "weights": w, "custom_weights": not ranking.is_default(w)}

    def _row(self, jid: str) -> dict:
        for r in ranking.rank(self._evals(), None, self.threshold()):
            if r["id"] == jid:
                return r
        raise ActionError("not_found", "That job was not found. Reload the page.", 404)

    def job_detail(self, jid: str) -> dict:
        row = self._row(jid)
        j = self._public(row, self._state())
        from utils.jd_cache import JDCache
        c = JDCache(str(self.root / "data" / "jd_cache.json")).get(row["url"])
        j["description"] = (c or {}).get("description", "")
        return j

    def pending(self, limit=50) -> dict:
        try:
            from run_evaluate import get_pending_jobs
            jobs = get_pending_jobs(str(self.root / "data" / "pipeline.md"))
        except Exception:
            jobs = []
        return {"count": len(jobs), "jobs": jobs[:limit]}

    # ---------- state ----------
    def set_status(self, jid: str, status: str | None = None, note: str | None = None) -> dict:
        row = self._row(jid)
        if status is not None and status not in STATUSES:
            raise ActionError("bad_status", f"Status must be one of: {', '.join(STATUSES)}")
        if note is not None and len(note) > 2000:
            raise ActionError("note_too_long", "Notes are limited to 2000 characters.")
        with self.lock:
            st = self._state()
            cur = st.setdefault(row["url"], {})
            if status is not None:
                cur["status"] = status
            if note is not None:
                cur["note"] = note
            cur["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _atomic_write(self.p_state, json.dumps(st, ensure_ascii=False, indent=1))
        return self.job_detail(jid)

    def _update_eval(self, url: str, **fields) -> None:
        from utils.evaluation_store import append_evaluation
        with self.lock:
            cur = [e for e in self._evals() if e.get("url") == url]
            if not cur:
                raise ActionError("not_found", "Evaluation record missing.", 404)
            rec = dict(max(cur, key=lambda e: str(e.get("evaluated_at", ""))))
            rec.update(fields)
            append_evaluation(rec, self.p_eval)

    # ---------- availability ----------
    def ai_configured(self) -> bool:
        return any(_real_key(os.environ.get(k)) for k in AI_KEY_NAMES)

    def telegram_configured(self) -> bool:
        return _real_key(os.environ.get("TELEGRAM_BOT_TOKEN")) and _real_key(os.environ.get("TELEGRAM_CHAT_ID"))

    def _require_cv(self) -> None:
        if not self.p_cv.is_file():
            raise ActionError("no_cv", "Add your CV first (Setup → Your CV), then try again.")

    def _begin(self, key: str) -> None:
        with self.lock:
            if key in self._busy:
                raise ActionError("busy", "That is already running. Please wait for it to finish.", 409)
            self._busy.add(key)

    def _end(self, key: str) -> None:
        with self.lock:
            self._busy.discard(key)

    # ---------- documents ----------
    def _job_dict(self, row: dict, warnings: list) -> dict:
        ev = row["ev"]
        from utils.jd_cache import JDCache
        cache = JDCache(str(self.root / "data" / "jd_cache.json"))
        c = cache.get(row["url"])
        desc = (c or {}).get("description", "")
        if not desc:
            try:
                fetch = self.jd_fetcher
                if fetch is None:
                    import asyncio
                    from utils.jd_fetcher import fetch_jd
                    res = asyncio.run(asyncio.wait_for(fetch_jd(row["url"]), 30))
                    desc = res.text if res.success else ""
                else:
                    desc = fetch(row["url"]) or ""
                if desc:
                    cache.put(row["url"], desc, ev.get("title", ""), ev.get("company", ""), ev.get("date_posted", ""))
                    cache.save()
            except Exception:
                desc = ""
        if not desc:
            warnings.append("The full job description was not available, so the result is based on the "
                            "job title and company only. Open the job link and check it before using it.")
        return {"url": row["url"], "title": ev.get("title") or ev.get("job_title") or "Unknown",
                "company": ev.get("company") or ev.get("company_name") or "Unknown", "description": desc,
                "date_posted": ev.get("date_posted", "")}

    def _pdf_cv(self):
        if self.pdf_cv:
            return self.pdf_cv
        from utils.pdf_generator import generate_cv_pdf
        return generate_cv_pdf

    def _pdf_cover(self):
        if self.pdf_cover:
            return self.pdf_cover
        from utils.pdf_generator import generate_cover_letter_pdf
        return generate_cover_letter_pdf

    def create_cv(self, jid: str, mode: str = "tailored") -> dict:
        if mode not in ("tailored", "base"):
            raise ActionError("bad_mode", "Mode must be 'tailored' or 'base'.")
        row = self._row(jid)
        self._require_cv()
        key = f"cv:{jid}"
        self._begin(key)
        try:
            warnings: list[str] = []
            if mode == "base":
                pdf = self.root / "cv.pdf"
                if not pdf.is_file():
                    pdf = self.p_out / "base-cv.pdf"
                    res = self._pdf_cv()(md_content=self.p_cv.read_text(encoding="utf-8"), output_path=str(pdf))
                    if not res.get("success"):
                        raise ActionError("pdf_failed", "Could not create the PDF: " + str(res.get("error")))
                self._update_eval(row["url"], cv_path="cv.md", cv_pdf_path=self.rel(pdf))
            else:
                if not self.ai_configured():
                    raise ActionError("no_ai", "Tailoring needs an AI key. Add one in Setup, or choose "
                                               "'Use my CV as is' (no AI needed).")
                job = self._job_dict(row, warnings)
                if self.tailor_factory:
                    tailor = self.tailor_factory(cv_path=str(self.p_cv), output_dir=str(self.p_out))
                else:
                    from agents.cv_tailor import CVTailor
                    tailor = CVTailor(cv_path=str(self.p_cv), output_dir=str(self.p_out))
                res = tailor.tailor(job)
                if not res.get("success"):
                    raise ActionError("ai_failed", "The AI could not tailor the CV right now: "
                                      + str(res.get("error", "unknown error")) + ". Try again in a minute.", 502)
                md = res["output_path"]
                pdf_out = str(md).replace("-cv.md", "-cv.pdf")
                pr = self._pdf_cv()(md_content=res.get("content", ""), output_path=pdf_out, subtitle=res.get("subtitle"))
                fields = {"cv_path": self.rel(Path(md)), "tailored_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                if pr.get("success"):
                    fields["cv_pdf_path"] = self.rel(Path(pdf_out))
                else:
                    warnings.append("The CV text was created but the PDF could not be made "
                                    f"({pr.get('error')}). See Setup → PDF support.")
                self._update_eval(row["url"], **fields)
            d = self.job_detail(jid)
            d["warnings"] = warnings
            return d
        finally:
            self._end(key)

    def create_cover(self, jid: str) -> dict:
        row = self._row(jid)
        self._require_cv()
        if not self.ai_configured():
            raise ActionError("no_ai", "Cover letters need an AI key. Add one in Setup.")
        key = f"cover:{jid}"
        self._begin(key)
        try:
            warnings: list[str] = []
            job = self._job_dict(row, warnings)
            if self.cover_factory:
                writer = self.cover_factory(cv_path=str(self.p_cv), output_dir=str(self.p_out))
            else:
                from agents.cover_letter import CoverLetterWriter
                writer = CoverLetterWriter(cv_path=str(self.p_cv), output_dir=str(self.p_out))
            res = writer.generate(job, row["ev"])
            if not res.get("success"):
                raise ActionError("ai_failed", "The AI could not write the cover letter right now: "
                                  + str(res.get("error", "unknown error")) + ". Try again in a minute.", 502)
            md = res["output_path"]
            pdf_out = str(md).replace("-cover.md", "-cover.pdf")
            pr = self._pdf_cover()(md_content=res.get("content", ""), output_path=pdf_out,
                                   company=job["company"], role=job["title"])
            fields = {"cover_letter_path": self.rel(Path(md))}
            if pr.get("success"):
                fields["cover_letter_pdf_path"] = self.rel(Path(pdf_out))
            else:
                warnings.append(f"The letter text was created but the PDF could not be made ({pr.get('error')}).")
            self._update_eval(row["url"], **fields)
            d = self.job_detail(jid)
            d["warnings"] = warnings
            return d
        finally:
            self._end(key)

    def send_telegram(self, jid: str) -> dict:
        if not self.telegram_configured():
            raise ActionError("no_telegram", "Telegram is not set up. Add the bot token and chat ID in Setup.")
        j = self.job_detail(jid)
        files = []
        for a in j["artifacts"].values():
            pick = a["pdf"] or a["md"]
            if pick:
                files.append(self.root / pick)
        if not files:
            raise ActionError("nothing_to_send", "Create a CV or cover letter first, then send it.")
        tg = self.telegram_factory() if self.telegram_factory else __import__(
            "utils.telegram", fromlist=["TelegramNotifier"]).TelegramNotifier()
        sent = [f.name for f in files if tg.send_document(str(f), caption=f'{j["company"]} — {j["title"]}')]
        if not sent:
            raise ActionError("telegram_failed", "Telegram did not accept the files. Check the token and chat ID.", 502)
        return {"sent": sent}

    # ---------- setup ----------
    def cv_status(self) -> dict:
        if not self.p_cv.is_file():
            return {"exists": False, "ok": False, "sections": [], "missing": list(CV_SECTIONS_USED)}
        try:
            from agents.cv_tailor import _split_cv_sections
            _, secs = _split_cv_sections(self.p_cv.read_text(encoding="utf-8"))
            names = list(secs.keys())
        except Exception:
            names = []
        missing = [s for s in CV_SECTIONS_USED if s not in names]
        return {"exists": True, "ok": not missing, "sections": names, "missing": missing}

    def pdf_status(self) -> dict:
        try:
            import weasyprint  # noqa: F401  (availability probe)
            return {"ok": True, "error": ""}
        except Exception as e:  # missing GTK/Pango raises OSError
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}

    def setup_status(self) -> dict:
        prof = self.profile()
        cand = prof.get("candidate", {}) or {}
        ev = prof.get("evaluation", {}) or {}
        return {
            "cv": self.cv_status(),
            "profile": {**{k: str(cand.get(k, "") or "") for k in PROFILE_FIELDS},
                        "auto_cv_threshold": self.threshold(),
                        "german_filter": ev.get("german_filter", "accept_all"),
                        "create_cv": bool(ev.get("create_cv", False))},
            "ai": {"configured": self.ai_configured(),
                   "keys": {k: _real_key(os.environ.get(k)) for k in AI_KEY_NAMES}},
            "telegram": {"configured": self.telegram_configured()},
            "pdf": self.pdf_status(),
            "counts": {"evaluated": len({e.get("url") for e in self._evals() if e.get("url")}),
                       "pending": self.pending(0)["count"]},
            "german_policies": list(GERMAN_POLICIES), "statuses": list(STATUSES),
        }

    def save_cv(self, text: str) -> dict:
        text = (text or "").replace("\r\n", "\n")
        if len(text.encode("utf-8")) > 200_000:
            raise ActionError("too_big", "That CV is too large (limit 200 KB).")
        if len(re.findall(r"^## \*\*.+\*\*\s*$", text, re.M)) < 2:
            raise ActionError("bad_format", "This does not look like the JobHunter CV format. Section headers "
                              "must look like  ## **EXPERIENCE** . Use the example or the 'Convert with AI' button.")
        with self.lock:
            if self.p_cv.exists():
                _atomic_write(self.root / "cv.md.bak", self.p_cv.read_text(encoding="utf-8"))
            _atomic_write(self.p_cv, text)
        return self.cv_status()

    def convert_cv_with_ai(self, raw_text: str) -> str:
        if not self.ai_configured():
            raise ActionError("no_ai", "Converting needs an AI key. Add one in Setup first.")
        if not (raw_text or "").strip() or len(raw_text) > 60_000:
            raise ActionError("bad_input", "Paste your CV text (up to 60,000 characters).")
        from agents.smart_router import SmartRouter
        r = SmartRouter().generate(
            system_prompt=("Convert the user's CV into this exact markdown format and output ONLY the markdown. "
                           "Never invent facts, dates, employers or skills; copy only what is present. Headers: "
                           "'# **NAME**', then '**Title**', contact lines, then sections '## **OBJECTIVE**', "
                           "'## **EDUCATION**', '## **TECHNICAL SKILLS**', '## **EXPERIENCE**', '## **PROJECTS**', "
                           "'## **CERTIFICATIONS & TRAINING**', '## **LANGUAGES**'. Titles/degrees in **bold**; dates "
                           "and companies in *italics*; experience as '*Company, Location | 2024 – Present*'; "
                           "bullets start with '* '."),
            user_prompt=raw_text, temperature=0.1, max_tokens=4096)
        if not r.success:
            raise ActionError("ai_failed", "The AI could not convert the CV: " + str(r.error), 502)
        out = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", r.content.strip())
        return out

    def save_keys(self, values: dict) -> dict:
        envp = self.root / ".env"
        clean: dict[str, str] = {}
        for k, v in (values or {}).items():
            if k not in KEY_NAMES:
                raise ActionError("bad_key", f"Unknown setting: {k}")
            v = (v or "").strip()
            if v and (len(v) > 300 or re.search(r"\s", v)):
                raise ActionError("bad_value", f"{k} must be a single line without spaces.")
            clean[k] = v
        with self.lock:
            lines = envp.read_text(encoding="utf-8").splitlines() if envp.exists() else []
            seen = set()
            out = []
            for ln in lines:
                m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=", ln)
                if m and m.group(1) in clean:
                    seen.add(m.group(1))
                    if clean[m.group(1)]:
                        out.append(f"{m.group(1)}={clean[m.group(1)]}")
                else:
                    out.append(ln)
            out += [f"{k}={v}" for k, v in clean.items() if v and k not in seen]
            _atomic_write(envp, "\n".join(out) + "\n")
            try:
                os.chmod(envp, 0o600)
            except OSError:
                pass
            for k, v in clean.items():
                if v:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)
        return self.setup_status()

    def save_profile(self, data: dict) -> dict:
        prof = self.profile()
        cand = prof.setdefault("candidate", {}) or {}
        ev = prof.setdefault("evaluation", {}) or {}
        for k in PROFILE_FIELDS:
            if k in data:
                v = str(data[k] or "").strip()
                if len(v) > 300 or "\n" in v:
                    raise ActionError("bad_value", f"{k} is too long or has line breaks.")
                cand[k] = v
        if "auto_cv_threshold" in data:
            try:
                t = float(data["auto_cv_threshold"])
            except (TypeError, ValueError):
                raise ActionError("bad_value", "Threshold must be a number between 1 and 5.")
            if not 1 <= t <= 5:
                raise ActionError("bad_value", "Threshold must be between 1 and 5.")
            ev["auto_cv_threshold"] = round(t, 1)
        if "german_filter" in data:
            if data["german_filter"] not in GERMAN_POLICIES:
                raise ActionError("bad_value", "Unknown German filter option.")
            ev["german_filter"] = data["german_filter"]
        if "create_cv" in data:
            ev["create_cv"] = bool(data["create_cv"])
        prof["candidate"], prof["evaluation"] = cand, ev
        with self.lock:
            if self.p_profile.exists():
                _atomic_write(self.root / "config" / "profile.yml.bak", self.p_profile.read_text(encoding="utf-8"))
            _atomic_write(self.p_profile, yaml.safe_dump(prof, allow_unicode=True, sort_keys=False))
        return self.setup_status()
