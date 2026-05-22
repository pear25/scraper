## ADDED Requirements

### Requirement: Console Article Text Output
WHEN a user enables console article output with the dedicated CLI flag,
the system SHALL write each scraped article to stdout as a stable text block
that includes the article title, the article URL, and the scraped body text.

#### Scenario: Emit one scraped article to stdout
GIVEN a run that scraped one article successfully
AND the user enabled console article output
WHEN the run reaches the output stage
THEN the system writes the article title to stdout
AND the system writes the article URL to stdout
AND the system writes the raw scraped article body to stdout
AND the system preserves the article ordering from the run result

#### Scenario: Emit multiple scraped articles to stdout
GIVEN a run that scraped multiple articles successfully
AND the user enabled console article output
WHEN the run reaches the output stage
THEN the system writes one complete stdout block per article
AND each block remains distinguishable from adjacent article blocks
AND each block contains the matching title, URL, and body for that article

#### Scenario: No articles scraped
GIVEN a run that scraped zero articles
AND the user enabled console article output
WHEN the run reaches the output stage
THEN the system SHALL NOT emit a partial or malformed article block to stdout

### Requirement: Console Output Is Opt-In
WHEN a user does not enable the new console output flags,
the system SHALL preserve the current default behavior of writing run artifacts
to disk without emitting scraped article text to stdout.

#### Scenario: Existing run behavior remains unchanged
GIVEN a normal run without the new console output flags
WHEN the run completes successfully
THEN the system writes the existing JSON artifacts and Markdown report as before
AND the system does not print scraped article bodies to stdout

## MODIFIED Requirements

### Requirement: CLI Output Controls
WHEN a user invokes the scraper CLI,
the system SHALL support both the existing file-based outputs and an explicit
console article-text mode exposed through CLI flags.

#### Scenario: Console output with file outputs retained
GIVEN a user enables the console article-text mode
WHEN the run completes successfully
THEN the system emits the requested article text blocks to stdout
AND the system continues to produce the existing file outputs unless the user
selected an additional flag that explicitly disables them

#### Scenario: Console output with source metadata
GIVEN a user enables the console article-text mode
WHEN an article is emitted to stdout
THEN the emitted text includes the article title before the article body
AND the emitted text includes the article URL before the article body
AND the emitted text does not require reading the JSON artifact to identify the source article