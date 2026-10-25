import streamlit as st
from drafting_engine.models import DraftRequest
from drafting_engine.skill_loader import load_skills
from drafting_engine.engine import run_skill

st.set_page_config(
    page_title="DraftMate AI | Legal Drafting Studio",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- DESIGN ----------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

    .stApp {
        background: #F5F6F8;
        color: #202735;
        font-family: 'DM Sans', sans-serif;
    }

    [data-testid="stHeader"] {
        background: rgba(245,246,248,0.95);
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1600px;
    }

    .brand {
        font-family: 'Playfair Display', serif;
        font-size: 30px;
        font-weight: 700;
        color: #142B49;
        letter-spacing: -0.8px;
    }

    .brand span { color: #B58B4C; }

    .subtitle {
        color: #738096;
        font-size: 12px;
        letter-spacing: 2px;
        font-weight: 600;
        text-transform: uppercase;
    }

    .panel {
        background: #FFFFFF;
        border: 1px solid #E5E8EF;
        border-radius: 15px;
        padding: 19px;
        margin-bottom: 14px;
    }

    .panel-title {
        font-size: 17px;
        font-weight: 700;
        color: #182B46;
        margin-bottom: 4px;
    }

    .muted {
        color: #7C8799;
        font-size: 12px;
    }

    .section-label {
        color: #778399;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin: 13px 0 7px;
    }

    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextInput"] input {
        background: #FBFCFE;
        border: 1px solid #E1E6EF;
        border-radius: 9px;
        color: #202735;
        font-size: 14px;
    }

    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stTextInput"] input:focus {
        border-color: #345A83;
        box-shadow: 0 0 0 1px #345A83;
    }

    .stButton > button {
        border-radius: 9px;
        font-weight: 600;
        min-height: 42px;
    }

    .stDownloadButton > button {
        border-radius: 9px;
        font-weight: 600;
        width: 100%;
    }

    div[data-testid="stFileUploader"] {
        background: #FBFCFE;
        border: 1px dashed #C8D1DF;
        border-radius: 10px;
        padding: 8px;
    }

    hr { border-color: #E8EBF1; }

    #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- SESSION STATE ----------
defaults = {
    "draftmate_draft": "",
    "draftmate_changes": [],
    "draftmate_warnings": [],
    "draftmate_skill": "",
    "draftmate_missing": [],
    "draftmate_instruction": "Draft this document",
    "draftmate_source": "",
    "draftmate_reference": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

skills = load_skills()

if not skills:
    st.error("No drafting skills were found. Check the drafting_engine/skills folder.")
    st.stop()

# ---------- HEADER ----------
header_left, header_right = st.columns([3, 1])

with header_left:
    st.markdown(
        """
        <div class="brand">DraftMate<span>.</span> AI</div>
        <div class="subtitle">Legal Drafting Studio</div>
        """,
        unsafe_allow_html=True,
    )

with header_right:
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:right;color:#718096;font-size:12px;'>"
        "AI-ASSISTED WORKSPACE &nbsp; · &nbsp; HUMAN REVIEW</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ---------- THREE-PANEL LAYOUT ----------
left, center, right = st.columns([1.05, 2.35, 1.1], gap="medium")

# ---------- LEFT: SKILLS & INPUT DOCUMENTS ----------
with left:
    st.markdown(
        '<div class="panel-title">Workspace</div>'
        '<div class="muted">Choose a legal drafting skill</div>',
        unsafe_allow_html=True,
    )

    skill_ids = list(skills.keys())

    current_index = (
        skill_ids.index(st.session_state["draftmate_skill"])
        if st.session_state["draftmate_skill"] in skill_ids
        else 0
    )

    skill_id = st.selectbox(
        "Drafting skill",
        skill_ids,
        index=current_index,
        format_func=lambda s: skills[s]["name"],
        label_visibility="collapsed",
    )

    skill = skills[skill_id]

    if st.session_state["draftmate_skill"] != skill_id:
        st.session_state["draftmate_skill"] = skill_id
        st.session_state["draftmate_missing"] = []

    st.caption(skill.get("description", "Specialised legal drafting workflow."))

    st.markdown("---")
    st.markdown("**Reference documents**")
    st.caption("Upload a plain-text or Markdown document.")

    uploaded = st.file_uploader(
        "Upload reference",
        type=["txt", "md"],
        help="PDF and DOCX extraction can be connected separately.",
        label_visibility="collapsed",
    )

    uploaded_text = ""
    if uploaded is not None:
        try:
            uploaded_text = uploaded.getvalue().decode("utf-8")
            st.success(f"Loaded: {uploaded.name}")
        except UnicodeDecodeError:
            st.error("This file is not valid UTF-8 text.")

    inputs_cfg = skill.get("inputs", {})
    required = inputs_cfg.get("required", [])
    optional = inputs_cfg.get("optional", [])

    st.markdown("---")
    st.markdown("**Document context**")

    source_text = ""
    if skill.get("requires_source_text"):
        source_default = uploaded_text or st.session_state["draftmate_source"]
        source_text = st.text_area(
            "Existing document",
            value=source_default,
            height=190,
            placeholder="Paste the agreement, clause, or existing draft...",
            key=f"source_{skill_id}",
        )
    elif uploaded_text:
        st.info("File loaded. This skill does not explicitly require source text.")

    reference_text = ""
    if skill.get("use_reference_style"):
        reference_text = st.text_area(
            "Style reference",
            value=st.session_state["draftmate_reference"],
            height=130,
            placeholder="Paste a sample to guide tone and formatting...",
            key=f"reference_{skill_id}",
        )

    st.markdown(
        '<div class="muted">Uploaded content is supplied as text. '
        'No PDF or DOCX extraction is implemented in this version.</div>',
        unsafe_allow_html=True,
    )

# ---------- CENTER: DRAFTING WORKSPACE ----------
with center:
    st.markdown(
        """
        <div class="panel-title">Drafting workspace</div>
        <div class="muted">Describe the task, provide the facts, and generate your draft.</div>
        """,
        unsafe_allow_html=True,
    )

    instruction = st.text_input(
        "What would you like to do?",
        value=st.session_state["draftmate_instruction"],
        placeholder="e.g. Draft a formal notice regarding breach of agreement",
        key="draftmate_instruction_input",
    )

    with st.form(f"draft_form_{skill_id}"):
        st.markdown('<div class="section-label">Required details</div>',
                    unsafe_allow_html=True)

        inputs = {}

        for field in required:
            inputs[field] = st.text_area(
                field.replace("_", " ").title(),
                height=90,
                placeholder=f"Enter {field.replace('_', ' ')}...",
                key=f"required_{skill_id}_{field}",
            )

        if optional:
            with st.expander("Additional details (optional)"):
                for field in optional:
                    inputs[field] = st.text_input(
                        field.replace("_", " ").title(),
                        key=f"optional_{skill_id}_{field}",
                    )

        generate = st.form_submit_button(
            "✦  Generate legal draft",
            type="primary",
            use_container_width=True,
        )

    if generate:
        clean = {
            k: v.strip()
            for k, v in inputs.items()
            if isinstance(v, str) and v.strip()
        }

        req = DraftRequest(
            skill_id=skill_id,
            instruction=instruction.strip(),
            inputs=clean,
            source_text=(source_text or uploaded_text or "").strip() or None,
            reference_text=reference_text.strip() or None,
        )

        try:
            with st.spinner("Working on your document..."):
                result = run_skill(req)

            st.session_state["draftmate_instruction"] = instruction
            st.session_state["draftmate_source"] = source_text or uploaded_text
            st.session_state["draftmate_reference"] = reference_text
            st.session_state["draftmate_missing"] = result.missing_inputs or []
            st.session_state["draftmate_warnings"] = result.warnings or []
            st.session_state["draftmate_changes"] = result.changes or []
            st.session_state["draftmate_skill"] = skill_id

            if result.draft_md:
                st.session_state["draftmate_draft"] = result.draft_md

            st.session_state["draftmate_last_run"] = True

        except Exception as exc:
            st.error(f"Draft generation failed: {exc}")

    st.markdown("---")

    st.markdown(
        '<div class="panel-title">Document editor</div>'
        '<div class="muted">Review and edit the generated text before exporting.</div>',
        unsafe_allow_html=True,
    )

    if st.session_state["draftmate_missing"]:
        st.error(
            "Missing required inputs: "
            + ", ".join(st.session_state["draftmate_missing"])
        )

    if st.session_state["draftmate_draft"]:
        draft = st.text_area(
            "Draft content",
            value=st.session_state["draftmate_draft"],
            height=430,
            key="draftmate_editor",
            label_visibility="collapsed",
        )

        st.session_state["draftmate_draft"] = draft

        is_dry_run = draft.startswith("[DRY RUN")

        if is_dry_run:
            st.warning(
                "The engine returned a dry-run response, not a real AI-generated draft. "
                "Check your model configuration."
            )

        download_left, download_right = st.columns(2)

        with download_left:
            st.download_button(
                "↓  Download Markdown",
                data=draft,
                file_name="draftmate_document.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with download_right:
            if st.button("Clear draft", use_container_width=True):
                st.session_state["draftmate_draft"] = ""
                st.session_state["draftmate_changes"] = []
                st.session_state["draftmate_warnings"] = []
                st.rerun()

    else:
        st.info(
            "Your document will appear here. Choose a skill, fill in the required "
            "details, and click Generate legal draft."
        )

# ---------- RIGHT: REVIEW & QUALITY ----------
with right:
    st.markdown(
        '<div class="panel-title">Review & quality</div>'
        '<div class="muted">Check the output before using it.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("**Citation verification**")

    st.info(
        "Citation verification is handled by a separate module. "
        "No live verification result is connected to this panel yet."
    )

    st.markdown("---")
    st.markdown("**Warnings**")

    warnings = st.session_state["draftmate_warnings"]

    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.caption("No engine warnings to display.")

    st.markdown("---")
    st.markdown("**Changes made**")

    changes = st.session_state["draftmate_changes"]

    if changes:
        for change in changes:
            st.write("• " + change.description)
    else:
        st.caption("Change summaries will appear here when provided by the engine.")

    st.markdown("---")
    st.markdown("**Before you use this draft**")
    st.caption(
        "Review names, dates, facts, legal provisions, jurisdiction, and all "
        "citations. AI-generated text requires human legal review."
    )

st.markdown("---")
st.caption(
    "DraftMate AI · Hackathon prototype · Generated documents are drafts, "
    "not a substitute for professional legal judgment."
)