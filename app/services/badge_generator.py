import random
import logging
from typing import Dict, Any, AsyncGenerator
from pydantic import ValidationError
from fastapi import HTTPException

from app.core.config import settings
from app.models.badge import BadgeValidated
from app.services.badge_prompt import build_badge_prompt
from app.services.model_output import extract_json_from_response
from app.services.ollama_client import call_model_async, call_model_stream_async
from app.services.text_processor import process_course_input

logger = logging.getLogger(__name__)

def get_badge_configuration(user_request) -> Dict[str, str]:
    """Get badge configuration parameters, applying defaults for empty values"""
    
    # Initialize badge parameters dictionary
    badge_params = {}
    
    # Handle both old BadgeRequest and new GenerateBadgeRequest formats
    if hasattr(user_request, 'badge_configuration'):
        # New format: GenerateBadgeRequest
        config = user_request.badge_configuration
        badge_style = config.badge_style
        badge_tone = config.badge_tone
        criterion_style = config.criterion_style
        badge_level = config.badge_level
    else:
        # Old format: BadgeRequest (legacy)
        badge_style = user_request.badge_style
        badge_tone = user_request.badge_tone
        criterion_style = user_request.criterion_style
        badge_level = user_request.badge_level
    
    # Badge Style - use default if not provided or empty
    if not badge_style or badge_style.strip() == "":
        badge_params['badge_style'] = random.choice(list(settings.STYLE_DESCRIPTIONS.keys()))
    else:
        badge_params['badge_style'] = badge_style
    
    # Badge Tone - use default if not provided or empty
    if not badge_tone or badge_tone.strip() == "":
        badge_params['badge_tone'] = random.choice(list(settings.TONE_DESCRIPTIONS.keys()))
    else:
        badge_params['badge_tone'] = badge_tone
    
    # Criterion Style - use default if not provided or empty
    if not criterion_style or criterion_style.strip() == "":
        badge_params['criterion_style'] = random.choice(list(settings.CRITERION_TEMPLATES.keys()))
    else:
        badge_params['criterion_style'] = criterion_style
    
    # Badge Level - use default if not provided or empty
    if not badge_level or badge_level.strip() == "":
        badge_params['badge_level'] = random.choice(list(settings.LEVEL_DESCRIPTIONS.keys()))
    else:
        badge_params['badge_level'] = badge_level
    
    return badge_params

def apply_regeneration_overrides(current_params: Dict[str, str], regeneration_request: Dict[str, str]) -> Dict[str, str]:
    """Override specific parameters for regeneration"""
    updated_params = current_params.copy()
    
    # Override with new selections for specified parameters
    if "badge_style" in regeneration_request:
        updated_params['badge_style'] = random.choice(list(settings.STYLE_DESCRIPTIONS.keys()))
    
    if "badge_tone" in regeneration_request:
        updated_params['badge_tone'] = random.choice(list(settings.TONE_DESCRIPTIONS.keys()))
    
    if "criterion_style" in regeneration_request:
        updated_params['criterion_style'] = random.choice(list(settings.CRITERION_TEMPLATES.keys()))
    
    if "badge_level" in regeneration_request:
        updated_params['badge_level'] = random.choice(list(settings.LEVEL_DESCRIPTIONS.keys()))
    
    return updated_params

def _resolve_language(request) -> str:
    """Return the full language name for the request, defaulting to English."""
    if hasattr(request, 'badge_configuration'):
        lang_code = request.badge_configuration.language or "en"
    elif hasattr(request, 'content'):
        lang_code = request.content.language or "en"
    else:
        lang_code = "en"
    return settings.SUPPORTED_LANGUAGES.get(lang_code.lower(), "English")


async def generate_badge_metadata_async(request) -> dict:
    """Generate badge metadata using the shared application system prompt."""

    badge_params = get_badge_configuration(request)
    processed_course_input = process_course_input(request.course_input)
    language = _resolve_language(request)

    # Handle both old and new request formats
    if hasattr(request, 'badge_configuration'):
        # New format: GenerateBadgeRequest
        config = request.badge_configuration
        badge_style = config.badge_style
        institution = config.institution if config.institution else None
        custom_instructions = config.custom_instructions if config.custom_instructions else None
    else:
        # Old format: BadgeRequest (legacy)
        badge_style = request.badge_style
        institution = request.institution
        custom_instructions = request.custom_instructions

    # The shared system prompt supplies the common generation instructions.
    prompt = build_badge_prompt(
        course_input=processed_course_input,
        language=language,
        badge_params=badge_params,
        style_descriptions=settings.STYLE_DESCRIPTIONS,
        tone_descriptions=settings.TONE_DESCRIPTIONS,
        level_descriptions=settings.LEVEL_DESCRIPTIONS,
        criterion_templates=settings.CRITERION_TEMPLATES,
        badge_style=badge_style,
        institution=institution,
        custom_instructions=custom_instructions,
    )
    
    response, metrics = await call_model_async(prompt)
    result = extract_json_from_response(response)
    
    # Add metrics to result
    result['metrics'] = metrics
    result["raw_model_output"] = response
    result["selected_parameters"] = badge_params
    result["processed_course_input"] = processed_course_input
    
    return result


