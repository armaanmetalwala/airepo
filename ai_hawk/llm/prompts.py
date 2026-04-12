# Prompt templates for GPTAnswerer (langchain ChatPromptTemplate).
# Variables must match src.utils.constants and GPTAnswerer.invoke() keys.

summarize_prompt_template = """Summarize the following job description in 5-8 bullet points for quick review.
Focus on role, stack, seniority, location/remote, and must-have requirements.

Job description:
{text}

Summary:"""

determine_section_template = """You classify a job application form question into ONE profile section.

Question: {question}

Reply with exactly one line containing ONLY the section name from this list (match spelling and capitalization):
Personal information | Self Identification | Legal Authorization | Work Preferences | Education Details | Experience Details | Projects | Availability | Salary Expectations | Certifications | Languages | Interests | Cover letter

Section:"""

personal_information_template = """You are helping a candidate answer a job application question truthfully using their profile.

Profile section (personal information):
{resume_section}

Question: {question}

Answer concisely in plain text only (no markdown). If unknown, say "Not specified"."""

self_identification_template = """You are helping a candidate answer a job application question truthfully.

Profile section (self identification):
{resume_section}

Question: {question}

Answer concisely in plain text only. Use the exact wording expected by typical ATS forms when possible."""

legal_authorization_template = """You are helping a candidate answer a job application question truthfully.

Profile section (legal authorization):
{resume_section}

Question: {question}

Answer concisely (Yes/No or short phrase) as appropriate."""

work_preferences_template = """You are helping a candidate answer a job application question truthfully.

Profile section (work preferences):
{resume_section}

Question: {question}

Answer concisely in plain text only."""

education_details_template = """You are helping a candidate answer a job application question using their education history.

Education details:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

experience_details_template = """You are helping a candidate answer a job application question using their work experience.

Experience details:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

projects_template = """You are helping a candidate answer a job application question using their projects.

Projects:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

availability_template = """You are helping a candidate answer a job application question.

Availability:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

salary_expectations_template = """You are helping a candidate answer a job application question.

Salary expectations:
{resume_section}

Question: {question}

Answer with a realistic range or numeric value as the form likely expects."""

certifications_template = """You are helping a candidate answer a job application question.

Certifications:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

languages_template = """You are helping a candidate answer a job application question.

Languages:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

interests_template = """You are helping a candidate answer a job application question.

Interests:
{resume_section}

Question: {question}

Answer concisely in plain text only."""

coverletter_template = """Write a short professional cover letter paragraph (120-200 words) for this application.

Candidate resume (JSON):
{resume}

Job description:
{job_description}

Company: {company}

Cover letter:"""

numeric_question_template = """Infer a single numeric answer for the application question using the candidate history.

Education: {resume_educations}
Experience: {resume_jobs}
Projects: {resume_projects}

Question: {question}

Reply with one number only (years, count, etc.). If unclear, reply with your best estimate as a single integer."""

options_template = """Pick the single best option for this application question from the list. Reply with ONLY one option string exactly as listed.

Candidate resume (JSON):
{resume}

Application profile (JSON):
{job_application_profile}

Question: {question}

Options: {options}

Best option:"""

resume_or_cover_letter_template = """Does this phrase refer to uploading or attaching a resume/CV or a cover letter?

Phrase: {phrase}

Reply with exactly one word: resume or cover"""

is_relavant_position_template = """Rate job fit for this candidate on a scale 1-10.

Candidate resume (JSON):
{resume}

Job description:
{job_description}

Reply in exactly this format:
Score: <integer 1-10>
Reasoning: <one short paragraph>"""
