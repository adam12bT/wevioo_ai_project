"""
Prompt Depot (packaged)
-------------
Single source of truth for every LLM-facing prompt used across the agent
pipeline. Every agent that needs to call an LLM imports its prompt(s) from
here instead of defining its own inline string.
"""

# Extraction Agent
EXTRACTION_PROMPT = """Two separately labelled sources are provided above: tender excerpts and \
response-template excerpts. Extract tender facts ONLY from the tender excerpts and template rules \
ONLY from the response-template excerpts. If those excerpts explicitly say that no template was \
uploaded, return an empty response_template object; the application supplies the fallback. \
Respond with ONLY a valid JSON object (no markdown fences, no extra text):

{
  "scope_summary": "2-3 sentence summary of what work is being requested",
  "deliverables": ["list", "of", "expected", "deliverables"],
  "technical_constraints": ["technologies, integrations, security, hosting, standards, or performance constraints"],
  "contractual_constraints": ["eligibility, legal, commercial, warranty, SLA, or contractual obligations"],
  "mandatory_requirements": ["requirements explicitly described as mandatory, required, shall, or must"],
  "domain_specific_constraints": ["requirements unique to the tender's actual sector or subject"],
  "required_evidence": ["documents, credentials, references, samples, or proof the bidder must submit"],
  "required_forms": ["named forms, schedules, declarations, tables, or annexes to complete"],
  "additional_requirements": ["important requirements that do not fit the other categories"],
  "deadlines": {"submission_deadline": "date if stated, else null", "project_duration": "if stated, else null"},
  "budget": "budget or price range if stated, else null",
  "evaluation_criteria": ["list of how proposals will be scored"],
  "selection_method": "e.g. QCBS, QBS, LCS, if stated, else null",
  "response_template": {
    "required_sections": ["exact section titles required by the response template"],
    "section_order": ["exact section titles in their required order"],
    "instructions": ["content instructions attached to individual sections"],
    "formatting_requirements": ["page limits, fonts, tables, annexes, language, or other formatting rules"]
  }
}

If a field cannot be found in the document, use null or an empty list — do not guess."""


# Research Agent
RESEARCH_SCOPE_PROMPT = """Based ONLY on the tender document provided, answer in ONE short \
sentence (max ~40 words, no markdown, no preamble): what specific product, service, \
or work is being procured, in what sector/domain, and what are the 1-2 most technically \
or regulatorily distinctive requirements (e.g. a specific integration, an offline/mobile \
requirement, a named compliance regime)? Be concrete rather than generic — prefer \
"a national health-exchange API integration" over "system integration"."""

RESEARCH_BUDGET_PROMPT = """Based ONLY on the tender document provided, state the total \
budget or price ceiling if one is mentioned (include currency and amount only, \
e.g. "USD 380,000"). If no budget or price range is stated anywhere in the \
document, respond with exactly: none stated"""

RESEARCH_FALLBACK_SCOPE = "the scope of this tender"
RESEARCH_FALLBACK_BUDGET = "none stated"

RESEARCH_QUERY_BASE = (
    "market landscape and competing firms/consultants for a project involving: {scope}."
)
RESEARCH_QUERY_BUDGET_CLAUSE = (
    " The project budget is approximately {budget} — prioritize firms and "
    "consultancies realistically sized to compete for a contract at this budget "
    "level, not large enterprise vendors whose typical engagements are far larger."
)
RESEARCH_QUERY_SELECTION_METHOD_CLAUSE = " Procurement is via {selection_method}."
RESEARCH_QUERY_GUARDRAILS = (
    " Identify likely competitors and their typical positioning. For the 'recent "
    "similar awarded projects' section: only name a specific project, client, or "
    "contract if you can point to a real, findable source confirming it (a news "
    "article, press release, or procurement notice with a date) — do not infer or "
    "guess a plausible-sounding award from a firm's homepage or service description. "
    "If no verifiable recent award can be found for a given firm, say so explicitly "
    "rather than describing a generic, undated project. In the references/sources "
    "list, include ONLY sources that are actually cited inline in the report body — "
    "do not list every page visited during research if it wasn't used as a citation."
)


