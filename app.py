
import streamlit as st
from pipeline_service import process_document_command

st.set_page_config(
    page_title="DraftMate AI | Document Intelligence",
    page_icon="📄",
    layout="wide"
)

st.title("📄 DraftMate AI")
st.subheader("Document Intelligence, Clause Retrieval & Voice Commands")
st.caption("Member 4 — Document Intelligence, Voice & Context")

st.info(
    "Upload a DOCX or PDF, enter a command, and inspect "
    "the retrieved context and AI-generated response."
)

uploaded_file = st.file_uploader(
    "Upload your legal document",
    type=["pdf", "docx"]
)

command = st.text_input(
    "Enter a voice command",
    placeholder="e.g. Explain clause 1.1"
)

st.caption(
    "Try: Explain clause 1.1 | Rewrite clause 1.1 in simpler language "
    "| Summarise this agreement"
)

if st.button("Process Document", type="primary"):
    if uploaded_file is None:
        st.warning("Please upload a PDF or DOCX document.")

    elif not command.strip():
        st.warning("Please enter a command.")

    else:
        try:
            with st.spinner("Extracting context and generating AI response..."):
                result = process_document_command(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    command
                )

            context = result["context"]

            if not context.get("found", False):
                st.warning(
                    context.get(
                        "message",
                        "The requested clause or context was not found."
                    )
                )

            else:
                st.success("Document processed successfully!")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Detected action", result["action"])

                with col2:
                    st.metric(
                        "Estimated context tokens",
                        result["estimated_tokens"]
                    )

                st.write("**Target clause:**", result["target_clause"])

                st.markdown("### Retrieved Context")

                if context.get("section_heading"):
                    st.write(context["section_heading"])

                if context.get("section_context"):
                    st.write(context["section_context"])

                if context.get("heading"):
                    st.write(context["heading"])

                st.text_area(
                    "Relevant document text",
                    value=context.get("text", ""),
                    height=220
                )

                if result.get("ai_response"):
                    st.markdown("### 🤖 DraftMate AI Response")
                    st.markdown(result["ai_response"])
                else:
                    st.info(
                        "No AI response was generated for this command."
                    )

        except Exception as error:
            st.error(f"Processing failed: {error}")
            st.caption(
                "Check the API key, internet connection, document format "
                "and terminal error message."
            )

