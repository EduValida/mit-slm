from typing import Dict, Mapping, Optional


def _description(
    values: Mapping[str, str],
    selected: str,
    parameter_name: str,
) -> str:
    """Resolve a configured prompt option with an actionable error."""
    try:
        return values[selected]
    except KeyError as exc:
        available = ", ".join(sorted(values))
        raise ValueError(
            f"Unknown {parameter_name} '{selected}'. Available values: {available}"
        ) from exc


def build_badge_prompt(
    *,
    course_input: str,
    language: str,
    badge_params: Dict[str, str],
    style_descriptions: Mapping[str, str],
    tone_descriptions: Mapping[str, str],
    level_descriptions: Mapping[str, str],
    criterion_templates: Mapping[str, str],
    badge_style: Optional[str] = None,
    institution: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> str:
    """Build the user prompt shared by production and model evaluations."""
    user_content = f"""[LANGUAGE: {language}]

Course Content: {course_input}

Parameters:
- Style: {_description(style_descriptions, badge_params['badge_style'], 'badge style')}
- Tone: {_description(tone_descriptions, badge_params['badge_tone'], 'badge tone')}  
- Level: {_description(level_descriptions, badge_params['badge_level'], 'badge level')}
- Criterion Style: {_description(criterion_templates, badge_params['criterion_style'], 'criterion style')}"""

    if badge_style:
        user_content += (
            f"\n- Badge Style: {badge_style} , incorporate prominently in both "
            "badge name and badge description"
        )

    if institution:
        user_content += (
            f"\n- Institution: {institution} , incorporate prominently in both "
            "badge name and badge description for branding"
        )

    if custom_instructions:
        user_content += f"\n- Special Instructions: {custom_instructions}"

    user_content += (
        f"\n\nCRITICAL: ALL badge text values MUST be written in {language}, "
        "even if the course content above is in a different language."
    )
    user_content += (
        "\n\nRespond with ONLY a JSON object. Start your response with `{` — "
        "no intro text, no explanation, no markdown fences."
    )
    user_content += (
        '\nSchema: {"badge_name": "...", "badge_description": "...", '
        '"criteria": {"narrative": "..."}}'
    )
    return user_content
