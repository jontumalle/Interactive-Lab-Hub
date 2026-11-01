"""Shared JSON-compatible contracts. Pipeline paths never appear in API output."""
from typing import Callable, Literal, NotRequired, Protocol, TypedDict

VIBES = ("Relaxed", "Exciting", "Adventurous", "Meaningful", "Funny", "Awe-inspiring")
State = Literal["collecting", "queued", "processing", "ready", "failed"]
Stage = Literal["observe", "synthesize", "outline", "chapter", "framing", "day", "narration"]


class Metadata(TypedDict):
    captured_at: str | None  # ISO 8601; preserve an absent timezone
    latitude: float | None
    longitude: float | None
    place_name: str | None
    embedded_description: str | None


class PhotoInput(TypedDict):
    id: str
    prepared_image_path: str
    analysis_image_path: str
    submission_order: int
    metadata: Metadata  # effective metadata, with user corrections applied
    extracted_metadata: NotRequired[Metadata]  # unchanged source values for the editor
    user_description: str
    vibes: list[str]


class Chapter(TypedDict):
    photo_id: str
    title: str
    narrative: str
    location: str | None
    time: str | None
    audio_path: str | None
    audio_error: NotRequired[str | None]


class StoryText(TypedDict):
    text: str
    audio_path: str | None
    audio_error: NotRequired[str | None]


class DayStory(TypedDict):
    id: str
    date: str | None
    title: str
    narrative: str
    moment_ids: list[str]
    audio_path: str | None
    audio_error: NotRequired[str | None]


class Story(TypedDict):
    title: str
    opening: StoryText
    chapters: list[Chapter]
    closing: StoryText
    narration: Literal["available", "unavailable", "partial"]
    story_style: NotRequired[Literal["connected_journal"]]
    journey_version: NotRequired[int]
    days: NotRequired[list[DayStory]]


class ProcessingError(TypedDict):
    stage: Stage | None
    photo_id: str | None
    message: str
    retryable: bool


class ProcessingStatus(TypedDict):
    state: State
    current_stage: Stage | None
    completed: int
    total: int
    error: ProcessingError | None


class Checkpoint(TypedDict):
    stage: Stage
    photo_id: str | None
    result: dict


class Trip(TypedDict):
    schema_version: int
    id: str
    title: str
    photos: list[PhotoInput]
    status: ProcessingStatus
    checkpoints: list[Checkpoint]
    story: Story | None
    created_at: str
    updated_at: str
    demo: NotRequired[bool]
    job_kind: NotRequired[Literal["story", "narration", "days"]]
    edition_id: NotRequired[str]


class Pipeline(Protocol):
    def run(self, trip: Trip, output_dir: str, checkpoint: Callable[[Checkpoint], None]) -> Story:
        """Reuse persisted trip checkpoints; save each new stage before proceeding.

        Called only by the single worker after explicit submission. Return local
        paths, never browser URLs. Raise StageFailure for retryable model errors.
        """
        ...


class StageFailure(RuntimeError):
    def __init__(self, stage: Stage, message: str, photo_id: str | None = None):
        super().__init__(message)
        self.stage = stage
        self.photo_id = photo_id
