# Phase 6: Resume Rendering & Document Generation Engine

## Overview

Phase 6 delivers the **Resume Rendering & Document Generation Engine** — a production-grade, deterministic document rendering system that transforms structured profile data and AI-tailored content into ATS-friendly professional documents (PDF and DOCX).

**Python owns all document rendering.** AI generates structured content (Phase 5), but Python handles all layout, typography, pagination, and formatting. No AI-generated HTML, PDF, or DOCX ever reaches the output.

---

## Architecture

```
Master Profile (Phase 3)  +  AI Tailored Sections (Phase 5)
                          |
                          v
                RenderContext (unified data model)
                          |
                          v
              ResumeRenderer / CoverLetterRenderer
                    |                 |
                    v                 v
           RendererFactory ──→ DocumentRenderer (ABC)
                    |                 |
                    v                 v
           PdfRenderer (reportlab)   DocxRenderer (python-docx)
                    |                 |
                    v                 v
           resume.pdf              resume.docx
           cover_letter.pdf        cover_letter.docx
```

### Module Layout

```
app/rendering/
├── __init__.py              # Public API exports
├── abstract.py              # DocumentRenderer (ABC)
├── models.py                # RenderContext, CoverLetterData, DocumentOutput, SectionContent
├── assets.py                # Font resolution
├── template_loader.py       # TemplateDef + TemplateLoader (reads templates/*/template.json)
├── theme_loader.py          # ThemeDef + ThemeLoader (reads config/theme.toml)
├── pdf_renderer.py          # PdfRenderer (reportlab)
├── docx_renderer.py         # DocxRenderer (python-docx)
├── resume_renderer.py       # ResumeRenderer (orchestrator)
├── cover_letter_renderer.py # CoverLetterRenderer (orchestrator)
└── renderer_factory.py      # RendererFactory + render_document()
```

---

## Template System

### Architecture

Templates are completely data-driven. Each template is a directory under `templates/` containing a `template.json` file:

```
templates/
├── modern/
│   └── template.json       # Clean, accent-colored dividers, centered header
├── executive/
│   └── template.json       # Traditional serif, formal layout, left-aligned
├── minimal/
│   └── template.json       # Lots of whitespace, subtle dividers, no footer
├── classic/
│   └── template.json       # Traditional serif, conservative black styling
└── professional/
    └── template.json       # Modern sans-serif, blue accent, clean typography
```

**Adding a new template requires ZERO code changes.** Create a new subdirectory under `templates/` with a `template.json` file. The `TemplateLoader` auto-discovers it.

### Template JSON Structure

```json
{
  "name": "modern",
  "version": "1.0.0",
  "description": "Clean modern design with accent color dividers",
  "fonts": {
    "family": "Helvetica",
    "heading": { "family": "Helvetica", "size": 18, "weight": "bold", "color": "#1a1a2e" },
    "subheading": { "family": "Helvetica", "size": 12, "weight": "bold", "color": "#16213e" },
    "body": { "family": "Helvetica", "size": 10, "weight": "normal", "color": "#333333" }
  },
  "colors": {
    "primary": "#1a1a2e", "secondary": "#16213e",
    "accent": "#e94560", "text": "#333333",
    "background": "#ffffff", "section_divider": "#e94560"
  },
  "spacing": {
    "page_margin_top": 50, "page_margin_bottom": 50,
    "page_margin_left": 50, "page_margin_right": 50,
    "section_gap": 18, "line_height": 1.15
  },
  "header": { "alignment": "center", "show_name": true, "show_title": true },
  "footer": { "alignment": "center", "show_page_number": true },
  "section_order": ["summary", "skills", "experience", "education", "projects", "languages", "certifications"],
  "page_size": "A4", "columns": 1,
  "show_header": true, "show_footer": true,
  "show_icons": false, "show_photo": false,
  "section_styles": {
    "summary": { "show_divider": false, "layout": "standard" },
    "skills": { "show_divider": true, "layout": "compact" },
    "experience": { "show_divider": true, "layout": "detailed" },
    "education": { "show_divider": true, "layout": "detailed" },
    "projects": { "show_divider": true, "layout": "detailed" },
    "languages": { "show_divider": true, "layout": "compact" },
    "certifications": { "show_divider": true, "layout": "compact" }
  }
}
```

