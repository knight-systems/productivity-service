"""AI-powered file classification using Claude via AWS Bedrock."""

from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import boto3

from .config import settings
from .models import Correction, FileAction, FileCategory, FilePlan, LifeDomain

logger = logging.getLogger(__name__)

# Suppress pypdf warnings about malformed PDFs (very noisy)
logging.getLogger("pypdf").setLevel(logging.ERROR)


@dataclass
class FileMetadata:
    """Extracted metadata from a file."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None  # Application that created it
    creation_date: str | None = None
    page_count: int | None = None
    first_page_text: str | None = None  # First ~500 chars of text

    def to_context_string(self) -> str:
        """Format metadata for AI context."""
        parts = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.author:
            parts.append(f"Author: {self.author}")
        if self.subject:
            parts.append(f"Subject: {self.subject}")
        if self.creator:
            parts.append(f"Created by: {self.creator}")
        if self.creation_date:
            parts.append(f"Created: {self.creation_date}")
        if self.page_count:
            parts.append(f"Pages: {self.page_count}")
        if self.first_page_text:
            # Truncate and clean up whitespace
            text = " ".join(self.first_page_text.split())[:300]
            parts.append(f"Content preview: {text}...")
        return "\n".join(parts) if parts else "No metadata available"


def extract_file_metadata(file_path: Path) -> FileMetadata | None:
    """Extract metadata from a file without reading the entire contents.

    Currently supports:
    - PDF: title, author, subject, creator, creation date, page count, first page text

    Returns None if metadata extraction fails or file type not supported.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_metadata(file_path)

    # Add more file types here as needed
    return None


def _extract_pdf_metadata(file_path: Path) -> FileMetadata | None:
    """Extract metadata from a PDF file."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        meta = reader.metadata

        # Extract first page text (limited to avoid loading huge content)
        first_page_text = None
        if reader.pages:
            try:
                text = reader.pages[0].extract_text()
                if text:
                    first_page_text = text[:500]  # First 500 chars only
            except Exception:
                pass  # Some PDFs have extraction issues

        # Parse creation date if available
        creation_date = None
        if meta and meta.creation_date:
            try:
                creation_date = str(meta.creation_date)[:10]  # Just YYYY-MM-DD
            except Exception:
                pass

        return FileMetadata(
            title=meta.title if meta else None,
            author=meta.author if meta else None,
            subject=meta.subject if meta else None,
            creator=meta.creator if meta else None,
            creation_date=creation_date,
            page_count=len(reader.pages),
            first_page_text=first_page_text,
        )

    except Exception as e:
        logger.debug(f"Failed to extract PDF metadata from {file_path}: {e}")
        return None

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
    file_path: Path,
    existing_plan: FilePlan | None = None,
    user_feedback: str | None = None,
    learned_corrections: list[Correction] | None = None,
) -> FilePlan:
    """Classify a file using Claude AI.

    Args:
        file_path: Path to the file to classify
        existing_plan: Optional existing plan (for revisions)
        user_feedback: Natural language feedback from user
        learned_corrections: Past corrections to include as context

    Returns:
        New or revised FilePlan
    """
    filename = file_path.name
    file_size = file_path.stat().st_size if file_path.exists() else 0
    file_ext = file_path.suffix.lower()

    # Extract metadata for supported file types
    metadata = extract_file_metadata(file_path)
    metadata_context = ""
    if metadata:
        metadata_context = f"""
