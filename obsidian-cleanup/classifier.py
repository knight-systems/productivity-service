"""AI-powered note classification using Claude via AWS Bedrock."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import boto3

from .config import AreaFolder, get_area_path, get_archive_path, settings
from .frontmatter import get_note_content, parse_frontmatter
from .models import Correction, NoteAction, NotePlan

logger = logging.getLogger(__name__)


# Bedrock client (lazy initialization)
_bedrock_client = None


def get_bedrock_client():
    """Get or create Bedrock runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name="us-west-2",
        )
    return _bedrock_client


def classify_with_ai(
    note_path: Path,
    existing_plan: NotePlan | None = None,
    user_feedback: str | None = None,
    learned_corrections: list[Correction] | None = None,
) -> NotePlan:
    """Classify a note using Claude AI based on its content.

    This is used as a fallback when rule-based classification
    yields low confidence (< 0.7).

    Args:
        note_path: Path to the note to classify
        existing_plan: Optional existing plan (for revisions)
        user_feedback: Natural language feedback from user
        learned_corrections: Past corrections to include as context

    Returns:
        New or revised NotePlan
    """
    filename = note_path.name

    # Get note content
    content = get_note_content(note_path, max_chars=settings.max_content_chars_for_ai)
    if not content:
        return NotePlan(
            source_path=str(note_path),
            action=NoteAction.SKIP,
            confidence=0.0,
            reasoning="Could not read note content",
            classification_source="ai",
        )

    # Parse frontmatter for additional context
    frontmatter = parse_frontmatter(note_path)

    # Build context from learned corrections
    correction_context = ""
    if learned_corrections:
        correction_examples = "\n".join(
            f"- {c.to_rule_description()}" for c in learned_corrections[:10]
        )
        correction_context = f"""
## Learned User Preferences
The user has made these corrections in the past. Use them to inform your classification:
{correction_examples}
"""

    # Build revision context
    revision_context = ""
    if existing_plan and user_feedback:
        revision_context = f"""
## Current Classification (NEEDS REVISION)
The system classified this note as:
- Action: {existing_plan.action.value}
- Area: {existing_plan.target_area or 'None'}
- Reasoning: {existing_plan.reasoning}

## User Feedback
The user said: "{user_feedback}"

Please reclassify based on this feedback.
"""

    # Build frontmatter context
    frontmatter_context = ""
    if frontmatter:
        fm_parts = []
        if frontmatter.category:
            fm_parts.append(f"Category: {frontmatter.category}")
        if frontmatter.tags:
            fm_parts.append(f"Tags: {', '.join(frontmatter.tags)}")
        if frontmatter.title:
            fm_parts.append(f"Title: {frontmatter.title}")
        if fm_parts:
            frontmatter_context = f"""
## Note Frontmatter
{chr(10).join(fm_parts)}
"""

    prompt = f"""You are an Obsidian vault organization assistant. Classify the following note and determine which Area folder it belongs in.

## Note Information
- Filename: {filename}
{frontmatter_context}
## Note Content (truncated)
{content}

## Available Area Folders
- 41 - Finance: Trading, investments, budgeting, financial documents
- 42 - Family: Family events, kids, home management
- 43 - Work: Career, job search, professional development
- 44 - Health: Medical records, fitness, mental health
- 45 - Learning: Courses, tutorials, study notes
- 46 - Projects: Personal projects, hobbies, DIY

## Available Actions
- move: Move to appropriate area folder
- archive: Old or completed content, move to archives
- skip: Leave in place (can't determine or shouldn't be moved)
{correction_context}
{revision_context}
## Instructions
Analyze the note content and determine the best classification. Consider:
1. The main topic of the note content
2. Any frontmatter tags or category
3. Keywords and themes in the content
4. Any learned user preferences above
5. User feedback if this is a revision

Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "action": "move|archive|skip",
    "area": "41 - Finance|42 - Family|43 - Work|44 - Health|45 - Learning|46 - Projects|null",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this classification was chosen"
}}
"""

    try:
        client = get_bedrock_client()

        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        result = json.loads(response["body"].read())
        response_content = result["content"][0]["text"]

        # Parse JSON response
        # Handle potential markdown code blocks
        if "```" in response_content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_content, re.DOTALL)
            if match:
                response_content = match.group(1)

        classification = json.loads(response_content)

        # Build destination path
        destination = None
        target_area = None
        raw_area = classification.get("area")

        if classification["action"] == "archive":
            destination = str(get_archive_path(filename))
        elif raw_area and raw_area != "null":
            # Validate area is one of our known areas
            if raw_area in AreaFolder.ALL:
                target_area = raw_area
                destination = str(get_area_path(target_area, filename))
            else:
                # Try to match partial area name
                for area in AreaFolder.ALL:
                    if raw_area.lower() in area.lower():
                        target_area = area
                        destination = str(get_area_path(target_area, filename))
                        break

        # Create new plan
        plan = NotePlan(
            source_path=str(note_path),
            action=NoteAction(classification["action"]),
            destination_path=destination,
            target_area=target_area,
            confidence=float(classification.get("confidence", 0.8)),
            reasoning=classification.get("reasoning", "AI classification"),
            classification_source="ai",
            user_feedback=user_feedback,
            original_plan_id=existing_plan.id if existing_plan else None,
            revision_count=(existing_plan.revision_count + 1) if existing_plan else 0,
            frontmatter_category=frontmatter.category if frontmatter else None,
            frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
        )

        logger.info(f"AI classified {filename}: {plan.action.value} -> {plan.target_area}")
        return plan

    except Exception as e:
        logger.error(f"AI classification failed for {filename}: {e}")
        # Return a skip plan on error
        return NotePlan(
            source_path=str(note_path),
            action=NoteAction.SKIP,
            confidence=0.0,
            reasoning=f"AI classification failed: {e}",
            classification_source="ai",
            user_feedback=user_feedback,
        )


