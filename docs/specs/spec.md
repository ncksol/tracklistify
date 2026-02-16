# Feature Specification: Tracklistify

**Feature**: `tracklistify`
**Created**: 2026-02-16
**Status**: Draft
**Input**: User description: "Web app that takes a link to a YouTube video with a DJ set and tries to detect every single track in that video in order with timestamps. Single user only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a DJ Set for Track Detection (Priority: P1)

A user pastes a YouTube link of a DJ set into the app. The system downloads the audio, runs audio fingerprinting against the entire recording, and returns an ordered tracklist with timestamps showing when each track starts and ends.

**Why this priority**: This is the entire core value proposition. Without track detection, there is no product.

**Independent Test**: Paste a known DJ set URL (e.g., a Boiler Room set with a published tracklist). The app should return a list of identified tracks with timestamps that roughly match the known tracklist.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** the user pastes a valid YouTube URL containing a DJ set and submits it, **Then** the system begins processing and shows a progress indicator.
2. **Given** the system is processing a DJ set, **When** audio fingerprinting completes, **Then** the user sees an ordered list of detected tracks with artist, title, and start timestamp for each.
3. **Given** a DJ set has been processed, **When** some tracks could not be identified, **Then** those segments are shown as "Unidentified" with their timestamps, so the user knows gaps exist.
4. **Given** the user submits a URL, **When** the URL is not a valid YouTube link, **Then** the system shows a clear error message.

---

### User Story 2 - View and Browse Detection Results (Priority: P2)

After processing completes, the user can browse the tracklist in a clean, readable format. Each track shows its position in the set, timestamps, and identified metadata (artist, title). The user can click a track to jump to that point in the original YouTube video.

**Why this priority**: Raw detection results need a usable presentation layer to be valuable. This turns data into a product.

**Independent Test**: After a set is processed, the results page displays all tracks in order. Clicking a track opens the YouTube video at the correct timestamp.

**Acceptance Scenarios**:

1. **Given** a DJ set has been processed, **When** the user views the results, **Then** tracks are displayed in chronological order with position number, start time, artist, and title.
2. **Given** the results are displayed, **When** the user clicks on a track entry, **Then** the YouTube video opens (or seeks) to that track's start timestamp.
3. **Given** the results are displayed, **When** there are unidentified segments, **Then** they are visually distinct from identified tracks.

---

### User Story 3 - Edit and Correct the Tracklist (Priority: P3)

Audio fingerprinting isn't perfect. The user can manually edit the generated tracklist — correcting misidentified tracks, filling in unidentified ones, adjusting timestamps, and removing false positives.

**Why this priority**: Detection accuracy will never be 100%. Manual correction turns an approximate tool into a reliable one. But the app is still useful without it (view-only).

**Independent Test**: After processing, the user can click "Edit" on any track, change the artist/title, adjust the timestamp, and save. Changes persist on page reload.

**Acceptance Scenarios**:

1. **Given** a processed tracklist, **When** the user clicks edit on a track, **Then** the artist, title, and start time become editable fields.
2. **Given** the user is editing a track, **When** they save changes, **Then** the updated information persists and displays correctly.
3. **Given** an unidentified segment, **When** the user fills in the artist and title manually, **Then** the segment is no longer marked as unidentified.
4. **Given** a false positive track, **When** the user deletes it, **Then** it is removed from the tracklist and adjacent timestamps adjust accordingly.

---

### User Story 4 - Export the Tracklist (Priority: P4)

The user can export the final tracklist in common formats for sharing or archival — plain text, JSON, or a shareable link.

**Why this priority**: Export is a natural endpoint of the workflow but not required for core functionality. The tracklist is already viewable in-app.

**Independent Test**: After processing (and optionally editing), the user clicks "Export", selects a format, and receives a correctly formatted file or link.

**Acceptance Scenarios**:

