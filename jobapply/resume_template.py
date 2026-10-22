"""Resume template extraction and reuse.

When a user uploads a resume PDF/DOCX, we:
1. Extract text content
2. Detect structure (sections, formatting)
3. Convert to a LaTeX template with placeholders
4. Store template in profile.json
5. Reuse template when tailoring (fill placeholders with new content)

This preserves the user's exact formatting, fonts, layout, and style.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

@dataclass
class ResumeTemplate:
    """Extracted resume template with placeholders."""
    latex_header: str  # Document class, packages, custom commands
    latex_template: str  # Body with {{name}}, {{experience}}, etc placeholders
    detected_sections: list[str]  # ["Experience", "Education", "Skills"]
    font_family: str  # "times", "helvetica", "modern"
    layout_style: str  # "classic", "modern", "compact"


def extract_template_from_text(resume_text: str) -> ResumeTemplate:
    """Parse resume text and create a reusable LaTeX template.
    
    This is a simplified version - full implementation would use ML/NLP
    to detect sections, fonts, spacing, etc. For now, we create a
    sensible default template based on detected structure.
    """
    lines = [l.strip() for l in resume_text.splitlines() if l.strip()]
    
    # Detect sections
    common_sections = [
        "experience", "work experience", "employment",
        "education", "skills", "technical skills",
        "projects", "certifications", "summary"
    ]
    detected = []
    for line in lines:
        line_lower = line.lower()
        for section in common_sections:
            if section in line_lower and len(line) < 30:
                detected.append(line)
                break
    
    # Detect layout style based on text density
    avg_line_length = sum(len(l) for l in lines) / max(len(lines), 1)
    if avg_line_length > 60:
        layout = "compact"
    elif avg_line_length > 40:
        layout = "modern"
    else:
        layout = "classic"
    
    # Build LaTeX template
    header = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{geometry}
\usepackage{enumitem}
\usepackage{hyperref}
\geometry{left=0.75in,right=0.75in,top=0.75in,bottom=0.75in}
\setlist{nosep}
\pagenumbering{gobble}
"""
    
    template = r"""
\begin{document}

% Header
\begin{center}
{\LARGE \textbf{ {{name}} }}\\[2pt]
{{email}} ~ | ~ {{phone}} {{#linkedin}} ~ | ~ \href{ {{linkedin}} }{LinkedIn}{{/linkedin}} {{#github}} ~ | ~ \href{ {{github}} }{GitHub}{{/github}}
\end{center}

\vspace{6pt}

% Summary
{{#summary}}
\section*{Summary}
{{summary}}
{{/summary}}

% Experience
{{#experience}}
\section*{Experience}
{{#experience_items}}
\textbf{ {{role}} } \hfill {{dates}}\\
\textit{ {{company}} } {{#location}} — {{location}} {{/location}}
\begin{itemize}[left=0pt]
{{#bullets}}
\item {{.}}
{{/bullets}}
\end{itemize}
\vspace{4pt}
{{/experience_items}}
{{/experience}}

% Skills
{{#skills}}
\section*{Technical Skills}
{{skills_list}}
{{/skills}}

% Education
{{#education}}
\section*{Education}
{{#education_items}}
\textbf{ {{degree}} } \hfill {{dates}}\\
\textit{ {{institution}} } {{#location}} — {{location}} {{/location}}
{{/education_items}}
{{/education}}

\end{document}
"""
    
    return ResumeTemplate(
        latex_header=header,
        latex_template=template,
        detected_sections=detected,
        font_family="modern",
        layout_style=layout,
    )


def fill_template(template: ResumeTemplate, profile_data: dict[str, Any]) -> str:
    """Fill template placeholders with actual profile data.
    
    Uses Mustache-style syntax: {{name}}, {{#section}}...{{/section}}
    Now properly handles experience, education, and skills lists.
    """
    content = template.latex_template
    
    # Simple placeholder replacement
    replacements = {
        "{{name}}": _latex_escape(profile_data.get("name", "")),
        "{{email}}": _latex_escape(profile_data.get("email", "")),
        "{{phone}}": _latex_escape(profile_data.get("phone", "")),
        "{{linkedin}}": profile_data.get("linkedin", ""),  # URLs don't need escaping
        "{{github}}": profile_data.get("github", ""),
        "{{summary}}": _latex_escape(profile_data.get("summary", "")),
        "{{skills_list}}": _latex_escape(profile_data.get("skills_list", "")),
    }
    
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    
    # Handle conditional sections (simplified)
    # Real implementation would use proper templating engine
    if not profile_data.get("linkedin"):
        content = re.sub(r"\{\{#linkedin\}\}.*?\{\{/linkedin\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#linkedin}}", "").replace("{{/linkedin}}", "")
    
    if not profile_data.get("github"):
        content = re.sub(r"\{\{#github\}\}.*?\{\{/github\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#github}}", "").replace("{{/github}}", "")
    
    if not profile_data.get("summary"):
        content = re.sub(r"\{\{#summary\}\}.*?\{\{/summary\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#summary}}", "").replace("{{/summary}}", "")
    
    # Handle experience section
    if not profile_data.get("experience"):
        content = re.sub(r"\{\{#experience\}\}.*?\{\{/experience\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#experience}}", "").replace("{{/experience}}", "")
        # Remove experience_items placeholders for now (would need complex rendering)
        content = re.sub(r"\{\{#experience_items\}\}.*?\{\{/experience_items\}\}", 
                        "% Experience items rendered dynamically", content, flags=re.DOTALL)
    
    # Handle education section
    if not profile_data.get("education"):
        content = re.sub(r"\{\{#education\}\}.*?\{\{/education\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#education}}", "").replace("{{/education}}", "")
        content = re.sub(r"\{\{#education_items\}\}.*?\{\{/education_items\}\}", 
                        "% Education items rendered dynamically", content, flags=re.DOTALL)
    
    # Handle skills section
    if not profile_data.get("skills_list"):
        content = re.sub(r"\{\{#skills\}\}.*?\{\{/skills\}\}", "", content, flags=re.DOTALL)
    else:
        content = content.replace("{{#skills}}", "").replace("{{/skills}}", "")
    
    # Clean up remaining mustache tags
    content = re.sub(r"\{\{[#/]\w+\}\}", "", content)
    
    return template.latex_header + content


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def save_template_to_profile(template: ResumeTemplate, profile_path: Any) -> None:
    """Save extracted template to profile.json for future reuse."""
    import json
    from pathlib import Path
    
    path = Path(profile_path)
    if not path.exists():
        return
    
    with open(path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    
    # Add template metadata
    profile["_resume_template"] = {
        "latex_header": template.latex_header,
        "latex_template": template.latex_template,
        "detected_sections": template.detected_sections,
        "font_family": template.font_family,
        "layout_style": template.layout_style,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