## File Metadata (extracted from file)
{metadata.to_context_string()}
"""

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
The system classified this file as:
- Action: {existing_plan.action.value}
- Domain: {existing_plan.domain.value if existing_plan.domain else 'None'}
- Subfolder: {existing_plan.subfolder or 'None'}
- Reasoning: {existing_plan.reasoning}

## User Feedback
The user said: "{user_feedback}"

Please reclassify based on this feedback.
"""

    prompt = f"""You are a file organization assistant. Classify the following file and determine where it should go.

## File Information
- Filename: {filename}
- Extension: {file_ext}
- Size: {file_size:,} bytes
{metadata_context}
## Available Domains (Life Areas)
- Finance: Financial documents, trading, investments, taxes, bank statements
- Family: Family documents, kids' school, family medical records
- Work: Career documents, resumes, work projects, professional learning
- Health: Personal health records, medical documents, fitness
- Property: Home documents, mortgages, property taxes, HOA
- Personal: General personal items, receipts, screenshots, misc

## Available Subfolders per Domain
- Documents: Official documents, records, statements
- Projects: Active work, ongoing projects
- Research: Learning materials, courses, reference docs
- Media: Photos, videos, screenshots
- Archive: Old/completed items

## Available Actions
- move: Move to appropriate domain/subfolder
- delete: File is temporary, installer, or garbage
- archive: Old file, move to Archive subfolder
- skip: Leave in place (can't determine or user should decide)
{correction_context}
{revision_context}
## File Renaming Convention
If the filename is messy or non-standard, suggest a clean standardized name:
- Documents: YYYY-MM-DD-description-kebab-case.ext (e.g., 2024-01-15-tax-return-2023.pdf)
- Receipts: YYYY-MM-DD-vendor-receipt.ext (e.g., 2024-03-20-amazon-receipt.pdf)
- Screenshots: YYYY-MM-DD-HHMMSS-screenshot.ext (e.g., 2024-12-08-143022-screenshot.png)
- Images: YYYY-MM-DD-description.ext (e.g., 2024-06-15-family-vacation.jpg)
- Trading: YYYY-MM-DD-source-topic.ext (e.g., 2024-02-10-42macro-weekly-report.pdf)
- Health: YYYY-MM-DD-provider-type.ext (e.g., 2024-11-05-kaiser-lab-results.pdf)

Rules: All lowercase, kebab-case, date prefix from filename or today's date.

## Instructions
Analyze the filename and determine the best classification. Consider:
1. File extension and type
2. Keywords in filename
3. File metadata (title, author, content preview) if available
4. Any learned user preferences above
5. User feedback if this is a revision

Respond with ONLY a JSON object (no markdown, no explanation):
{{
    "action": "move|delete|archive|skip|rename",
    "domain": "Finance|Family|Work|Health|Property|Personal|null",
    "subfolder": "Documents|Projects|Research|Media|Archive|null",
    "category": "document|image|video|audio|installer|archive|code|trading|receipt|screenshot|download|unknown",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "suggested_name": "standardized-filename.ext or null if already clean",
    "extracted_pattern": "Optional regex pattern for similar files",
    "extracted_keywords": ["optional", "keywords", "for", "matching"]
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
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Parse JSON response
        # Handle potential markdown code blocks
        if "```" in content:
            content = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if content:
                content = content.group(1)

        classification = json.loads(content)

        # Build destination path
        destination = None
        domain = None
        if classification.get("domain") and classification["domain"] != "null":
            domain = LifeDomain(classification["domain"])
            subfolder = classification.get("subfolder") or "Documents"
            destination = str(
                settings.areas_path / domain.value / subfolder / filename
            )

        # Create new plan
        plan = FilePlan(
            source_path=str(file_path),
            action=FileAction(classification["action"]),
            destination_path=destination,
            category=FileCategory(classification.get("category", "unknown")),
            domain=domain,
            subfolder=classification.get("subfolder"),
            confidence=float(classification.get("confidence", 0.8)),
            reasoning=classification.get("reasoning", "AI classification"),
            classification_source="ai",
            user_feedback=user_feedback,
            original_plan_id=existing_plan.id if existing_plan else None,
            revision_count=(existing_plan.revision_count + 1) if existing_plan else 0,
            suggested_name=classification.get("suggested_name"),
            metadata={
                "extracted_pattern": classification.get("extracted_pattern"),
                "extracted_keywords": classification.get("extracted_keywords", []),
            },
        )

        logger.info(f"AI classified {filename}: {plan.action.value} -> {plan.domain}")
        return plan

    except Exception as e:
        logger.error(f"AI classification failed for {filename}: {e}")
        # Return a skip plan on error
        return FilePlan(
            source_path=str(file_path),
            action=FileAction.SKIP,
            category=FileCategory.UNKNOWN,
            confidence=0.0,
            reasoning=f"AI classification failed: {e}",
            classification_source="ai",
            user_feedback=user_feedback,
        )


def classify_batch_with_ai(
    file_paths: list[Path],
    learned_corrections: list[Correction] | None = None,
) -> list[FilePlan]:
    """Classify multiple files in a single API call.

    Args:
        file_paths: List of file paths to classify (max 20 recommended)
        learned_corrections: Past corrections to include as context

    Returns:
        List of FilePlans for each file
    """
    if not file_paths:
        return []

    # Build file list for prompt with metadata
    file_list = []
    for i, fp in enumerate(file_paths[:20]):  # Limit to 20 files per batch
        stat = fp.stat() if fp.exists() else None
        size = stat.st_size if stat else 0

        # Get file modification date as fallback for renaming
        file_mtime = ""
        if stat:
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime)
            file_mtime = f", modified: {mtime.strftime('%Y-%m-%d')}"

        entry = f"{i+1}. {fp.name} ({fp.suffix}, {size:,} bytes{file_mtime})"

        # Add metadata for PDFs
        metadata = extract_file_metadata(fp)
        if metadata:
            meta_parts = []
            if metadata.title:
                # Sanitize: remove newlines, limit length
                title = " ".join(metadata.title.split())[:100]
                meta_parts.append(f"Title: {title}")
            if metadata.author:
                author = " ".join(metadata.author.split())[:50]
                meta_parts.append(f"Author: {author}")
            if metadata.first_page_text:
                # Sanitize: remove special chars, limit length
                preview = " ".join(metadata.first_page_text.split())[:100]
                preview = re.sub(r'[^\w\s.,;:!?-]', '', preview)  # Remove special chars
                meta_parts.append(f"Preview: {preview}")
            if meta_parts:
                entry += f"\n   Metadata: {'; '.join(meta_parts)}"

        file_list.append(entry)

    files_text = "\n".join(file_list)

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

    prompt = f"""You are a file organization assistant. Classify the following files and determine where each should go.