1. **Given** a processed tracklist, **When** the user clicks export and selects plain text, **Then** a formatted text file downloads with timestamps, artists, and titles.
2. **Given** a processed tracklist, **When** the user clicks export and selects JSON, **Then** a structured JSON file downloads with all track metadata.
3. **Given** an exported tracklist, **When** shared as a link, **Then** the recipient can view the tracklist without needing an account.

---

### User Story 5 - View Processing History (Priority: P5)

The user can see a list of previously processed DJ sets and access their tracklists again without re-processing.

**Why this priority**: Nice-to-have for repeat use, but the app delivers full value with a single submission flow.

**Independent Test**: After processing multiple sets, the user navigates to a history page showing all past submissions with links to their results.

**Acceptance Scenarios**:

1. **Given** the user has processed multiple DJ sets, **When** they visit the history page, **Then** all past submissions are listed with title, date processed, and track count.
2. **Given** the history page, **When** the user clicks on a past submission, **Then** the full tracklist results are displayed.

---

### Edge Cases

- What happens when the YouTube video is longer than 6 hours?
- What happens when the video is a single track (not a DJ set)?
- What happens when the video is region-locked or age-restricted?
- What happens when the video is taken down after submission but before processing completes?
- What happens when two tracks are playing simultaneously (beatmatching/transition)?
- What happens when the same track appears multiple times in a set?
- What happens when the video has no music (e.g., a talk or interview linked by mistake)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a YouTube URL as input and validate it before processing.
- **FR-002**: System MUST extract audio from the YouTube video for fingerprinting.
- **FR-003**: System MUST run audio fingerprinting across the full duration of the extracted audio.
- **FR-004**: System MUST return detected tracks in chronological order with start timestamps.
- **FR-005**: System MUST display unidentified segments with their timestamp ranges.
- **FR-006**: System MUST show processing progress to the user during detection.
- **FR-007**: System MUST allow the user to edit track metadata (artist, title) after detection.
- **FR-008**: System MUST allow the user to adjust timestamps of detected tracks.
- **FR-009**: System MUST allow the user to delete false positive tracks from results.
- **FR-010**: System MUST persist all tracklist data (detected and edited) across sessions.
- **FR-011**: System MUST support exporting tracklists in plain text and JSON formats.
- **FR-012**: System MUST generate a shareable link for any processed tracklist.
- **FR-013**: System MUST handle DJ transitions gracefully — overlapping tracks should be represented as separate entries with overlapping timestamps.
- **FR-014**: System MUST reject non-YouTube URLs with a clear error message.
- **FR-015**: System MUST handle videos that are unavailable, private, or region-locked with appropriate error messages.

### Key Entities

- **DJSet**: A submitted YouTube video — URL, title, duration, date submitted, processing status.
- **Track**: A detected or manually entered track within a set — position, start time, end time, artist, title, confidence score, identification source.
- **Tracklist**: The ordered collection of tracks for a DJ set — linked to a DJSet, contains export/share metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can submit a YouTube URL and receive a tracklist within a reasonable time relative to the video's duration (target: processing time < 50% of video duration).
- **SC-002**: For well-known commercial tracks, detection accuracy is at least 70% (7 out of 10 tracks correctly identified in a typical DJ set).
- **SC-003**: Users can view, edit, and export a tracklist in under 2 minutes after processing completes.
- **SC-004**: Every detected track includes a timestamp accurate to within 10 seconds of the actual track start.
- **SC-005**: The app handles DJ sets up to 4 hours long without failure.

## Assumptions

- Single user — no authentication, accounts, or multi-tenancy required. The app is for personal use.
- The user has a modern browser (no legacy browser support needed).
- Audio fingerprinting accuracy depends on the quality of the fingerprinting service's catalogue — niche/unreleased tracks may not be identifiable.
- YouTube video availability is outside our control — processing fails gracefully if a video becomes unavailable.
- Processing is asynchronous — the user does not need to keep the browser open during detection.
