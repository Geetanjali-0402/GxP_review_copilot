"""streamlit_app.py (project root).  Run: streamlit run streamlit_app.py"""
import html
import json
import os
import re
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="GxP Review Copilot",
                   page_icon="assets/favicon.png", layout="wide")

try:  # Streamlit Cloud secrets -> env (must happen before importing app.*)
    for _k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "DATABASE_URL"):
        if _k in st.secrets and (st.secrets[_k] or _k == "LLM_BASE_URL"):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

from app.checklist import LLM_CHECKS  # noqa: E402
from app.llm import MODEL  # noqa: E402
from app.parser import extract_text, split_sections  # noqa: E402
from app.pipeline import analyze  # noqa: E402
from app.reviewer import PROMPT_VERSION, SYSTEM_PROMPT  # noqa: E402
from evaluate import KEYS_DIR  # noqa: E402
from evaluate import match as eval_match  # noqa: E402
from app import db  # noqa: E402

st.markdown("""<style>
.stApp{font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",sans-serif}
header[data-testid="stHeader"]{background:transparent}
.stAppDeployButton,#MainMenu{display:none}
.block-container{padding-top:2rem;max-width:1400px}
ssection[data-testid="stSidebar"],section[data-testid="stSidebar"]>div{background:#dbeafe;border-right:1px solid #c3d9f5}
[data-testid="stSidebar"] [role="radiogroup"]{gap:4px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:9px 14px;border-radius:10px;width:100%;cursor:pointer}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(255,255,255,.55)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#ffffff;color:#17468f;font-weight:600;box-shadow:0 1px 3px rgba(23,70,143,.15)}
.stButton>button,.stDownloadButton>button{border-radius:10px;border:1px solid #d5d9e0;background:#fff;color:#1f2430;font-weight:500;box-shadow:0 1px 1px rgba(16,24,40,.05);transition:.15s}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#2b6cb0;color:#2b6cb0;background:#f3f8ff}
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"]{background:#2b6cb0;border-color:#2b6cb0;color:#fff}
.stButton>button[kind="primary"]:hover,.stButton>button[data-testid="stBaseButton-primary"]:hover{background:#245a96;color:#fff}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px;border-color:#e6e6df}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"]{background:#fff;box-shadow:0 1px 3px rgba(16,24,40,.07)}
[data-testid="stExpander"]{border-radius:14px;border:1px solid #e6e6df;background:#fff}
textarea{border-radius:10px!important}
.banner{background:#fadfa6;color:#6b4a00;border-radius:12px;padding:14px 18px;font-weight:500;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.tile{background:#f5f5f2;border-radius:14px;padding:14px 20px}
.lbl{font-size:13px;color:#6b7280}.val{font-size:30px;font-weight:600;line-height:1.3}
.pill{display:inline-block;padding:3px 14px;border-radius:999px;font-size:13px;font-weight:600}
.pill-critical{background:#fbd3d3;color:#8a1c1c}.pill-major{background:#fbe3a6;color:#7a5200}
.pill-minor{background:#d3e5fb;color:#1c4f8a}.cat{color:#7a8190;margin-left:10px;font-size:14px}
.doc h4{font-size:17px;font-weight:600;margin:8px 0 4px}.doc p{font-size:15px;line-height:1.8;margin:0 0 16px}
mark.hl{background:#fde9b0;color:#222;padding:1px 5px;border-radius:5px}
mark.sel{background:#ffb454;box-shadow:0 0 0 2px #ff9a1f}
.ok{color:#1a7f37;font-weight:500}.no{color:#b42318;font-weight:500}
.usercard{display:flex;gap:10px;align-items:center;padding:10px 12px;background:#fff;border:1px solid #e6e6df;border-radius:12px;margin:8px 0}
.avatar{width:34px;height:34px;min-width:34px;border-radius:50%;background:#2b6cb0;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:600}
.who{display:flex;flex-direction:column;font-size:13px;line-height:1.3;overflow:hidden}
.who span{color:#7a8190;font-size:12px;overflow:hidden;text-overflow:ellipsis}
[data-testid="stSidebarUserContent"]>div>[data-testid="stVerticalBlock"]{min-height:calc(100vh - 7rem)}
.st-key-sb_bottom{margin-top:auto}
</style>""", unsafe_allow_html=True)

S = st.session_state
for k, v in {"decisions": {}, "log": [], "runs": [], "sel": None, "edit": None,
             "scroll": False, "report": None, "sections": []}.items():
    S.setdefault(k, v)


