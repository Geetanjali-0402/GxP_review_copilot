# Required sections: (name, keywords that indicate the section exists)
REQUIRED_SECTIONS = [
    ("Purpose", ["purpose", "objective"]),
    ("Scope", ["scope"]),
    ("Responsibilities", ["responsibilit", "roles"]),
    ("Definitions", ["definition", "abbreviation", "glossary"]),
    ("Procedure", ["procedure", "process", "instructions"]),
    ("References", ["reference"]),
    ("Revision History", ["revision history",
     "change history", "version history"]),
    ("Approval", ["approval", "approved by", "signature"]),
]

# Content-level checks the LLM performs on each section: (id, description)
LLM_CHECKS = [
    ("vague_language", "Vague or non-measurable wording such as 'as appropriate', 'where necessary', 'periodically', 'timely' without defined criteria."),
    ("undefined_acronym",
     "Acronyms or technical terms used without being defined in the document."),
    ("responsibility_gap", "Actions described without a clearly assigned role or owner."),
    ("data_integrity", "ALCOA+ gaps: records without attribution, timestamps, original/legible/accurate requirements, or retention rules."),
    ("missing_reference", "References to other documents, forms or regulations that are not identified with number/version."),
    ("inconsistency", "Contradictory statements or inconsistent terminology within the section."),
]