### Section Layouts

| Layout | Behavior | Used By |
|---|---|---|
| `compact` | Comma-separated inline items | Skills, Languages |
| `standard` | Name: Description per item | Summary |
| `detailed` | Multi-line with title/company/dates/technologies | Experience, Education, Projects |

### TemplateDef (frozen dataclass)

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique template identifier |
| `version` | `str` | Semantic version |
| `description` | `str` | Human-readable description |
| `fonts` | `FontConfig` | Font family + heading/subheading/body styles |
| `colors` | `ColorConfig` | Primary, secondary, accent, text, background, divider |
| `spacing` | `SpacingConfig` | Page margins (top/bottom/left/right), section gap, line height |
| `section_styles` | `dict[str, SectionStyle]` | Per-section divider and layout config |
| `header` | `HeaderStyle` | Alignment, name/title visibility |
| `footer` | `FooterStyle` | Alignment, page number visibility |
| `section_order` | `tuple[str, ...]` | Ordered list of section keys |
| `page_size` | `str` | "A4" or "letter" |
| `columns` | `int` | Column count (1 currently) |
| `show_header` | `bool` | Enable/disable header |
| `show_footer` | `bool` | Enable/disable footer |
| `show_icons` | `bool` | Show section icons |
| `show_photo` | `bool` | Show candidate photo |

---

## Theme System

Themes provide runtime overrides on top of templates, configured in `config/theme.toml`:

```toml
name = "default"

# Override any template value (leave commented to use template defaults)
# primary_color = "#e94560"
# secondary_color = "#16213e"
# accent_color = "#0f3460"
# page_size = "letter"
# font_family = "Helvetica"

[font_sizes]
# heading = 16

[margins]
# top = 50
# bottom = 50
# left = 50
# right = 50

[spacing]
# section_gap = 20
```

The `ThemeDef.apply_to()` method merges theme overrides with a `TemplateDef`, producing a new `TemplateDef` with the overridden values. Unset theme values pass through from the template unchanged.

---

## PDF Rendering Pipeline

Built on **reportlab** (`SimpleDocTemplate`):

```
RenderContext + TemplateDef + ThemeDef
             ↓
PdfRenderer.render_resume()
             ↓
1. Apply theme to template → effective template
2. Calculate page size (A4/letter) and margins
3. Build paragraph styles from template fonts/colors/spacing
4. Build header block (name + contact info)
5. For each section in section_order:
   a. Skip if no items exist
   b. Add section gap spacer
   c. Add section title paragraph
   d. Add divider line (if show_divider)
   e. Render items in compact/standard/detailed layout
6. SimpleDocTemplate.build(story)
             ↓
DocumentOutput(path, format="pdf", sections_rendered, template_used, theme_used)
```

### PDF Features

| Feature | Implementation |
|---|---|
| Selectable text | `Paragraph` with `reportlab` text operators |
| Unicode | reportlab's built-in Unicode support |
| Automatic page breaks | `SimpleDocTemplate` handles flowable overflow |
| Header/Footer | Header built inline; footer via page templates in future |
| Section spacing | `Spacer` + configurable `section_gap` |
| Embedded fonts | ReportLab standard Type1 fonts (Helvetica, Times-Roman, Courier) |
| Consistent typography | `ParagraphStyle` per role (heading, subheading, section_title, body, body_small) |
| ATS compatible | Extractable text, no images, standard fonts, simple layout |
| Metadata | Author, title set on `SimpleDocTemplate` |

---

## DOCX Rendering Pipeline

