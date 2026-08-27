"""Shared badge prompt options without application framework dependencies."""


STYLE_DESCRIPTIONS = {
    "Professional": "Style Instructions: Use formal, business-oriented language emphasizing industry standards and career advancement. Write in a professional corporate tone. Focus on business value, organizational impact, and career development. Use formal language suitable for executive presentations and HR documentation. Badge Naming: Create formal, professional titles that emphasize credibility and career value (e.g., 'Executive Leadership Certificate', 'Strategic Business Analyst Credential', 'Professional Project Management Badge'). Use titles that would appear on a resume or LinkedIn profile.",
    "Academic": "Style Instructions: Use scholarly language emphasizing learning outcomes and academic rigor. Adopt an academic writing style with emphasis on educational objectives and pedagogical frameworks. Reference learning theories and competency standards. Use precise educational terminology. Badge Naming: Create academic honors and scholarly titles that convey intellectual achievement (e.g., 'Research Excellence Award', 'Advanced Studies in Biology', 'Scholar of Data Science', 'Academic Achievement in Literature'). Use titles common in educational institutions and academic transcripts.",
    "Industry": "Style Instructions: Use sector-specific terminology focusing on job-readiness and practical applications. Write with industry-specific language emphasizing hands-on skills and workplace readiness. Focus on practical competencies, certifications, and real-world application. Use terminology that hiring managers recognize. Badge Naming: Create job-ready certification titles that signal employability (e.g., 'Certified Full-Stack Developer', 'Professional Welder Certification', 'Licensed Phlebotomy Technician', 'Qualified Network Administrator'). Use titles that employers and recruiters actively search for.",
    "Technical": "Style Instructions: Use precise technical language with emphasis on tools and measurable outcomes. Write with technical precision using specific metrics, tools, and technologies. Emphasize quantifiable achievements and technical proficiencies. Include technical stack details where relevant. Badge Naming: Create technical achievement titles that specify technologies and competencies (e.g., 'Python Mastery Badge', 'AWS Cloud Solutions Architect', 'React.js Developer Certification', 'Machine Learning Specialist'). Include specific tools, frameworks, or technologies in the title when relevant.",
    "Creative": "Style Instructions: Use engaging language highlighting innovation and problem-solving. Write in an inspiring tone that celebrates creativity, innovation, and breakthrough thinking. Emphasize unique approaches, original solutions, and forward-thinking mindset. Use energetic and motivational language. Badge Naming: Create inspiring, imaginative titles that energize and celebrate innovation (e.g., 'Innovation Pioneer', 'Creative Problem-Solver', 'Design Thinking Champion', 'Digital Storytelling Virtuoso'). Use dynamic, memorable titles that spark enthusiasm and highlight originality.",
}

TONE_DESCRIPTIONS = {
    "Authoritative": "Confident, definitive tone with institutional credibility.",
    "Encouraging": "Motivating, supportive tone inspiring continued learning.",
    "Detailed": "Comprehensive detail with examples and specific metrics.",
    "Concise": "Short, direct guidance focusing on essential information.",
    "Engaging": "Dynamic, compelling language to capture attention.",
}

LEVEL_DESCRIPTIONS = {
    "Beginner": "Target learners with minimal prior knowledge; focus on foundations.",
    "Intermediate": "Target learners with basic familiarity; emphasize applied tasks.",
    "Advanced": "Target learners with solid foundations; emphasize complex problem solving.",
}

CRITERION_TEMPLATES = {
    "Task-Oriented": "The learner explains, determines, analyzes, evaluates, applies... (simple present tense action verbs describing what learners demonstrate). Example: The learner determines the tax treatment for items reflected in individual income tax returns. Do NOT use 'Upon completion' prefixes.",
}

SUPPORTED_LANGUAGES = {
    "ar": "Arabic",
    "zh": "Chinese",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "fi": "Finnish",
    "fr": "French",
    "de": "German",
    "he": "Hebrew",
    "hu": "Hungarian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
}