# Generation Agent
GENERATION_PROMPT_TEMPLATE = """You are a senior bid writer producing batch {batch_number} of \
{batch_count} for a formal proposal in response to the tender document below. Generate \
ONLY the complete sections assigned to this batch. This is a formal deliverable that \
will be submitted to the client for evaluation, not a conversational answer or cover letter. \
Each section below must be written in complete, substantive paragraphs with real analysis and \
detail grounded in the material provided. Shallow, generic filler is worse than a shorter section \
that is actually specific to this tender.

RELEVANT TENDER DOCUMENT EXCERPTS:
{tender_excerpts}

CLIENT RESPONSE TEMPLATE EXCERPTS:
{response_template_excerpts}

EXTRACTED RESPONSE TEMPLATE RULES:
{response_template_rules}

REVISION FEEDBACK FROM THE PREVIOUS QUALITY REVIEW:
{revision_feedback}

EXTRACTED REQUIREMENTS:
{requirements}

MARKET / COMPETITOR RESEARCH:
{research_summary}

RELEVANT PAST PROJECT REFERENCES (company evidence; use wherever the selected structure asks for experience, references, qualifications, or track record):
{project_references}

RELEVANT CONSULTANT CVs (company evidence; use these and only these wherever the selected structure asks for personnel, roles, credentials, or experience):
{cv_excerpts}

RELEVANT PAST PROPOSALS (for tone/structure reference only — do not copy text verbatim, \
just match the general style and level of detail):
{past_proposals}

MANDATORY PROPOSAL STRUCTURE:
{proposal_structure}

Write a complete, substantive Markdown section beneath every heading above. Reproduce each \
heading exactly, including any numbering, accents, and wording supplied by the client. Do not \
replace headings from the selected structure, omit sections, merge sections, or add an \
alternative top-level outline. Map every extracted requirement and available evidence into the \
most appropriate selected section without assuming that this tender belongs to a specific domain.

This request contains only the section or sections assigned to the current batch. Emit exactly one \
level-two (`##`) heading for each assigned section and no other level-one or level-two headings. \
Never continue with the next template heading, never return an outline, and never return a heading \
without substantive body text. Level-three (`###`) subsections are allowed inside the assigned section.

Follow the target word range printed beneath each assigned heading. Use the range to produce substantive analysis, concrete activities, outputs, acceptance criteria, dependencies, controls, and traceability where they are relevant to that section. Tables count toward the target. Never pad a section with unsupported claims or repetitive filler merely to reach its target. Emit every exact Markdown heading assigned to this batch.

The upper end of each target word range is a hard maximum. Finish the current section cleanly before reaching it; do not continue expanding the answer after all required points are covered.

For bidder-specific content, use only the supplied company knowledge. Tender requirements describe \
what the bidder must provide; they are not evidence that the bidder already has that experience, \
certification, staff member, project, product, or capability. Never write that internal records, \
confidential projects, a consortium, named personnel, certifications, or past performance exist \
unless that exact evidence appears in the company-knowledge excerpts. If the selected section \
requires unsupported bidder information, omit the unsupported sentence. Add one concise level-three \
"Evidence gaps" subsection at the end of that section, using a single Markdown table that identifies \
the exact missing evidence and the user action required. Never use a generic row such as "Company \
evidence" when CVs, references, or past proposals were supplied. Name the specific absent role, \
credential, project type, price, or attachment. Put a company-evidence gap only in the section whose \
purpose is personnel, qualifications, references, commercial evidence, or annexes, and do not repeat \
the same gap in later sections. Do not scatter placeholders through the prose.

Use every relevant named CV and project reference supplied above when the template has an appropriate \
team, qualifications, references, delivery, security, migration, or governance section. Do not let the \
closest architect CV or first project stand in for the full evidence set. Compare tender-required roles \
against the supplied CVs and report only the specific roles that remain uncovered. Use the past proposal \
to influence compatible subsection sequencing, traceability-table design, and evidence presentation, \
but never import its client facts, personnel, prices, or commitments into this tender response.

Use a person's actual name and role from the CV body. Never present a retrieval chunk ID, opaque source \
identifier, filename hash, or label such as "CV 1243" as a consultant's identity. Treat multiple chunks \
from one source document as one CV/reference. If a tender-required role has no matching named CV, add \
one specific gap row for that role in the personnel/qualifications section; do not invent a candidate and \
do not repeat that gap elsewhere. Describe annexes as planned or unavailable unless their exact artefacts \
are present in the supplied company evidence.

In qualifications and reference tables, populate rows only with actual named people and projects from the \
company evidence. Never output an empty evidence table, a generic assertion that unnamed individuals have \
worked on comparable programmes, or a statement that all role-specific CVs are absent when named matching \
CVs were supplied. Evidence from a project supports that project; it does not prove that unidentified team \
members participated in it.

If the company-evidence fields say that nothing was found, treat that as zero evidence, not as \
permission to infer capability from the proposed methodology. In that case, never claim that the \
bidder possesses core competencies, a proven framework, certified processes, senior or certified \
staff, standards adherence, prior delivery, relevant qualifications, or demonstrated capability. \
For a qualifications/evidence section, state plainly which evidence is unavailable in that single \
evidence-gap table and describe only what evidence must be supplied before submission. An \
execution plan shows intent; it does not prove the bidder's experience or capability.

Do not describe the bidder as a consortium, partnership, joint venture, multi-company team, or \
group unless the supplied company-knowledge excerpts explicitly establish that organisational \
structure. Evidence for one consultant or one project supports only that person or project; never \
generalise it into broader company or consortium experience.

Maintain identical numeric commitments everywhere in the proposal. For RTO, RPO, availability, \
retention, response times, performance targets, migration accuracy, schedules, quantities, warranty \
periods, staffing quantities, payment percentages, and delivery phases, use only a value explicitly \
present in the tender evidence. If no value is provided, omit the numeric commitment and record the \
missing value once in the section's Evidence gaps table. A planned or \
scheduled test must be described as a future activity, never as completed evidence.

Never mark an annex, attachment, certificate, CV, test report, scan, penetration test, demonstration, \
or other evidence as included, completed, passed, or available unless that exact artefact appears in \
the supplied company knowledge. Never invent a financial amount, cost allocation, discount, budget \
margin, or tax calculation. When pricing evidence is absent, preserve only the requested financial \
structure and record the missing pricing evidence once in the section's Evidence gaps table. Never \
say an annex, CV, reference, certificate, or attachment is included or will be supplied when unavailable.

When describing a future test or acceptance gate, label it explicitly as "planned", "target", or \
"acceptance criterion". For example, write "acceptance target: zero unresolved critical findings", \
not "the penetration test has zero critical findings". Do not invent test coverage percentages, \
sample counts, audit results, or certifications.

Follow the language required by the selected template. If it gives no language rule, use the predominant language of the tender excerpts.

Do not invent specific figures, dates, project names, consultant names, vendors, identity \
providers, cloud providers, certificate authorities, datacenter locations, exchange rates, or \
currency conversions that are not present in the supplied material. Do not turn a tender \
requirement into a claim that the bidder already implements it: describe it as a proposed or \
committed future control. Put unknown information only in the section's single Evidence gaps table \
without attaching a guessed example (do not write "provider X", an assumed city, or an \
illustrative product name). Write in a professional, confident register \
appropriate for a formal procurement submission."""