async def optimize_badge_text(badge_data: dict, language: str = "English"):
    """Optimize badge text for image overlay with strict word limits"""
    prompt = f"""[LANGUAGE: {language}]

Badge: "{badge_data['badge_name']}"
Description: "{badge_data['badge_description']}"

Generate optimized overlay text WITH STRICT WORD LIMITS in {language}:

CRITICAL REQUIREMENTS:
- short_title: MAXIMUM 2 WORDS in {language}
- achievement_phrase: MAXIMUM 3 WORDS in {language}

Guidelines:
- Use concise, impactful phrases
- Avoid articles (the, a, an, and equivalents in {language}) to save words
- Use powerful action words
- Make every word count
- Output MUST be in {language}

Return JSON:
{{
    "short_title": "",
    "achievement_phrase": ""
}}"""

    response, metrics = await call_model_async(prompt)
    result = extract_json_from_response(response)
    result['metrics'] = metrics
    return result

async def generate_badge_metadata_stream_async(request) -> AsyncGenerator[Dict[str, Any], None]:
    """Generate badge metadata with streaming response using new format"""

    # Process course input
    processed_input = process_course_input(request.course_input)

    # Get badge configuration parameters
    badge_params = get_badge_configuration(request)
    language = _resolve_language(request)

    # Handle both old and new request formats
    if hasattr(request, 'badge_configuration'):
        # New format: GenerateBadgeRequest
        config = request.badge_configuration
        institution = config.institution if config.institution else None
        custom_instructions = config.custom_instructions if config.custom_instructions else None
    else:
        # Old format: BadgeRequest (legacy)
        institution = request.institution
        custom_instructions = request.custom_instructions

    # Build the prompt
    prompt = f"""[LANGUAGE: {language}]

Generate Open Badges 3.0 compliant metadata from course content.

COURSE CONTENT:
{processed_input}

BADGE STYLE: {badge_params['badge_style']} - {settings.STYLE_DESCRIPTIONS[badge_params['badge_style']]}
BADGE TONE: {badge_params['badge_tone']} - {settings.TONE_DESCRIPTIONS[badge_params['badge_tone']]}
BADGE LEVEL: {badge_params['badge_level']} - {settings.LEVEL_DESCRIPTIONS[badge_params['badge_level']]}
CRITERION STYLE: {badge_params['criterion_style']} - {settings.CRITERION_TEMPLATES[badge_params['criterion_style']]}

INSTITUTION: {institution or "Not specified"}
CUSTOM INSTRUCTIONS: {custom_instructions or "None"}

CRITICAL: ALL badge text fields MUST be written in {language} — this overrides the language of the course content above.

OUTPUT FORMAT: Return ONLY valid JSON in this exact format:
{{
    "badge_name": "string",
    "badge_description": "string", 
    "criteria": {{
        "narrative": "string"
    }},
    "raw_model_output": "string"
}}

Generate badge metadata now:"""

    # Stream the response using the new ollama service
    from app.services.ollama_client import ollama_client
    
    accumulated_text = ""
    async for chunk in ollama_client.generate_stream(
        content=prompt,
        temperature=settings.MODEL_CONFIG.get("temperature", 0.15),
        max_tokens=settings.MODEL_CONFIG.get("num_predict", 400),
        top_p=settings.MODEL_CONFIG.get("top_p", 0.8),
        top_k=settings.MODEL_CONFIG.get("top_k", 30),
        repeat_penalty=settings.MODEL_CONFIG.get("repeat_penalty", 1.05)
    ):
        if chunk.get("type") == "token":
            accumulated_text += chunk.get("content", "")
            yield chunk
        elif chunk.get("type") == "final":
            # Process the final response
            raw_response = chunk.get("content", "")
            
            # Try to extract JSON from the response
            try:
                badge_json = extract_json_from_response(raw_response)
                badge_json["selected_parameters"] = badge_params
                badge_json["processed_course_input"] = processed_input
                
                # Return the parsed JSON as final content
                yield {
                    "type": "final",
                    "content": badge_json,
                    "request_id": chunk.get("request_id")
                }
            except Exception as e:
                logger.warning(f"Failed to parse JSON from streaming response: {e}")
                yield {
                    "type": "error",
                    "content": f"Failed to parse JSON: {str(e)}",
                    "request_id": chunk.get("request_id")
                }
        elif chunk.get("type") == "error":
            yield chunk
