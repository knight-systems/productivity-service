"""Rule-based file classification using patterns and heuristics."""

import re
from pathlib import Path

from .config import settings
from .models import FileAction, FileCategory, FilePlan, LifeDomain


class ClassificationRule:
    """A single classification rule."""

    def __init__(
        self,
        name: str,
        patterns: list[str],
        category: FileCategory,
        action: FileAction,
        domain: LifeDomain | None = None,
        subfolder: str | None = None,
        confidence: float = 0.9,
        case_sensitive: bool = False,
    ):
        self.name = name
        self.patterns = patterns
        self.category = category
        self.action = action
        self.domain = domain
        self.subfolder = subfolder
        self.confidence = confidence
        self.case_sensitive = case_sensitive
        # Compile patterns
        flags = 0 if case_sensitive else re.IGNORECASE
        self._compiled = [re.compile(p, flags) for p in patterns]

    def matches(self, filename: str) -> bool:
        """Check if filename matches any pattern."""
        return any(p.search(filename) for p in self._compiled)


# --- Classification Rules ---

RULES: list[ClassificationRule] = [
    # === DELETE RULES (installers, temp files) ===
    ClassificationRule(
        name="mac_installers",
        patterns=[r"\.dmg$", r"\.pkg$"],
        category=FileCategory.INSTALLER,
        action=FileAction.DELETE,
        confidence=0.95,
    ),
    ClassificationRule(
        name="windows_installers",
        patterns=[r"\.exe$", r"\.msi$"],
        category=FileCategory.INSTALLER,
        action=FileAction.DELETE,
        confidence=0.95,
    ),
    ClassificationRule(
        name="temp_files",
        patterns=[r"\.tmp$", r"\.part$", r"\.crdownload$", r"~$"],
        category=FileCategory.DOWNLOAD,
        action=FileAction.DELETE,
        confidence=0.95,
    ),
    ClassificationRule(
        name="windows_artifacts",
        patterns=[r"\$RECYCLE\.BIN", r"desktop\.ini", r"Thumbs\.db"],
        category=FileCategory.UNKNOWN,
        action=FileAction.DELETE,
        confidence=0.95,
    ),
    # === ARCHIVE RULES ===
    ClassificationRule(
        name="archive_files",
        patterns=[r"\.zip$", r"\.tar\.gz$", r"\.tgz$", r"\.rar$", r"\.7z$"],
        category=FileCategory.ARCHIVE,
        action=FileAction.ARCHIVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Archive",
        confidence=0.7,  # Lower confidence - may need AI review
    ),
    # === FINANCE RULES ===
    ClassificationRule(
        name="trading_research",
        patterns=[
            r"SA2",
            r"42Macro",
            r"Factor",
            r"trading",
            r"backtest",
            r"strategy",
        ],
        category=FileCategory.TRADING,
        action=FileAction.MOVE,
        domain=LifeDomain.FINANCE,
        subfolder="Research",
        confidence=0.85,
    ),
    ClassificationRule(
        name="financial_statements",
        patterns=[
            r"statement",
            r"invoice",
            r"tax.*\d{4}",
            r"1099",
            r"W-?2",
            r"bank.*statement",
        ],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.FINANCE,
        subfolder="Documents",
        confidence=0.85,
    ),
    ClassificationRule(
        name="receipts",
        patterns=[r"receipt", r"order.*confirm", r"purchase"],
        category=FileCategory.RECEIPT,
        action=FileAction.MOVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Documents",
        confidence=0.8,
    ),
    # === HEALTH RULES ===
    ClassificationRule(
        name="health_documents",
        patterns=[
            r"BP_Log",
            r"blood.*pressure",
            r"medical",
            r"prescription",
            r"lab.*results",
            r"doctor",
            r"health",
        ],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.HEALTH,
        subfolder="Documents",
        confidence=0.9,
    ),
    # === WORK RULES ===
    ClassificationRule(
        name="work_documents",
        patterns=[r"resume", r"cv", r"cover.*letter", r"job.*application"],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.WORK,
        subfolder="Documents",
        confidence=0.85,
    ),
    ClassificationRule(
        name="learning_materials",
        patterns=[r"course", r"tutorial", r"ebook", r"\.epub$"],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.WORK,
        subfolder="Learning",
        confidence=0.8,
    ),
    # === PROPERTY RULES ===
    ClassificationRule(
        name="property_documents",
        patterns=[
            r"mortgage",
            r"deed",
            r"property.*tax",
            r"HOA",
            r"home.*insurance",
            r"18199",  # Address pattern
        ],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.PROPERTY,
        subfolder="Documents",
        confidence=0.9,
    ),
    # === FAMILY RULES ===
    ClassificationRule(
        name="family_documents",
        patterns=[
            r"birth.*cert",
            r"passport",
            r"social.*security",
            r"marriage",
            r"school.*report",
        ],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=LifeDomain.FAMILY,
        subfolder="Documents",
        confidence=0.9,
    ),
    # === MEDIA RULES ===
    ClassificationRule(
        name="macos_screenshots_delete",
        patterns=[
            # Standard macOS format: Screenshot YYYY-MM-DD at H.MM.SS [AM|PM].png
            # Handles various Unicode spaces: regular space, non-breaking space (U+00A0),
            # and narrow no-break space (U+202F) which macOS uses before AM/PM
            r"^Screenshot[ \u00a0]+\d{4}-\d{2}-\d{2}[ \u00a0]+at[ \u00a0]+\d{1,2}\.\d{2}(\.\d{2})?([ \u00a0\u202f]+(AM|PM))?\.png$",
        ],
        category=FileCategory.SCREENSHOT,
        action=FileAction.DELETE,
        confidence=0.95,
    ),
    ClassificationRule(
        name="screenshots",
        patterns=[
            r"screenshot",
            r"Screen Shot",
            r"Screenshot \d{4}",
            r"CleanShot",
        ],
        category=FileCategory.SCREENSHOT,
        action=FileAction.MOVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Media",
        confidence=0.9,
    ),
    ClassificationRule(
        name="images",
        patterns=[r"\.jpg$", r"\.jpeg$", r"\.png$", r"\.gif$", r"\.heic$"],
        category=FileCategory.IMAGE,
        action=FileAction.MOVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Media",
        confidence=0.6,  # Low confidence - needs context
    ),
    ClassificationRule(
        name="videos",
        patterns=[r"\.mp4$", r"\.mov$", r"\.avi$", r"\.mkv$", r"\.m4v$"],
        category=FileCategory.VIDEO,
        action=FileAction.MOVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Media",
        confidence=0.6,  # Low confidence - needs context
    ),
    ClassificationRule(
        name="audio",
        patterns=[r"\.mp3$", r"\.wav$", r"\.m4a$", r"\.aac$", r"\.flac$"],
        category=FileCategory.AUDIO,
        action=FileAction.MOVE,
        domain=LifeDomain.PERSONAL,
        subfolder="Media",
        confidence=0.6,
    ),
    # === CODE RULES ===
    ClassificationRule(
        name="code_files",
        patterns=[
            r"\.py$",
            r"\.js$",
            r"\.ts$",
            r"\.java$",
            r"\.cpp$",
            r"\.c$",
            r"\.rs$",
            r"\.go$",
        ],
        category=FileCategory.CODE,
        action=FileAction.MOVE,
        domain=LifeDomain.WORK,
        subfolder="Projects",
        confidence=0.7,
    ),
    # === DOCUMENT RULES (general, lower priority) ===
    ClassificationRule(
        name="pdf_documents",
        patterns=[r"\.pdf$"],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=None,  # Needs AI classification for domain
        subfolder="Documents",
        confidence=0.5,  # Low - needs AI to determine domain
    ),
    ClassificationRule(
        name="office_documents",
        patterns=[r"\.docx?$", r"\.xlsx?$", r"\.pptx?$", r"\.pages$", r"\.numbers$"],
        category=FileCategory.DOCUMENT,
        action=FileAction.MOVE,
        domain=None,
        subfolder="Documents",
        confidence=0.5,
    ),
]