# Quality Agent: groundedness and coherence evaluator
QUALITY_GROUNDING_PROMPT_TEMPLATE = """You are an evidence-grounding reviewer for a formal \
technical proposal. Compare the proposal against the exact evidence that was supplied to its \
writer. Do not use outside knowledge. Distinguish factual claims (dates, budgets, requirements, \
credentials, named people/projects, competitor facts) from clearly labelled recommendations, \
plans, assumptions, and placeholders.

EVIDENCE AVAILABLE TO THE WRITER:
{evidence}

EVIDENCE PROVENANCE RULES:
- company_knowledge.cv_excerpts is valid evidence for named staff, roles, skills,
  certifications, and experience when the excerpt explicitly states the fact.
- company_knowledge.project_references is valid evidence for the bidder's past
  projects and capabilities when the excerpt explicitly states the fact.
- company_knowledge.past_proposals is primarily style/structure context; treat
  it as factual company evidence only when it explicitly contains the claim.
- market_research is external context only. Never use it as proof of the
  bidding company's staff, experience, projects, clients, or certifications.
- Tender requirements are evidence of what the buyer requests, never proof
  that the bidder already owns a certification, employs a qualified person,
  delivered a past project, or has an existing capability.
- Phrases such as "our internal records confirm", "confidential reference",
  or "the consortium has" are unsupported unless the supplied company
  excerpts explicitly contain the same fact.
- A claim supported by any supplied company or tender evidence is grounded;
  do not mark it unsupported merely because it came from retrieved knowledge.

PROPOSAL TO REVIEW:
{draft}

Return ONLY valid JSON using this schema:
{{
  "groundedness_score": 0.0,
  "coherence_score": 0.0,
  "unsupported_claims": [
    {{"claim": "exact proposal wording", "reason": "why the evidence does not support it"}}
  ],
  "contradictions": [
    {{"claim": "proposal claim", "evidence": "conflicting evidence"}}
  ],
  "coherence_issues": ["internal inconsistency, impossible sequence, or requirement mismatch"],
  "notes": ["short reviewer note"]
}}

Scores must be numbers from 0 to 1. Groundedness measures whether factual claims are supported \
by the evidence. Coherence measures internal consistency and consistency with tender constraints. \
Every unsupported-claim `claim` value must quote wording that actually occurs in the proposal. \
Never replace it with a meta-description such as "the proposal lists" or invent example staff, \
projects, table rows, or quantities that are not present in the proposal. If the alleged wording \
cannot be found in the proposal, omit the finding. \
Facts copied from the tender requirements (including its duration, warranty, budget, dates, and \
constraints) are supported claims; do not demand separate proof that the bidder can comply with \
them. This includes short requirement labels in headings, bullets, and compliance tables such as \
"integration with six systems" or "migration of up to N records"; those labels describe buyer scope, \
not the bidder's historical performance. Proposed project-specific roles, governance boards, delivery offices, workflows, controls, \
tests, and artefacts written in future tense are plans and do not require evidence that the bidder \
used the same structure previously. Do not penalize \
them. A contradiction requires evidence that directly conflicts with the proposal—not merely an \
absence of capability evidence. Do not penalize future-tense delivery plans merely because they \
have not happened yet. A value explicitly labelled as a planned acceptance target, acceptance \
criterion, or future test target is a proposed gate, not a claim that testing has already passed. \
Explicit placeholders in square brackets, including TEAM PROFILES TO BE \
COMPLETED and TO BE CONFIRMED, are disclosures of missing information and must not be listed as \
unsupported factual claims, contradictions, or coherence issues. They should be reported as \
non-scoring evidence warnings for the user to resolve by uploading company documents. Do penalize invented company experience, CV details, contract facts, \
dates, amounts, certifications, and named projects. Keep each list concise and include only \
material issues."""
