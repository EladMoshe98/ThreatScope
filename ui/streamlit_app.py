"""
ThreatScope — Streamlit UI for the NER service.

A thin client: it uploads one text file to the FastAPI service (`/predict`) and
renders the results. Set API_URL to point at the API (default localhost for dev,
http://api:8000 inside docker-compose).
"""
import html
import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
MAX_FILE_SIZE_MB = os.getenv("MAX_FILE_SIZE_MB", "2")

# --- SecureBERT-NER native classes: display order, meaning/example, and colour ---
SECUREBERT_CLASSES = [
    "APT", "SECTEAM", "IDTY", "ACT", "OS", "TOOL",
    "VULID", "VULNAME", "MAL",
    "FILE", "DOM", "ENCR", "IP", "URL", "MD5", "PROT", "EMAIL", "SHA1", "SHA2",
    "TIME", "LOC",
]
SB_ENTITY_INFO = {
    "APT": ("Threat participants", "APT32, OceanLotus"),
    "SECTEAM": ("Security team", "Cisco, FireEye"),
    "IDTY": ("Authentication identity", "Google"),
    "ACT": ("Attack action", "Spear phishing"),
    "OS": ("Operating system", "Windows"),
    "TOOL": ("Tool", "PowerShell, Nmap"),
    "VULID": ("Vulnerability number", "CVE-2016-4117"),
    "VULNAME": ("Vulnerability name", "zero-day"),
    "MAL": ("Malware", "Cobalt Strike, Trojan.SH.MALXMR"),
    "FILE": ("File sample", "at.exe"),
    "DOM": ("Domain", "globalowa.com"),
    "ENCR": ("Encryption algorithm", "DES"),
    "IP": ("IP address", "109.248.148.42"),
    "URL": ("URL", "http://shwoo.gov.taipei/buyer_flowchart.asp"),
    "MD5": ("Hash value (MD5)", "11a9f798227be8a53b06d7e8943f8d68"),
    "PROT": ("Protocol", "HTTP"),
    "EMAIL": ("Malicious mailbox", "uglygorilla@163.com"),
    "SHA1": ("Hash value (SHA1)", "906dc86cb466c1a22cf847dda27a434d04adf065"),
    "SHA2": ("Hash value (SHA2)", "4741c2884d1ca3a40dadd3f3f61cb95a…"),
    "TIME": ("Time", "April 2018"),
    "LOC": ("Location", "China"),
}
# colour each class by its high-level family so related tags read together
_FAMILY_COLOR = {
    "Organization": "#2a78d6", "System": "#4a3aa7", "Vulnerability": "#1baf7a",
    "Malware": "#eda100", "Indicator": "#008300", "Time": "#e87ba4", "Area": "#e34948",
}
_SB_FAMILY = {
    "APT": "Organization", "SECTEAM": "Organization", "IDTY": "Organization",
    "ACT": "System", "OS": "System", "TOOL": "System",
    "VULID": "Vulnerability", "VULNAME": "Vulnerability", "MAL": "Malware",
    "FILE": "Indicator", "DOM": "Indicator", "ENCR": "Indicator", "IP": "Indicator",
    "URL": "Indicator", "MD5": "Indicator", "PROT": "Indicator", "EMAIL": "Indicator",
    "SHA1": "Indicator", "SHA2": "Indicator", "TIME": "Time", "LOC": "Area",
}
SB_COLORS = {c: _FAMILY_COLOR[_SB_FAMILY[c]] for c in SECUREBERT_CLASSES}

# benchmark common classes (for the static comparison chart order)
COMMON_CLASSES = ["Organization", "System", "Vulnerability", "Malware", "Indicator", "Time", "Area"]