def classify_batch_with_ai(
    note_paths: list[Path],
    learned_corrections: list[Correction] | None = None,
) -> list[NotePlan]:
    """Classify multiple notes in a single API call.

    Args:
        note_paths: List of note paths to classify (max 10 recommended)
        learned_corrections: Past corrections to include as context

    Returns:
        List of NotePlans for each note
    """
    if not note_paths:
        return []

    # Build note list for prompt
    note_list = []
    note_contents = []

    for i, np in enumerate(note_paths[:10]):  # Limit to 10 notes per batch
        content = get_note_content(np, max_chars=500)  # Shorter for batch
        frontmatter = parse_frontmatter(np)

        entry = f"{i+1}. {np.name}"
        if frontmatter:
            if frontmatter.category:
                entry += f" [category: {frontmatter.category}]"
            if frontmatter.tags:
                entry += f" [tags: {', '.join(frontmatter.tags[:3])}]"

        note_list.append(entry)

        if content:
            preview = content[:200].replace("\n", " ")
            note_contents.append(f"{i+1}. {preview}...")
        else:
            note_contents.append(f"{i+1}. (no content)")

    notes_text = "\n".join(note_list)
    contents_text = "\n".join(note_contents)

    # Build context from learned corrections
    correction_context = ""
    if learned_corrections:
        correction_examples = "\n".join(
            f"- {c.to_rule_description()}" for c in learned_corrections[:10]
        )
        correction_context = f"""
## Learned User Preferences
{correction_examples}
"""

    prompt = f"""You are an Obsidian vault organization assistant. Classify the following notes into appropriate Area folders.

## Notes to Classify
{notes_text}

## Note Content Previews
{contents_text}

## Available Area Folders
- 41 - Finance: Trading, investments, budgeting
- 42 - Family: Family events, kids, home
- 43 - Work: Career, job, professional
- 44 - Health: Medical, fitness, mental health
- 45 - Learning: Courses, tutorials, study
- 46 - Projects: Personal projects, hobbies

## Available Actions
- move: Move to appropriate area folder
- archive: Old content, move to archives
- skip: Leave in place
{correction_context}
## Instructions
Classify each note. Respond with ONLY a JSON array (no markdown):
[
  {{
    "index": 1,
    "action": "move|archive|skip",
    "area": "41 - Finance|42 - Family|43 - Work|44 - Health|45 - Learning|46 - Projects|null",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
  }},
  ...
]
"""

    try:
        client = get_bedrock_client()

        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        result = json.loads(response["body"].read())
        response_content = result["content"][0]["text"]

        # Parse JSON response
        if "```" in response_content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_content, re.DOTALL)
            if match:
                response_content = match.group(1)

        classifications = json.loads(response_content)

        # Build NotePlans from response
        plans = []
        for classification in classifications:
            idx = classification.get("index", 1) - 1
            if idx < 0 or idx >= len(note_paths):
                continue

            note_path = note_paths[idx]
            filename = note_path.name
            frontmatter = parse_frontmatter(note_path)

            # Build destination path
            destination = None
            target_area = None
            raw_area = classification.get("area")

            if classification["action"] == "archive":
                destination = str(get_archive_path(filename))
            elif raw_area and raw_area != "null" and raw_area in AreaFolder.ALL:
                target_area = raw_area
                destination = str(get_area_path(target_area, filename))

            plan = NotePlan(
                source_path=str(note_path),
                action=NoteAction(classification["action"]),
                destination_path=destination,
                target_area=target_area,
                confidence=float(classification.get("confidence", 0.8)),
                reasoning=classification.get("reasoning", "AI classification"),
                classification_source="ai",
                frontmatter_category=frontmatter.category if frontmatter else None,
                frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
            )
            plans.append(plan)

        logger.info(f"AI batch classified {len(plans)} notes")
        return plans

    except Exception as e:
        logger.error(f"AI batch classification failed: {e}")
        # Return skip plans for all notes on error
        return [
            NotePlan(
                source_path=str(np),
                action=NoteAction.SKIP,
                confidence=0.0,
                reasoning=f"AI classification failed: {e}",
                classification_source="ai",
            )
            for np in note_paths
        ]