def _secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _auth_on():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


if _auth_on():  # Google sign-in required; every visitor is recorded
    if not st.user.is_logged_in:
        _, mid, _ = st.columns([1, 1.2, 1])
        with mid:
            st.markdown("<div style='height:18vh'></div>",
                        unsafe_allow_html=True)
            st.markdown("## GxP Review Copilot")
            st.write(
                "AI-assisted review of controlled documents, with human approval of every finding.")
            st.button("Sign in with Google", type="primary",
                      on_click=st.login, use_container_width=True)
            st.caption(
                "Signing in records your email, name and review decisions for the audit trail.")
        st.stop()
    USER = {"email": st.user.email, "name": st.user.name or st.user.email}
else:  # local development without auth configured
    USER = {"email": "dev@local", "name": "Local dev"}
_admins = {e.strip().lower()
           for e in str(_secret("ADMIN_EMAILS")).split(",") if e.strip()}
IS_ADMIN = (not _auth_on()) or USER["email"].lower() in _admins
if not S.get("visit_logged"):
    db.log_visit(USER["email"], USER["name"])
    S["visit_logged"] = True

rep = S["report"]
SEVS = ["critical", "major", "minor"]


def sev(f):
    return str(getattr(f.severity, "value", f.severity)).lower()


def tiles(items):
    cells = "".join(f'<div class="tile"><div class="lbl">{l}</div>'
                    f'<div class="val" style="color:{c}">{v}</div></div>' for l, v, c in items)
    st.markdown(f'<div class="grid">{cells}</div>', unsafe_allow_html=True)


def decide(i, action, edited=None):
    f, now = rep.findings[i], datetime.now()
    if action == "undo":
        S.decisions.pop(i, None)
    else:
        S.decisions[i] = {"action": action, "by": reviewer,
                          "at": now.strftime("%H:%M"), "edited": edited}
    db.save_decision(reviewer_email=USER["email"], reviewer_name=reviewer, document=rep.filename,
                     finding_id=i, section=f.section, category=f.category, severity=sev(
                         f),
                     action=action, original_text=f.finding, edited_text=edited or "")
    S.log.append({"time": now.isoformat(timespec="seconds"), "reviewer": reviewer,
                  "document": rep.filename, "finding": i, "section": f.section,
                  "category": f.category, "action": action, "edited_text": edited or ""})
    S.edit = None
    st.rerun()


def render_section(s, quotes, focus=False):
    esc, spans = html.escape(s["text"]), []
    for q, sel in quotes:
        words = html.escape(q).split()
        m = re.search(r"\s+".join(map(re.escape, words)),
                      esc, re.I) if words else None
        if m:
            spans.append((m.start(), m.end(), sel))
    out, pos = "", 0
    for a, b, sel in sorted(spans):
        if a < pos:
            continue
        cls = "hl sel sel-mark" if sel else "hl"
        out += esc[pos:a] + f'<mark class="{cls}">{esc[a:b]}</mark>'
        pos = b
    out += esc[pos:]
    head = '<h4 class="sel-mark sel-head">' if focus else "<h4>"
    return f"{head}{html.escape(s['title'])}</h4><p>{out.replace(chr(10), '<br>')}</p>"


PAGES = ["Review", "Observability", "Evaluation", "Audit trail",
         "Prompts"] + (["Visitors"] if IS_ADMIN else [])
reviewer = USER["name"]
with st.sidebar:
    st.markdown("### GxP Review Copilot")
    page = st.radio("nav", PAGES, label_visibility="collapsed")
    with st.container(key="sb_bottom"):
        st.caption(f"Model: {rep.llm_model if rep else MODEL}")
        st.caption(f"Prompt: {rep.prompt_version if rep else PROMPT_VERSION}")
        st.markdown(f'<div class="usercard"><div class="avatar">{html.escape(USER["name"][:1].upper())}</div>'
                    f'<div class="who"><b>{html.escape(USER["name"])}</b>'
                    f'<span>{html.escape(USER["email"])}</span></div></div>', unsafe_allow_html=True)
        if _auth_on():
            st.button("Sign out", on_click=st.logout, use_container_width=True)