Built on **python-docx**:

```
RenderContext + TemplateDef + ThemeDef
             ↓
DocxRenderer.render_resume()
             ↓
1. Apply theme → effective
2. Create Document, set margins
3. Add name as Heading 0 (centered/left per template)
4. Add contact info paragraph with pipes
5. For each section:
   a. Add Heading 1 section title
   b. Render items in compact/standard/detailed layout
6. Document.save()
             ↓
DocumentOutput(path, format="docx", ...)
```

### DOCX Features

| Feature | Implementation |
|---|---|
| Heading hierarchy | Heading 0 (name) → Heading 1 (sections) |
| Professional formatting | Consistent font sizes, colors, margins |
| Lists | Detailed layout uses paragraph-per-item with bold headers |
| Page margins | Set via `doc.sections[0].margin` with Inches |
| Consistent fonts | `run.font.size = Pt()`, `run.font.color.rgb` per element |
| Template appearance | Colors applied via `_hex_to_rgb()` |

---

## Supported Sections

| Section | Source | Layout Default |
|---|---|---|
| Summary | AI-tailored or MasterProfile | standard |
| Skills | MasterProfile skills | compact |
| Experience | MasterProfile experience | detailed (title, company, dates, description, technologies) |
| Education | MasterProfile education | detailed (institution, degree, field, dates, GPA) |
| Projects | MasterProfile projects | detailed (name, description, technologies) |
| Languages | MasterProfile languages | compact (name + proficiency) |
| Certifications | MasterProfile certifications | compact (name + issuer) |

If AI-tailored sections are available (from Phase 5 `TailoredResume`), they replace the default section content. The section order is configured per-template.

---

## Configuration

### `config/rendering.toml`

```toml
[general]
default_template = "modern"
default_theme = "default"
default_language = "en"

[page]
page_size = "A4"

[fonts]
font_directory = ""
fallback_family = "Helvetica"

[pdf_metadata]
author = "StagePilot Automation"
subject = "Resume / Cover Letter"
keywords = "resume, cover letter, job application"

[export]
default_formats = ["pdf", "docx"]

[preview]
default_page = 1
```

### `RenderingConfig` (frozen dataclass)

Loaded via `get_rendering_config()` with `lru_cache(maxsize=1)`. Configurable sections: `general`, `page`, `fonts`, `pdf_metadata`, `export`, `preview`.

---

## CLI

Six subcommands under `stagepilot render`:

### `stagepilot render resume [--template NAME] [--theme NAME] [--format FORMAT]`

Generate a resume PDF and/or DOCX from the current MasterProfile.

```bash
# Default template (modern), PDF
uv run stagepilot render resume

# Specific template + all formats
uv run stagepilot render resume --template executive --format all

# Specific template + DOCX only
uv run stagepilot render resume --template minimal --format docx

# Custom output path
uv run stagepilot render resume --output custom_resume.pdf
```

### `stagepilot render cover-letter [--template NAME] [--theme NAME] [--format FORMAT]`

Generate a cover letter PDF and/or DOCX with placeholder content.

```bash
uv run stagepilot render cover-letter --template modern --format pdf
```

### `stagepilot render templates`

List all available templates with metadata.

### `stagepilot render themes`

List available themes.

### `stagepilot render preview --template NAME`

Preview template configuration (dry run, no file generated).

```bash
uv run stagepilot render preview --template modern
```

---

## Output Directory

All generated documents are written to `output/`:

```
output/
├── resume.pdf          # PDF resume
├── resume.docx         # DOCX resume
├── cover_letter.pdf    # PDF cover letter
└── cover_letter.docx   # DOCX cover letter
```

---

## ATS Compatibility

The generated PDFs are designed to be ATS-friendly:

