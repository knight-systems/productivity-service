"""Rule-based note classification using patterns and frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

from .config import AreaFolder, get_area_path, get_archive_path, is_protected_path, settings
from .frontmatter import FrontmatterData, parse_frontmatter
from .models import NoteAction, NotePlan


class NoteRule:
    """A single classification rule for notes."""

    def __init__(
        self,
        name: str,
        patterns: list[str],
        target_area: str,
        action: NoteAction = NoteAction.MOVE,
        confidence: float = 0.8,
        case_sensitive: bool = False,
    ):
        self.name = name
        self.patterns = patterns
        self.target_area = target_area
        self.action = action
        self.confidence = confidence
        self.case_sensitive = case_sensitive
        # Compile patterns
        flags = 0 if case_sensitive else re.IGNORECASE
        self._compiled = [re.compile(p, flags) for p in patterns]

    def matches(self, filename: str) -> bool:
        """Check if filename matches any pattern."""
        return any(p.search(filename) for p in self._compiled)


# --- Frontmatter Category to Area Mapping ---

CATEGORY_TO_AREA: dict[str, str] = {
    "finance": AreaFolder.FINANCE,
    "trading": AreaFolder.FINANCE,
    "investment": AreaFolder.FINANCE,
    "family": AreaFolder.FAMILY,
    "kids": AreaFolder.FAMILY,
    "children": AreaFolder.FAMILY,
    "work": AreaFolder.WORK,
    "career": AreaFolder.WORK,
    "professional": AreaFolder.WORK,
    "health": AreaFolder.HEALTH,
    "medical": AreaFolder.HEALTH,
    "fitness": AreaFolder.HEALTH,
    "learning": AreaFolder.LEARNING,
    "education": AreaFolder.LEARNING,
    "course": AreaFolder.LEARNING,
    "projects": AreaFolder.PROJECTS,
    "project": AreaFolder.PROJECTS,
    "hobby": AreaFolder.PROJECTS,
}

# --- Tag Keywords to Area Mapping ---

TAG_KEYWORDS: dict[str, str] = {
    # Finance
    "trading": AreaFolder.FINANCE,
    "stocks": AreaFolder.FINANCE,
    "crypto": AreaFolder.FINANCE,
    "portfolio": AreaFolder.FINANCE,
    "backtest": AreaFolder.FINANCE,
    "SA2": AreaFolder.FINANCE,
    "42macro": AreaFolder.FINANCE,
    "investment": AreaFolder.FINANCE,
    "budget": AreaFolder.FINANCE,
    "tax": AreaFolder.FINANCE,
    # Family
    "family": AreaFolder.FAMILY,
    "kids": AreaFolder.FAMILY,
    "parenting": AreaFolder.FAMILY,
    "home": AreaFolder.FAMILY,
    # Work
    "work": AreaFolder.WORK,
    "career": AreaFolder.WORK,
    "resume": AreaFolder.WORK,
    "job": AreaFolder.WORK,
    "interview": AreaFolder.WORK,
    # Health
    "health": AreaFolder.HEALTH,
    "medical": AreaFolder.HEALTH,
    "fitness": AreaFolder.HEALTH,
    "exercise": AreaFolder.HEALTH,
    "BP": AreaFolder.HEALTH,
    "bloodpressure": AreaFolder.HEALTH,
    # Learning
    "learning": AreaFolder.LEARNING,
    "course": AreaFolder.LEARNING,
    "tutorial": AreaFolder.LEARNING,
    "study": AreaFolder.LEARNING,
    # Projects
    "project": AreaFolder.PROJECTS,
    "hobby": AreaFolder.PROJECTS,
    "diy": AreaFolder.PROJECTS,
}

# --- Filename Pattern Rules ---

FILENAME_RULES: list[NoteRule] = [
    # Finance patterns
    NoteRule(
        name="trading_research",
        patterns=[
            r"trading",
            r"backtest",
            r"SA2",
            r"42macro",
            r"portfolio",
            r"stock",
            r"crypto",
            r"market",
        ],
        target_area=AreaFolder.FINANCE,
        confidence=0.8,
    ),
    # Health patterns
    NoteRule(
        name="health_notes",
        patterns=[
            r"health",
            r"BP[_\s]?Log",
            r"blood[_\s]?pressure",
            r"medical",
            r"fitness",
            r"workout",
            r"exercise",
        ],
        target_area=AreaFolder.HEALTH,
        confidence=0.8,
    ),
    # Work patterns
    NoteRule(
        name="work_notes",
        patterns=[
            r"resume",
            r"cv",
            r"career",
            r"job[_\s]?search",
            r"interview",
            r"work[_\s]?notes",
        ],
        target_area=AreaFolder.WORK,
        confidence=0.8,
    ),
    # Family patterns
    NoteRule(
        name="family_notes",
        patterns=[
            r"family",
            r"kids",
            r"children",
            r"parenting",
            r"school",
        ],
        target_area=AreaFolder.FAMILY,
        confidence=0.8,
    ),
    # Learning patterns
    NoteRule(
        name="learning_notes",
        patterns=[
            r"course",
            r"tutorial",
            r"lesson",
            r"study[_\s]?notes",
            r"learning",
        ],
        target_area=AreaFolder.LEARNING,
        confidence=0.8,
    ),
    # Projects patterns
    NoteRule(
        name="project_notes",
        patterns=[
            r"project[_\s]?notes",
            r"hobby",
            r"diy",
            r"build[_\s]?log",
        ],
        target_area=AreaFolder.PROJECTS,
        confidence=0.8,
    ),
]


def classify_note(note_path: Path) -> NotePlan:
    """Classify a note using rules and frontmatter.

    Priority order:
    1. Skip if in protected folder
    2. Check learned corrections (highest priority)
    3. Frontmatter category (0.95 confidence)
    4. Frontmatter tags (0.9 confidence)
    5. Filename patterns (0.8 confidence)
    6. Return low confidence for AI classification

    Returns a plan with the highest confidence match.
    """
    from .database import get_relevant_corrections, increment_correction_usage

    filename = note_path.name

    # Check if file should be skipped (protected folder)
    if is_protected_path(note_path):
        return NotePlan(
            source_path=str(note_path),
            action=NoteAction.SKIP,
            confidence=1.0,
            reasoning="Note is in a protected folder",
            classification_source="rules",
        )

    # Check if file matches ignore patterns
    if _should_ignore(filename):
        return NotePlan(
            source_path=str(note_path),
            action=NoteAction.SKIP,
            confidence=1.0,
            reasoning="File matches ignore pattern",
            classification_source="rules",
        )

    # Parse frontmatter
    frontmatter = parse_frontmatter(note_path)

    # First, check learned corrections (user preferences take priority)
    try:
        relevant_corrections = get_relevant_corrections(filename, limit=5)
        for correction in relevant_corrections:
            # Check if this correction applies
            if correction.filename_pattern:
                try:
                    if re.search(correction.filename_pattern, filename, re.IGNORECASE):
                        # Strong pattern match - use this correction
                        increment_correction_usage(correction.id)
                        destination = None
                        if correction.corrected_action == NoteAction.MOVE and correction.corrected_area:
                            destination = str(
                                get_area_path(correction.corrected_area, filename)
                            )
                        elif correction.corrected_action == NoteAction.ARCHIVE:
                            destination = str(get_archive_path(filename))

                        return NotePlan(
                            source_path=str(note_path),
                            action=correction.corrected_action,
                            destination_path=destination,
                            target_area=correction.corrected_area,
                            confidence=0.95,
                            reasoning=f"Matched learned pattern: {correction.user_feedback[:50]}",
                            classification_source="learned",
                            frontmatter_category=frontmatter.category if frontmatter else None,
                            frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
                        )
                except re.error:
                    pass

            # Check keyword matches
            if correction.keywords:
                filename_lower = filename.lower()
                matches = sum(
                    1 for kw in correction.keywords if kw.lower() in filename_lower
                )
                if matches >= 2:  # At least 2 keywords match
                    increment_correction_usage(correction.id)
                    destination = None
                    if correction.corrected_action == NoteAction.MOVE and correction.corrected_area:
                        destination = str(
                            get_area_path(correction.corrected_area, filename)
                        )
                    elif correction.corrected_action == NoteAction.ARCHIVE:
                        destination = str(get_archive_path(filename))

                    return NotePlan(
                        source_path=str(note_path),
                        action=correction.corrected_action,
                        destination_path=destination,
                        target_area=correction.corrected_area,
                        confidence=0.85,
                        reasoning=f"Matched learned keywords: {', '.join(correction.keywords[:3])}",
                        classification_source="learned",
                        frontmatter_category=frontmatter.category if frontmatter else None,
                        frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
                    )
    except Exception:
        pass  # Database might not be initialized yet

    # Check frontmatter category
    if frontmatter and frontmatter.category:
        category_lower = frontmatter.category.lower()
        if category_lower in CATEGORY_TO_AREA:
            target_area = CATEGORY_TO_AREA[category_lower]
            destination = str(get_area_path(target_area, filename))
            return NotePlan(
                source_path=str(note_path),
                action=NoteAction.MOVE,
                destination_path=destination,
                target_area=target_area,
                confidence=0.95,
                reasoning=f"Frontmatter category: {frontmatter.category}",
                classification_source="rules",
                frontmatter_category=frontmatter.category,
                frontmatter_tags=frontmatter.tags or [],
            )

    # Check frontmatter tags
    if frontmatter and frontmatter.tags:
        for tag in frontmatter.tags:
            tag_lower = tag.lower()
            if tag_lower in TAG_KEYWORDS:
                target_area = TAG_KEYWORDS[tag_lower]
                destination = str(get_area_path(target_area, filename))
                return NotePlan(
                    source_path=str(note_path),
                    action=NoteAction.MOVE,
                    destination_path=destination,
                    target_area=target_area,
                    confidence=0.9,
                    reasoning=f"Frontmatter tag: {tag}",
                    classification_source="rules",
                    frontmatter_category=frontmatter.category,
                    frontmatter_tags=frontmatter.tags or [],
                )

    # Check filename patterns
    for rule in FILENAME_RULES:
        if rule.matches(filename):
            destination = str(get_area_path(rule.target_area, filename))
            return NotePlan(
                source_path=str(note_path),
                action=rule.action,
                destination_path=destination,
                target_area=rule.target_area,
                confidence=rule.confidence,
                reasoning=f"Matched filename rule: {rule.name}",
                classification_source="rules",
                frontmatter_category=frontmatter.category if frontmatter else None,
                frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
            )

    # No match - return low confidence for AI classification
    return NotePlan(
        source_path=str(note_path),
        action=NoteAction.SKIP,
        confidence=0.0,
        reasoning="No matching rule found - needs AI classification",
        classification_source="rules",
        frontmatter_category=frontmatter.category if frontmatter else None,
        frontmatter_tags=(frontmatter.tags or []) if frontmatter else [],
    )


def _should_ignore(filename: str) -> bool:
    """Check if file should be ignored."""
    for pattern in settings.ignore_patterns:
        if pattern.startswith("*"):
            if filename.endswith(pattern[1:]):
                return True
        elif pattern in filename:
            return True
    return filename.startswith(".")


def needs_ai_classification(plan: NotePlan) -> bool:
    """Check if a plan needs AI classification for better accuracy."""
    # Needs AI if confidence is below threshold
    return plan.confidence < settings.ai_confidence_threshold