# ------------------------------------------------------------------ Review
if page == "Review":
    st.markdown('<div class="banner">⚠️ AI-assisted review. Every finding needs human approval.</div>',
                unsafe_allow_html=True)
    with st.expander("Upload document", expanded=rep is None):
        up = st.file_uploader("SOP (PDF, DOCX, TXT)",
                              type=["pdf", "docx", "txt"])
        if up and st.button("Analyze", type="primary"):
            data = up.getvalue()
            try:
                with st.spinner("Reviewing section by section..."):
                    t0 = time.perf_counter()
                    r = analyze(data, up.name)
                    lat = time.perf_counter() - t0
                S.report, S.sections, S.decisions, S.sel, S.latency = (
                    r, split_sections(extract_text(data, up.name)), {}, None, lat)
                S.runs.append({"time": datetime.now().strftime("%H:%M:%S"), "document": up.name,
                               "model": r.llm_model, "prompt": r.prompt_version,
                               "latency_s": round(lat, 1), "findings": len(r.findings),
                               "llm_errors": r.llm_errors})
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if rep:
        if not rep.complete:
            st.warning(
                f"Partial review: {rep.llm_errors} section(s) failed (LLM error).")
        n = len(rep.findings)
        tiles([("Findings", n, "inherit"), ("Critical", rep.counts.get("critical", 0), "#b42318"),
               ("Reviewed", f"{len(S.decisions)}/{n}", "inherit"),
               ("Latency", f"{S.get('latency', 0):.1f}s", "inherit")])
        f1, f2, f3 = st.columns([2, 2, 1])
        shown_sev = f1.multiselect("Severity", SEVS, default=SEVS)
        status = f2.radio(
            "Status", ["All", "Pending", "Accepted", "Rejected"], horizontal=True)
        f3.download_button("Export", json.dumps({
            "report": json.loads(rep.model_dump_json()),
            "decisions": {str(k): v for k, v in S.decisions.items()}}, indent=2),
            f"{rep.filename}.reviewed.json", "application/json")

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Document: {rep.filename}**")
            with st.container(height=620, border=True):
                parts = []
                for s in S.sections:
                    if not s["text"] and s["title"] == "Preamble":
                        continue
                    qs = [(f.evidence_quote, i == S.sel) for i, f in enumerate(rep.findings)
                          if f.section == s["title"] and f.evidence_quote
                          and getattr(f, "evidence_verified", None) is not False]
                    sel_f = rep.findings[S.sel] if S.sel is not None and S.sel < len(
                        rep.findings) else None
                    focus = bool(sel_f and sel_f.section ==
                                 s["title"] and not any(sel for _, sel in qs))
                    parts.append(render_section(s, qs, focus))
                st.markdown(
                    f'<div class="doc">{"".join(parts)}</div>', unsafe_allow_html=True)
            if S.scroll:
                components.html("<script>setTimeout(()=>{const e=window.parent.document."
                                "querySelector('.sel-mark');if(e)e.scrollIntoView("
                                "{behavior:'smooth',block:'center'})},200)</script>", height=0)
                S.scroll = False
        with right:
            st.markdown("**Findings**")
            with st.container(height=620, border=True):
                for i, f in enumerate(rep.findings):
                    d = S.decisions.get(i)
                    st_name = d["action"] if d else "pending"
                    group = "accepted" if st_name == "edited" else st_name
                    if sev(f) not in shown_sev or (status != "All" and group != status.lower()):
                        continue
                    text = (d or {}).get("edited") or f.finding
                    with st.container(border=True):
                        st.markdown(f'<span class="pill pill-{sev(f)}">{sev(f).title()}</span>'
                                    f'<span class="cat">{f.category}</span>', unsafe_allow_html=True)
                        st.write(text)
                        ver = getattr(f, "evidence_verified", None)
                        ev = {True: f"✓ Evidence verified in {f.section}",
                              False: "⚠ Quote not found in document, check manually",
                              None: "Document-level finding"}[ver]
                        conf = getattr(f, "confidence", None)
                        st.caption(
                            ev + (f" · {conf:.0%} confidence" if conf is not None else ""))
                        if S.edit == i:
                            new = st.text_area(
                                "Edit finding", text, key=f"ta{i}")
                            c1, c2, _ = st.columns([1, 1, 3])
                            if c1.button("Save", key=f"sv{i}", type="primary"):
                                decide(i, "edited", new)
                            if c2.button("Cancel", key=f"cn{i}"):
                                S.edit = None
                                st.rerun()
                        elif d:
                            cls, word = ("no", "Rejected") if d["action"] == "rejected" else (
                                "ok", "Edited & accepted" if d["action"] == "edited" else "Accepted")
                            c1, c2 = st.columns([4, 1])
                            c1.markdown(f'<span class="{cls}">{word} by {d["by"]}, {d["at"]}</span>',
                                        unsafe_allow_html=True)
                            if c2.button("Undo", key=f"un{i}"):
                                decide(i, "undo")
                        else:
                            b = st.columns(4)
                            if b[0].button("Accept", key=f"ac{i}"):
                                decide(i, "accepted")
                            if b[1].button("Reject", key=f"rj{i}"):
                                decide(i, "rejected")
                            if b[2].button("Edit", key=f"ed{i}"):
                                S.edit = i
                                st.rerun()
                            if b[3].button("📍 Locate", key=f"lc{i}", disabled=(f.section == "Document"),
                                           help="Show this finding in the document"):
                                S.sel, S.scroll = i, True
                                st.rerun()