1. **Selectable text** — All content is rendered as text, not images
2. **Standard fonts** — Helvetica and Times-Roman are universally recognized
3. **Simple layout** — Single-column, no tables for layout, no text boxes
4. **No encryption** — No PDF security that would block text extraction
5. **Standard encoding** — WinAnsiEncoding for broad compatibility
6. **Linear content flow** — Sections are rendered in reading order

---

## Design Decisions

### No AI in the Rendering Pipeline

AI (Phase 5) produces structured content. Python owns all document rendering. This ensures:

- **Deterministic output** — Same profile + template = same document every time
- **ATS compatibility** — AI cannot produce non-standard or unparsable formats
- **Speed** — No API calls during document generation
- **Offline capability** — Documents can be generated without internet

### Data-Driven Templates

Templates are plain JSON files, not Python code. This means:

- **Adding a template = adding a JSON file** — no code changes, no redeploy
- **Non-developer editable** — designers can modify template.json directly
- **Version controlled** — template changes tracked in git
- **Discoverable** — `TemplateLoader` auto-discovers all templates

### Theme Override Pattern

Themes don't duplicate template config — they provide targeted overrides. The `ThemeDef.apply_to()` method merges theme values into the template, returning a new `TemplateDef` instance. This avoids mutation and allows multiple independent overrides.

### Frozen Dataclasses

All configuration and model classes use `@dataclass(frozen=True, slots=True)` for immutability, memory efficiency, and type safety. No mutable state leaks into rendering.

### Provider Independence

The `DocumentRenderer` ABC separates the renderer interface from both PDF and DOCX implementations. The `RendererFactory` and per-document-type renderers (`ResumeRenderer`, `CoverLetterRenderer`) are completely provider-independent.

---

## Test Coverage

39 new tests across 7 test files:

| Test File | Tests | Coverage |
|---|---|---|
| `test_render_models.py` | 5 | RenderContext, DocumentOutput, CoverLetterData, SectionContent |
| `test_render_config.py` | 4 | RenderingConfig loading, caching, metadata |
| `test_render_templates.py` | 10 | Template loading, all 5 templates, section styles, error handling |
| `test_render_theme.py` | 7 | ThemeDef, apply_to with color/font/page/spacing overrides, preservation |
| `test_render_pdf.py` | 6 | PDF generation, cover letter, tailored sections, empty profile, theme overrides |
| `test_render_docx.py` | 4 | DOCX generation, cover letter, tailored sections, empty profile |
| `test_render_factory.py` | 6 | Factory list/resume/cover-letter/all-formats/themes |

Total: **196 tests** (157 existing Phase 1–5 + 39 new Phase 6)

---

## Limitations & Future Improvements

### Current Limitations

1. **No two-column layout** — All templates are single-column. Column support is in the `TemplateDef` model (`columns` field) but not yet implemented in renderers.
2. **No embedded custom fonts** — Uses standard reportlab Type1 fonts. TrueType font embedding via `reportlab.pdfbase.ttfonts` is prepared in `assets.py` but requires the font files in `fonts/`.
3. **No automatic page count** — `page_count` is always reported as 1. ReportLab's `SimpleDocTemplate` handles pagination internally but doesn't expose the final count without post-processing.
4. **Cover letter body is placeholder text** — The CLI `render cover-letter` command uses a hardcoded placeholder body. Integration with the Phase 5 `CoverLetterService` for AI-generated body text is straightforward.
5. **No icons or photos** — `show_icons` and `show_photo` fields are defined but not implemented in renderers. Icons would require a font or image asset pipeline.

### Future Improvements

- Two-column layout engine (left sidebar for contact/skills, right for experience/education)
- Embedded TrueType/OpenType fonts with Unicode coverage
- Header/Footer page templates with automatic repetition across pages
- Visual regression testing with pixel comparison
- HTML export format
- Batch rendering multiple templates in one command
- Watermark support (DRAFT, CONFIDENTIAL)
- Page numbering with "Page X of Y"
- Table-based skills matrix layout option
- Award, Volunteer, and Publication section support