def extract_correction_pattern(correction: Correction) -> Correction:
    """Use AI to extract generalizable patterns from a correction.

    This helps the system learn from specific corrections and apply
    them to similar notes in the future.
    """
    prompt = f"""Analyze this user correction and extract patterns that could apply to similar notes.

## Original Classification
- Filename: {correction.original_filename}
- Classified as: {correction.original_action.value} -> {correction.original_area or 'None'}

## User's Correction
- Should be: {correction.corrected_action.value} -> {correction.corrected_area or 'archive'}
- User said: "{correction.user_feedback}"

## Instructions
Extract patterns that would help identify similar notes in the future:

1. What regex pattern would match filenames like this?
2. What keywords indicate this type of note?

Respond with ONLY a JSON object:
{{
    "filename_pattern": "regex pattern or null",
    "keywords": ["list", "of", "keywords"],
    "reasoning": "Why these patterns were extracted"
}}
"""

    try:
        client = get_bedrock_client()

        response = client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        result = json.loads(response["body"].read())
        response_content = result["content"][0]["text"]

        # Parse JSON
        if "```" in response_content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_content, re.DOTALL)
            if match:
                response_content = match.group(1)

        patterns = json.loads(response_content)

        # Update correction with extracted patterns
        correction.filename_pattern = patterns.get("filename_pattern")
        correction.keywords = patterns.get("keywords", [])

        logger.info(f"Extracted patterns for correction: {correction.keywords}")
        return correction

    except Exception as e:
        logger.error(f"Pattern extraction failed: {e}")
        return correction