def classify_file(file_path: Path) -> FilePlan:
    """Classify a file using rules and learned corrections.

    Priority order:
    1. Check learned corrections first (highest priority - user preferences)
    2. Check static rules
    3. If confidence < threshold, AI classification should be used

    Returns a plan with the highest confidence match.
    """
    from .database import get_relevant_corrections, increment_correction_usage

    filename = file_path.name
    best_match: ClassificationRule | None = None
    best_confidence = 0.0

    # Check if file should be ignored
    if _should_ignore(filename):
        return FilePlan(
            source_path=str(file_path),
            action=FileAction.SKIP,
            category=FileCategory.UNKNOWN,
            confidence=1.0,
            reasoning="File matches ignore pattern",
            classification_source="rules",
        )

    # First, check learned corrections (user preferences take priority)
    try:
        relevant_corrections = get_relevant_corrections(filename, limit=5)
        for correction in relevant_corrections:
            # Check if this correction applies
            if correction.filename_pattern:
                import re
                try:
                    if re.search(correction.filename_pattern, filename, re.IGNORECASE):
                        # Strong pattern match - use this correction
                        increment_correction_usage(correction.id)
                        destination = None
                        if correction.corrected_action == FileAction.MOVE and correction.corrected_domain:
                            destination = str(
                                settings.areas_path
                                / correction.corrected_domain.value
                                / (correction.corrected_subfolder or "Documents")
                                / filename
                            )
                        return FilePlan(
                            source_path=str(file_path),
                            action=correction.corrected_action,
                            destination_path=destination,
                            category=FileCategory.DOCUMENT,  # Default
                            domain=correction.corrected_domain,
                            subfolder=correction.corrected_subfolder,
                            confidence=0.95,  # High confidence from learned rule
                            reasoning=f"Matched learned pattern from correction: {correction.user_feedback[:50]}",
                            classification_source="learned",
                        )
                except re.error:
                    pass

            # Check keyword matches
            if correction.keywords:
                filename_lower = filename.lower()
                matches = sum(1 for kw in correction.keywords if kw.lower() in filename_lower)
                if matches >= 2:  # At least 2 keywords match
                    increment_correction_usage(correction.id)
                    destination = None
                    if correction.corrected_action == FileAction.MOVE and correction.corrected_domain:
                        destination = str(
                            settings.areas_path
                            / correction.corrected_domain.value
                            / (correction.corrected_subfolder or "Documents")
                            / filename
                        )
                    return FilePlan(
                        source_path=str(file_path),
                        action=correction.corrected_action,
                        destination_path=destination,
                        category=FileCategory.DOCUMENT,
                        domain=correction.corrected_domain,
                        subfolder=correction.corrected_subfolder,
                        confidence=0.85,  # Good confidence from keywords
                        reasoning=f"Matched learned keywords: {', '.join(correction.keywords[:3])}",
                        classification_source="learned",
                    )
    except Exception:
        pass  # Database might not be initialized yet

    # Fall back to static rules
    for rule in RULES:
        if rule.matches(filename):
            if rule.confidence > best_confidence:
                best_match = rule
                best_confidence = rule.confidence

    if best_match:
        # Build destination path
        destination = None
        if best_match.action == FileAction.MOVE and best_match.domain:
            destination = str(
                settings.areas_path
                / best_match.domain.value
                / (best_match.subfolder or "Documents")
                / filename
            )

        return FilePlan(
            source_path=str(file_path),
            action=best_match.action,
            destination_path=destination,
            category=best_match.category,
            domain=best_match.domain,
            subfolder=best_match.subfolder,
            confidence=best_match.confidence,
            reasoning=f"Matched rule: {best_match.name}",
            classification_source="rules",
        )

    # No match - return unknown for AI classification
    return FilePlan(
        source_path=str(file_path),
        action=FileAction.SKIP,
        category=FileCategory.UNKNOWN,
        confidence=0.0,
        reasoning="No matching rule found - needs AI classification",
        classification_source="rules",
    )


def _should_ignore(filename: str) -> bool:
    """Check if file should be ignored."""
    for pattern in settings.ignore_patterns:
        if pattern.startswith("*"):
            if filename.endswith(pattern[1:]):
                return True
        elif pattern in filename:
            return True
    return filename.startswith(".") and settings.ignore_hidden


def needs_ai_classification(plan: FilePlan) -> bool:
    """Check if a plan needs AI classification for better accuracy."""
    # Needs AI if:
    # 1. Confidence is below threshold
    # 2. No domain assigned (generic file type)
    # 3. Category is unknown
    return (
        plan.confidence < settings.ai_confidence_threshold
        or plan.domain is None
        or plan.category == FileCategory.UNKNOWN
    )


def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes."""
    try:
        return file_path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def can_use_ai_for_file(file_path: Path) -> bool:
    """Check if file is suitable for AI classification."""
    if not settings.ai_enabled:
        return False
    size_mb = get_file_size_mb(file_path)
    return size_mb <= settings.max_file_size_for_ai_mb