st.set_page_config(page_title="ThreatScope — NER", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.5rem; max-width: 1120px; }
      h1 { font-weight: 700; letter-spacing: -0.02em; }
      table td, table th { font-size: 0.92rem; }
      thead tr th { background: #F4F6F9 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- helpers
def api_health():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None


def render_highlight(text: str, entities: list) -> str:
    """Escape the document text (XSS-safe) and wrap detected spans in colored marks."""
    out, pos = [], 0
    for e in sorted(entities, key=lambda x: x["start"]):
        s, end = e["start"], e["end"]
        if s < pos:
            continue  # skip overlaps
        out.append(html.escape(text[pos:s]))
        color = SB_COLORS.get(e["label"], "#888888")
        span = html.escape(text[s:end])
        out.append(
            f'<mark style="background:{color}22;border-bottom:2px solid {color};'
            f'border-radius:3px;padding:0 3px;">{span}'
            f'<sub style="color:{color};font-weight:600;font-size:0.7em;">&nbsp;{e["label"]}</sub></mark>'
        )
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


def legend(present: set) -> str:
    chips = [
        f'<span style="background:{SB_COLORS[c]}22;border-bottom:2px solid {SB_COLORS[c]};'
        f'padding:1px 8px;border-radius:3px;margin-right:8px;font-size:0.8rem;">{c}</span>'
        for c in SECUREBERT_CLASSES if c in present
    ]
    return "".join(chips)


# --------------------------------------------------------------------------- header
st.title("ThreatScope")
st.caption("Named-entity recognition for cyber-threat-intelligence")
st.markdown("**Model:** SecureBERT-NER")
with st.expander("Model details"):
    st.markdown(
        "- **Source:** `CyberPeace-Institute/SecureBERT-NER` — RoBERTa fine-tuned on the APTNER corpus.\n"
        "- **Size:** ~124M parameters · CPU inference.\n"
        "- **Entity classes:** 21 fine-grained cyber-threat-intel types (see the reference in the Analyze tab)."
    )

_health = api_health()
if _health:
    st.markdown('<p style="color:#0a7d33;font-weight:600;">&#9679; System online</p>', unsafe_allow_html=True)
else:
    st.markdown(
        '<p style="color:#c0392b;font-weight:600;">&#9679; System offline '
        f'<span style="color:#6b7280;font-weight:400;">— cannot reach the API at {API_URL}.</span></p>',
        unsafe_allow_html=True,
    )

st.divider()
tab_analyze, tab_compare, tab_history = st.tabs(["Analyze", "Model Comparison", "History"])


# --------------------------------------------------------------------------- Analyze
with tab_analyze:
    st.subheader("Analyze a document")
    st.markdown(
        f"Upload a text file to extract named entities. "
        f"**Accepted:** `.txt` files only · up to **{MAX_FILE_SIZE_MB} MB** · **one file at a time**."
    )

    with st.expander("Entity classes — meaning & examples"):
        ref = pd.DataFrame(
            [{"Class": c, "Meaning": SB_ENTITY_INFO[c][0], "Example": SB_ENTITY_INFO[c][1]}
             for c in SECUREBERT_CLASSES]
        )
        st.table(ref)

    uploaded = st.file_uploader(
        "Drag and drop a .txt file onto the box below, or click Browse",
        type=["txt"], accept_multiple_files=False,
    )

    if uploaded is not None and st.button("Run extraction", type="primary"):
        with st.spinner("Extracting entities…"):
            try:
                resp = requests.post(
                    f"{API_URL}/predict",
                    files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")},
                    timeout=120,
                )
            except requests.RequestException as exc:
                st.session_state.pop("result", None)
                st.error(f"Request failed: {exc}")
            else:
                if resp.status_code != 200:
                    st.session_state.pop("result", None)
                    st.error(f"Rejected: {resp.json().get('detail', resp.text)}")
                else:
                    st.session_state["result"] = {
                        "data": resp.json(),
                        "text": uploaded.getvalue().decode("utf-8", errors="replace"),
                        "name": uploaded.name,
                    }

    # Render from session_state so the results (and downloads) survive the rerun a
    # download button triggers — otherwise the whole extraction would disappear.
    result = st.session_state.get("result")
    if result:
        data, text, name = result["data"], result["text"], result["name"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Entities found", data["num_entities"])
        c2.metric("Latency", f"{data['latency_ms']} ms")
        c3.metric("Classes", len(data["entities_by_class"]))

        # --- results table + downloads FIRST (before the document) ---
        st.markdown("##### Results")
        table = pd.DataFrame(
            [{"Class": cls, "Entities": ", ".join(vals)} for cls, vals in data["entities_by_class"].items()]
        )
        st.table(table)

        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button(
            "Download CSV", table.to_csv(index=False).encode("utf-8"),
            file_name=f"{Path(name).stem}_entities.csv", mime="text/csv",
        )
        d2.download_button(
            "Download JSON", json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"),
            file_name=f"{Path(name).stem}_entities.json", mime="application/json",
        )

        # --- highlighted document AFTER ---
        st.markdown("##### Highlighted text")
        present = {e["label"] for e in data["entities"]}
        if present:
            st.markdown(legend(present), unsafe_allow_html=True)
        st.markdown(
            f'<div style="line-height:1.9;border:1px solid #E3E7EE;border-radius:8px;'
            f'padding:14px;background:#FFFFFF;">{render_highlight(text, data["entities"])}</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------- Comparison
with tab_compare:
    st.subheader("Model comparison — DNRTI benchmark")
    st.caption("Evaluated on 662 DNRTI test sentences (full test split, seed 42). Chosen model: SecureBERT-NER.")

    
    st.markdown("##### Overall metrics")
    st.markdown(
        """
| Model | Precision | Recall | F1 (micro) | F1 (macro) | Params | Latency |
|---|---|---|---|---|---|---|
| **SecureBERT-NER** | **0.703** | **0.696** | **0.700** | **0.692** | 124M | 122 ms |
| CyNER-base | 0.380 | 0.204 | 0.265 | 0.224 | 277M | 135 ms |
| SecureBERT2.0-NER | 0.124 | 0.170 | 0.144 | 0.090 | 150M | 157 ms |

<span style="color:#6b7280;font-size:0.85rem;">Micro-F1 weights frequent classes; macro-F1 treats every class equally.</span>
""",
        unsafe_allow_html=True,
    )

    st.markdown("##### Per-class F1")
    per_class_f1 = {
        "SecureBERT-NER":    {"Organization": 0.754, "System": 0.477, "Vulnerability": 0.576,
                              "Malware": 0.654, "Indicator": 0.784, "Time": 0.801, "Area": 0.799},
        "CyNER-base":        {"Organization": 0.330, "System": 0.015, "Vulnerability": 0.582,
                              "Malware": 0.311, "Indicator": 0.327, "Time": 0.0, "Area": 0.0},
        "SecureBERT2.0-NER": {"Organization": 0.242, "System": 0.003, "Vulnerability": 0.065,
                              "Malware": 0.203, "Indicator": 0.119, "Time": 0.0, "Area": 0.0},
    }
    st.bar_chart(pd.DataFrame(per_class_f1).reindex(COMMON_CLASSES))

    st.markdown("##### Decision")
    st.markdown(
        "**Our pick: SecureBERT-NER.** For our product it's the clear choice — it correctly extracts more than "
        "**twice as many entities** as the next-best model, responds the **fastest**, and is the **lightest** to run. "
        "It's also the only model that captures **when** and **where** events happen, giving analysts the complete "
        "picture of an incident. The result: the most reliable extraction, the quickest turnaround, and simple "
        "deployment on your own infrastructure."
    )

    with st.expander("Class mapping across taxonomies"):
        st.markdown(
            """
| CyNER | DNRTI | SecureBERT-NER |
|---|---|---|
| Organization | HackOrg | APT |
| Organization | SecTeam | SECTEAM |
| Organization | Idus, Org | IDTY |
| System | OffAct, Way | ACT, OS, TOOL |
| Vulnerability | Exp | VULID, VULNAME |
| Malware | Tool | MAL |
| Indicator | SamFile | FILE |
| Indicator | — | DOM, ENCR, IP, URL, MD5, PROT, EMAIL, SHA1, SHA2 |
| — | Time | TIME |
| — | Area | LOC |
| — | Purp, Features | — |
"""
        )


# --------------------------------------------------------------------------- History
with tab_history:
    st.subheader("Recent requests")
    st.caption("Metadata only — the uploaded text is never stored.")
    try:
        rows = requests.get(f"{API_URL}/history", params={"limit": 20}, timeout=5).json()
        if rows:
            hist = pd.DataFrame(rows)
            hist["timestamp"] = pd.to_datetime(hist["timestamp"]).dt.strftime("%b %d, %H:%M")
            hist = hist[["timestamp", "filename", "latency_ms", "num_entities", "status"]]
            st.dataframe(hist, use_container_width=True, hide_index=True)
        else:
            st.info("No requests logged yet — analyze a file to populate history.")
    except requests.RequestException:
        st.error("Could not load history (API unreachable).")