## Files to Classify
{files_text}

## Available Domains (Life Areas)
- Finance: Financial documents, trading, investments, taxes, bank statements
- Family: Family documents, kids' school, family medical records
- Work: Career documents, resumes, work projects, professional learning
- Health: Personal health records, medical documents, fitness
- Property: Home documents, mortgages, property taxes, HOA
- Personal: General personal items, receipts, screenshots, misc

## Available Subfolders per Domain
- Documents: Official documents, records, statements
- Projects: Active work, ongoing projects
- Research: Learning materials, courses, reference docs
- Media: Photos, videos, screenshots
- Archive: Old/completed items

## Available Actions
- move: Move to appropriate domain/subfolder
- delete: File is temporary, installer, or garbage
- archive: Old file, move to Archive subfolder
- skip: Leave in place (can't determine or user should decide)
- rename: Only rename the file (keep in place)

## File Renaming Convention (IMPORTANT - ALWAYS provide suggested_name for move/archive actions)
For ALL files with action=move or action=archive, you MUST provide a standardized suggested_name:
- Format: YYYY-MM-DD-description-in-kebab-case.ext
- Date: Extract from filename, metadata, OR use the file's "modified" date shown in parentheses. NEVER use "undated".
- Description: Clear, descriptive, based on content/metadata. Max 50 chars.
- Extension: Keep original extension

Examples:
- "_Agent_Full5437.pdf (modified: 2024-05-15)" → "2024-05-15-insurance-policy-full.pdf"
- "FULLTEXT01.pdf (modified: 2023-06-01)" → "2023-06-01-research-paper-fulltext.pdf"
- "GbjBp1KXYAALfW8.jpeg (modified: 2024-03-20)" → "2024-03-20-twitter-image.jpeg"
- "Marc Knight 2022 Tax Return.T23" → "2022-marc-knight-tax-return.t23"
- "FPL _ My Account.pdf (modified: 2024-12-01)" → "2024-12-01-fpl-utility-bill.pdf"

Rules: All lowercase, kebab-case (hyphens not underscores), no special chars.
{correction_context}
## Instructions
Classify each file. For move/archive actions, ALWAYS include suggested_name.
Respond with ONLY a JSON array (no markdown, no explanation):
[
  {{
    "index": 1,
    "action": "move|delete|archive|skip|rename",
    "domain": "Finance|Family|Work|Health|Property|Personal|null",
    "subfolder": "Documents|Projects|Research|Media|Archive|null",
    "category": "document|image|video|audio|installer|archive|code|trading|receipt|screenshot|download|unknown",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "suggested_name": "REQUIRED for move/archive: yyyy-mm-dd-description.ext"
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
                "max_tokens": 4000,  # Increased for batch response
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Parse JSON response
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)

        # Try to parse JSON, handle truncated responses
        try:
            classifications = json.loads(content)
        except json.JSONDecodeError as e:
            # Response may have been truncated - try to salvage partial results
            logger.warning(f"JSON parse error: {e}. Attempting to salvage partial results.")
            # Find the last complete object by looking for },
            last_complete = content.rfind("},")
            if last_complete > 0:
                content = content[:last_complete + 1] + "]"
                try:
                    classifications = json.loads(content)
                    logger.info(f"Salvaged {len(classifications)} classifications from truncated response")
                except json.JSONDecodeError:
                    raise e
            else:
                raise e

        # Valid domain values for mapping
        valid_domains = {d.value: d for d in LifeDomain}
        # Map common AI mistakes to valid domains
        domain_aliases = {
            "Travel": "Personal",
            "Education": "Work",
            "Legal": "Finance",
            "Medical": "Health",
            "Insurance": "Finance",
            "Automotive": "Property",
            "Vehicle": "Property",
            "Car": "Property",
            "Home": "Property",
            "Kids": "Family",
            "Children": "Family",
        }

        # Build FilePlans from response
        plans = []
        for classification in classifications:
            idx = classification.get("index", 1) - 1
            if idx < 0 or idx >= len(file_paths):
                continue

            file_path = file_paths[idx]
            filename = file_path.name

            # Build destination path
            destination = None
            domain = None
            raw_domain = classification.get("domain")
            if raw_domain and raw_domain != "null":
                # Try direct match first
                if raw_domain in valid_domains:
                    domain = valid_domains[raw_domain]
                # Try alias mapping
                elif raw_domain in domain_aliases:
                    mapped = domain_aliases[raw_domain]
                    domain = valid_domains[mapped]
                    logger.debug(f"Mapped domain '{raw_domain}' to '{mapped}'")
                else:
                    # Default to Personal for unknown domains
                    logger.warning(f"Unknown domain '{raw_domain}', defaulting to Personal")
                    domain = LifeDomain.PERSONAL

                subfolder = classification.get("subfolder") or "Documents"
                dest_filename = classification.get("suggested_name") or filename
                destination = str(
                    settings.areas_path / domain.value / subfolder / dest_filename
                )

            plan = FilePlan(
                source_path=str(file_path),
                action=FileAction(classification["action"]),
                destination_path=destination,
                category=FileCategory(classification.get("category", "unknown")),
                domain=domain,
                subfolder=classification.get("subfolder"),
                confidence=float(classification.get("confidence", 0.8)),
                reasoning=classification.get("reasoning", "AI classification"),
                classification_source="ai",
                suggested_name=classification.get("suggested_name"),
            )
            plans.append(plan)

        logger.info(f"AI batch classified {len(plans)} files")
        return plans

    except Exception as e:
        logger.error(f"AI batch classification failed: {e}")
        # Return skip plans for all files on error
        return [
            FilePlan(
                source_path=str(fp),
                action=FileAction.SKIP,
                category=FileCategory.UNKNOWN,
                confidence=0.0,
                reasoning=f"AI classification failed: {e}",
                classification_source="ai",
            )
            for fp in file_paths
        ]


def extract_correction_pattern(correction: Correction) -> Correction:
    """Use AI to extract generalizable patterns from a correction.

    This helps the system learn from specific corrections and apply
    them to similar files in the future.
    """
    prompt = f"""Analyze this user correction and extract patterns that could apply to similar files.

## Original Classification
- Filename: {correction.original_filename}
- Classified as: {correction.original_action.value} -> {correction.original_domain.value if correction.original_domain else 'None'}/{correction.original_subfolder or 'None'}

## User's Correction
- Should be: {correction.corrected_action.value} -> {correction.corrected_domain.value if correction.corrected_domain else 'None'}/{correction.corrected_subfolder or 'None'}
- User said: "{correction.user_feedback}"

## Instructions
Extract patterns that would help identify similar files in the future:

1. What regex pattern would match filenames like this?
2. What keywords indicate this type of file?
3. Is this a specific vendor/source pattern?

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
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Parse JSON
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)

        patterns = json.loads(content)

        # Update correction with extracted patterns
        correction.filename_pattern = patterns.get("filename_pattern")
        correction.keywords = patterns.get("keywords", [])

        logger.info(f"Extracted patterns for correction: {correction.keywords}")
        return correction

    except Exception as e:
        logger.error(f"Pattern extraction failed: {e}")
        return correction
