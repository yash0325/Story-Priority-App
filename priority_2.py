import streamlit as st
from jira import JIRA
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

st.set_page_config(page_title="User Story Prioritization AI", layout="wide")
st.title("🚦 User Story Prioritization AI")

PRIORITY_PROMPT = """
You are a software project manager assistant. Given a user story or task and its context, evaluate its urgency and impact to recommend a **priority** (High, Medium, Low) for the team.

Assess using:
- Business value or customer impact
- Deadlines or time sensitivity
- Dependencies on or by other work
- Risk of delay or failure
- Effort or complexity
- Alignment with strategic goals

Return:
---
**Priority Recommendation:** <High/Medium/Low>

**Rationale:**  
<1-2 lines explaining your reasoning, referencing the input factors.>
---

User Story/Task: {user_story}
Business Value/Impact: {business_value}
Deadline/Time Sensitivity: {deadline}
Dependencies: {dependencies}
Risk: {risk}
Effort/Complexity: {effort}
Other Context: {other_context}
"""

def clear_connection_state():
    for k in [
        "jira_host", "jira_email", "jira_api_token", "jira_project_key",
        "connected", "last_priority_recommendation", "last_priority_rationale",
        "last_selected_issue_key"
    ]:
        if k in st.session_state:
            del st.session_state[k]

if st.session_state.get("connected", False):
    colc, cold = st.columns([10, 1])
    with cold:
        if st.button("Disconnect"):
            clear_connection_state()
            st.rerun()

if not st.session_state.get("connected", False):
    st.subheader("Connect to Jira")
    with st.form("connection_form"):
        jira_host = st.text_input("Jira Host URL (e.g. https://yourdomain.atlassian.net)", value=st.session_state.get("jira_host", ""))
        jira_email = st.text_input("Jira Email", value=st.session_state.get("jira_email", ""))
        jira_api_token = st.text_input("Jira API Token", type="password", value=st.session_state.get("jira_api_token", ""))
        jira_project_key = st.text_input("Jira Project Key", value=st.session_state.get("jira_project_key", ""))
        submitted = st.form_submit_button("Connect")
    if submitted:
        if not (jira_host and jira_email and jira_api_token and jira_project_key):
            st.warning("Please fill in all fields to connect.")
        else:
            st.session_state["jira_host"] = jira_host.strip()
            st.session_state["jira_email"] = jira_email.strip()
            st.session_state["jira_api_token"] = jira_api_token.strip()
            st.session_state["jira_project_key"] = jira_project_key.strip()
            try:
                jira = JIRA(server=jira_host, basic_auth=(jira_email, jira_api_token))
                st.session_state["connected"] = True
                st.success(f"Connected as {jira_email} to JIRA: {jira_project_key}")
            except Exception as e:
                st.session_state["connected"] = False
                st.error(f"Failed to connect to Jira: {e}")
else:
    st.success(
        f"Connected as {st.session_state['jira_email']} to JIRA: {st.session_state['jira_project_key']}",
        icon="🔗"
    )