# ------------------------------------------------------------ Observability
elif page == "Observability":
    st.subheader("Observability")
    if S.runs:
        df = pd.DataFrame(S.runs)
        tiles([("Runs", len(df), "inherit"), ("Avg latency", f"{df.latency_s.mean():.1f}s", "inherit"),
               ("Findings", int(df.findings.sum()), "inherit"),
               ("LLM errors", int(df.llm_errors.sum()), "#b42318")])
        st.dataframe(df, use_container_width=True, hide_index=True)
        if rep:
            st.markdown("**Findings by category (latest run)**")
            st.bar_chart(
                pd.Series([f.category for f in rep.findings]).value_counts())
    else:
        st.info("No runs yet. Analyze a document on the Review page.")

# --------------------------------------------------------------- Evaluation
elif page == "Evaluation":
    st.subheader("Evaluation against answer key")
    m = re.match(r"(sop_\d+)", rep.filename) if rep else None
    kf = KEYS_DIR / f"{m.group(1)}.json" if m else None
    if not rep:
        st.info("Analyze a document first.")
    elif not kf or not kf.exists():
        st.info(
            "No answer key found for this document (expects names like sop_001_*.pdf).")
    else:
        if not rep.complete:
            st.warning(
                "Some LLM calls failed, so these metrics are unreliable.")
        keys = json.loads(kf.read_text())
        pairs, used = eval_match(keys, list(rep.findings))
        tiles([("Recall", f"{len(pairs)}/{len(keys)}", "inherit"),
               ("Precision", f"{len(used)}/{len(rep.findings)}", "inherit"),
               ("Accepted by reviewer", sum(1 for d in S.decisions.values()
                if d["action"] != "rejected"), "#1a7f37"),
               ("Rejected by reviewer", sum(1 for d in S.decisions.values() if d["action"] == "rejected"), "#b42318")])
        st.markdown("**Missed planted issues**")
        st.dataframe(pd.DataFrame([k for i, k in enumerate(keys) if i not in pairs]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Extra findings (not in key, review manually)**")
        st.dataframe(pd.DataFrame([{"severity": sev(f), "category": f.category, "section": f.section,
                                    "finding": f.finding} for i, f in enumerate(rep.findings)
                                   if i not in used]), use_container_width=True, hide_index=True)

# -------------------------------------------------------------- Audit trail
elif page == "Audit trail":
    st.subheader("Audit trail" + (" (all reviewers)" if IS_ADMIN else ""))
    rows = db.list_decisions(None if IS_ADMIN else USER["email"])
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(
            index=False), "audit_trail.csv", "text/csv")
    else:
        st.info("No review decisions recorded yet.")

# ------------------------------------------------------------------ Prompts
elif page == "Visitors":
    st.subheader("Visitors")
    users = db.visitors_summary()
    if users:
        df = pd.DataFrame(users)
        tiles([("Unique visitors", len(df), "inherit"), ("Total visits", int(df.visits.sum()), "inherit"),
               ("Decisions logged", len(db.list_decisions(None)), "inherit"),
               ("Last visit (UTC)", df.last_seen.max()[5:16].replace("T", " "), "inherit")])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("**Recent visits**")
        st.dataframe(pd.DataFrame(db.recent_visits()),
                     use_container_width=True, hide_index=True)
    else:
        st.info("No visits recorded yet.")

else:
    st.subheader(f"Prompts ({PROMPT_VERSION})")
    st.markdown("**System prompt**")
    st.code(SYSTEM_PROMPT, language="text")
    st.markdown("**Checks sent to the model**")
    st.dataframe(pd.DataFrame(LLM_CHECKS, columns=["id", "description"]),
                 use_container_width=True, hide_index=True)