if st.session_state.get("connected", False):
    jira_host = st.session_state["jira_host"]
    jira_email = st.session_state["jira_email"]
    jira_api_token = st.session_state["jira_api_token"]
    jira_project_key = st.session_state["jira_project_key"]

    def get_llm():
        return ChatOpenAI(model="gpt-4o", temperature=0, api_key=st.secrets["OPENAI_API_KEY"])

    try:
        jira = JIRA(server=jira_host, basic_auth=(jira_email, jira_api_token))
        jql = f'project={jira_project_key} ORDER BY created ASC'
        issues = jira.search_issues(jql, maxResults=20)
    except Exception as e:
        st.error(f"Failed to load issues: {e}")
        issues = []

    if issues:
        issue_titles = [f"{i.key}: {i.fields.summary}" for i in issues]
        selected = st.selectbox("Select a user story/task to prioritize:", issue_titles)
        selected_issue = issues[issue_titles.index(selected)]
        story_input = f"{selected_issue.fields.summary}\n\n{selected_issue.fields.description or ''}".strip()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📝 Original Story/Task")
            st.markdown(f"**Summary:** {selected_issue.fields.summary}")
            st.markdown(f"**Description:** {selected_issue.fields.description or ''}")

        with col2:
            st.subheader("🔎 Priority Assessment")

            # Collapsible Best Practices Help Section
            with st.expander("Best practices for filling out these fields (Click to expand)", expanded=False):
                st.markdown("""
- **Business Value / Customer Impact:**  
  Describe how this task will benefit the business or customer.  
  _Example:_ “Improves sign-up conversion rates by 20%.”  
  _Tip:_ Mention business KPIs, cost savings, or risk reduction.

- **Deadline / Time Sensitivity:**  
  Specify any important dates or deadlines.  
  _Example:_ “Must be completed before July 31.”  
  _Tip:_ State urgency or flexibility.

- **Dependencies:**  
  List related tasks or teams.  
  _Example:_ “Depends on backend API being ready.”  
  _Tip:_ If none, say “None.”

- **Risk of Delay or Failure:**  
  Explain what could go wrong if delayed.  
  _Example:_ “Missing this could lead to SLA breaches.”  
  _Tip:_ If low risk, state that.

- **Effort / Complexity:**  
  Estimate work involved and note challenges.  
  _Example:_ “Simple—2 hours.” or “Complex; requires refactor.”  
  _Tip:_ If unsure, say so.
                """)

            with st.form("priority_form", clear_on_submit=True):
                business_value = st.text_area(
                    "Business Value / Customer Impact",
                    help=(
                        "Describe how this user story or task will benefit the business or customer. "
                        "Example: 'Improves sign-up conversion rates by 20%.' "
                        "Be specific—mention business KPIs, cost savings, risk reduction, or revenue potential."
                    )
                )
                deadline = st.text_input(
                    "Deadline / Time Sensitivity",
                    help=(
                        "Specify important dates or deadlines. Example: 'Must be completed before July 31.' "
                        "If not urgent, state that. If driven by compliance or an event, mention it."
                    )
                )
                dependencies = st.text_area(
                    "Dependencies (on/by other work)",
                    help=(
                        "List tasks or teams this depends on or that depend on this work. "
                        "Example: 'Depends on backend API being ready.' "
                        "If none, say 'None.'"
                    )
                )
                risk = st.text_area(
                    "Risk of delay or failure",
                    help=(
                        "Explain what could go wrong if this isn't done on time. "
                        "Example: 'Missing this could cause SLA breaches.' "
                        "If low risk, state that."
                    )
                )
                effort = st.text_input(
                    "Effort / Complexity",
                    help=(
                        "Estimate work involved (hours, days, story points) and challenges. "
                        "Example: 'Simple—2 hours.' or 'Complex; requires cross-team coordination.' "
                        "If unsure, say so."
                    )
                )
                other_context = st.text_area(
                    "Other context (optional)",
                    help="Any other relevant information to help prioritize this item."
                )
                submitted = st.form_submit_button("🟢 Assess Priority")
                if submitted:
                    with st.spinner("Evaluating priority..."):
                        chain = LLMChain(
                            llm=get_llm(),
                            prompt=PromptTemplate.from_template(PRIORITY_PROMPT)
                        )
                        try:
                            priority_output = chain.run({
                                "user_story": story_input,
                                "business_value": business_value,
                                "deadline": deadline,
                                "dependencies": dependencies,
                                "risk": risk,
                                "effort": effort,
                                "other_context": other_context,
                            })
                        except Exception as e:
                            st.error(f"OpenAI Error: {e}")
                            priority_output = ""
                        # Parse the output
                        lines = priority_output.splitlines()
                        priority = ""
                        rationale = ""
                        for idx, line in enumerate(lines):
                            if "**Priority Recommendation:**" in line:
                                priority = line.split("**Priority Recommendation:**",1)[-1].strip()
                            if "**Rationale:**" in line:
                                rationale = "\n".join(lines[idx+1:]).strip()
                        st.markdown(f"**Priority Recommendation:** `{priority}`")
                        st.markdown("**Rationale:**")
                        st.markdown(rationale)
                        # Store for update
                        st.session_state["last_priority_recommendation"] = priority
                        st.session_state["last_priority_rationale"] = rationale
                        st.session_state["last_selected_issue_key"] = selected_issue.key

            # Button to update Jira ticket priority field (if recommended)
            if (
                st.session_state.get("last_priority_recommendation")
                and st.session_state.get("last_selected_issue_key") == selected_issue.key
            ):
                if st.button("⬆️ Update Jira Issue Priority", key="update_priority_btn"):
                    # Set Jira priority
                    try:
                        # Jira priorities are usually ("Highest", "High", "Medium", "Low", "Lowest")
                        prio_map = {"High": "High", "Medium": "Medium", "Low": "Low"}
                        priority_name = prio_map.get(st.session_state["last_priority_recommendation"].capitalize(), "Medium")
                        # Find corresponding priority id (needed by Jira API)
                        all_prios = jira.priorities()
                        prio_id = None
                        for p in all_prios:
                            if p.name.lower() == priority_name.lower():
                                prio_id = p.id
                        if prio_id is None:
                            st.warning("Could not map recommended priority to Jira priority field. Please set manually in Jira.")
                        else:
                            jira.issue(selected_issue.key).update(fields={"priority": {"id": prio_id}})
                            st.success(f"Issue {selected_issue.key} updated to priority: {priority_name}")
                    except Exception as e:
                        st.error(f"Failed to update Jira issue priority: {e}")

                # Button to add rationale as a comment (optional)
                if st.button("💬 Add Rationale as Jira Comment", key="add_comment_btn"):
                    try:
                        comment = f"AI Priority Recommendation: **{st.session_state['last_priority_recommendation']}**\n\nRationale:\n{st.session_state['last_priority_rationale']}"
                        jira.add_comment(selected_issue.key, comment)
                        st.success("Comment added to Jira ticket!")
                    except Exception as e:
                        st.error(f"Failed to add comment: {e}")

    else:
        st.warning("No issues found in the selected project.")
