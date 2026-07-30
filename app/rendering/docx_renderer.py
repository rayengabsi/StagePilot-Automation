from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from app.rendering.abstract import DocumentRenderer
from app.rendering.models import CoverLetterData, DocumentOutput, RenderContext
from app.rendering.template_loader import TemplateDef
from app.rendering.theme_loader import ThemeDef


class DocxRenderer(DocumentRenderer):
    """DOCX document renderer using python-docx."""

    def render_resume(
        self,
        context: RenderContext,
        template: TemplateDef,
        theme: ThemeDef,
        output_path: Path,
    ) -> DocumentOutput:
        effective = self._apply_theme(template, theme)
        doc = Document()
        self._set_margins(doc, effective)
        sections_rendered = 0

        hc = self._hex_to_rgb(effective.colors.primary)
        sc = self._hex_to_rgb(effective.colors.secondary)

        name = context.personal_info.full_name
        heading = doc.add_heading(name, level=0)
        heading.alignment = self._align(effective.header.alignment)
        for run in heading.runs:
            run.font.color.rgb = hc

        contact_parts: list[str] = []
        if context.personal_info.email:
            contact_parts.append(context.personal_info.email)
        if context.personal_info.phone:
            contact_parts.append(context.personal_info.phone)
        if context.personal_info.location:
            contact_parts.append(context.personal_info.location)
        if contact_parts:
            p = doc.add_paragraph(" | ".join(contact_parts))
            p.alignment = self._align(effective.header.alignment)
            for run in p.runs:
                run.font.size = Pt(effective.fonts.body.size)
                run.font.color.rgb = sc

        for section_name in effective.section_order:
            items = self._get_section_items(context, section_name)
            if not items:
                continue
            sec_style = effective.section_styles.get(section_name)
            layout = sec_style.layout if sec_style else "standard"

            label = section_name.replace("_", " ").title()
            doc.add_heading(label, level=1)

            if layout == "compact":
                self._render_compact_docx(doc, items, effective)
            elif layout == "detailed":
                self._render_detailed_docx(doc, items, effective)
            else:
                self._render_standard_docx(doc, items, effective)
            sections_rendered += 1

        doc.save(str(output_path))
        return DocumentOutput(
            path=output_path,
            format="docx",
            page_count=1,
            sections_rendered=sections_rendered,
            template_used=effective.name,
            theme_used=theme.name,
        )

    def render_cover_letter(
        self,
        context: RenderContext,
        cover_data: CoverLetterData,
        template: TemplateDef,
        theme: ThemeDef,
        output_path: Path,
    ) -> DocumentOutput:
        effective = self._apply_theme(template, theme)
        doc = Document()
        self._set_margins(doc, effective)

        hc = self._hex_to_rgb(effective.colors.primary)
        candidate = cover_data.candidate_name or context.personal_info.full_name

        heading = doc.add_heading(candidate, level=0)
        for run in heading.runs:
            run.font.color.rgb = hc

        title = cover_data.job_title or "Job Application"
        p = doc.add_paragraph(f"Re: {title}")
        for run in p.runs:
            run.font.size = Pt(effective.fonts.subheading.size)
            run.font.color.rgb = self._hex_to_rgb(effective.colors.secondary)

        if cover_data.recipient_name:
            doc.add_paragraph(f"Dear {cover_data.recipient_name},")

        for para in cover_data.body.strip().split("\n\n"):
            p = doc.add_paragraph(para.strip())
            for run in p.runs:
                run.font.size = Pt(effective.fonts.body.size)

        if cover_data.recipient_name:
            doc.add_paragraph("Sincerely,")
            doc.add_paragraph(candidate)

        doc.save(str(output_path))
        return DocumentOutput(
            path=output_path,
            format="docx",
            page_count=1,
            sections_rendered=1,
            template_used=effective.name,
            theme_used=theme.name,
        )

    def _set_margins(self, doc: Document, template: TemplateDef) -> None:
        factor = 10.0 / 254.0
        for section in doc.sections:
            section.top_margin = Inches(template.spacing.page_margin_top * factor)
            section.bottom_margin = Inches(template.spacing.page_margin_bottom * factor)
            section.left_margin = Inches(template.spacing.page_margin_left * factor)
            section.right_margin = Inches(template.spacing.page_margin_right * factor)

    def _render_compact_docx(self, doc: Document, items: list[dict], template: TemplateDef) -> None:
        names = [item.get("name", "") for item in items if item.get("name")]
        if names:
            p = doc.add_paragraph(", ".join(names))
            for run in p.runs:
                run.font.size = Pt(template.fonts.body.size)

    def _render_standard_docx(
        self, doc: Document, items: list[dict], template: TemplateDef
    ) -> None:
        for item in items:
            name = item.get("name", "")
            desc = item.get("description", "")
            line = f"{name}: {desc}" if name and desc else (name or desc)
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.size = Pt(template.fonts.body.size)

    def _render_detailed_docx(
        self, doc: Document, items: list[dict], template: TemplateDef
    ) -> None:
        for item in items:
            header_parts: list[str] = self._build_item_header(item)
            if header_parts:
                p = doc.add_paragraph(" | ".join(header_parts))
                for run in p.runs:
                    run.font.size = Pt(template.fonts.subheading.size)
                    run.bold = True

            desc = item.get("description", "")
            if desc:
                p = doc.add_paragraph(desc)
                for run in p.runs:
                    run.font.size = Pt(template.fonts.body.size)

            technologies = item.get("technologies", [])
            if technologies:
                tech_str = ", ".join(str(t) for t in technologies)
                p = doc.add_paragraph(f"Technologies: {tech_str}")
                for run in p.runs:
                    run.font.size = Pt(template.fonts.body.size)
                    run.italic = True

    def _build_item_header(self, item: dict) -> list[str]:
        parts: list[str] = []
        title = item.get("title", "")
        company = item.get("company", "")
        institution = item.get("institution", "")
        degree = item.get("degree", "")
        field = item.get("field_of_study", "")
        name = item.get("name", "")

        if title and company:
            parts.append(f"{title}, {company}")
        elif company:
            parts.append(company)
        elif title:
            parts.append(title)
        if institution:
            parts.append(institution)
        if degree and field:
            parts.append(f"{degree}, {field}")
        elif name and not parts:
            parts.append(name)

        start = item.get("start_date", "")
        end = item.get("end_date", "")
        if start and end:
            parts.append(f"{start} - {end}")
        elif start:
            parts.append(f"{start} - Present")
        return parts

    def _get_section_items(self, context: RenderContext, section_name: str) -> list[dict]:
        if context.tailored_sections and section_name in context.tailored_sections:
            text = context.tailored_sections[section_name]
            return [{"name": section_name, "description": text}]

        if section_name == "summary":
            if context.tailored_sections and "summary" in context.tailored_sections:
                text = context.tailored_sections["summary"]
                return [{"name": "Summary", "description": text}]
            return []
        if section_name == "skills":
            return [{"name": s.name} for s in context.skills]
        if section_name == "experience":
            exps = []
            for e in context.experience:
                item: dict = {"title": e.title, "company": e.company}
                if e.start_date:
                    item["start_date"] = str(e.start_date)
                if e.end_date:
                    item["end_date"] = str(e.end_date)
                if e.description:
                    item["description"] = e.description
                if e.technologies:
                    item["technologies"] = list(e.technologies)
                exps.append(item)
            return exps
        if section_name == "education":
            eds = []
            for e in context.education:
                item: dict = {
                    "institution": e.institution,
                    "degree": e.degree,
                    "field_of_study": e.field_of_study,
                }
                if e.start_date:
                    item["start_date"] = str(e.start_date)
                if e.end_date:
                    item["end_date"] = str(e.end_date)
                if e.description:
                    item["description"] = e.description
                if e.gpa:
                    item["gpa"] = e.gpa
                eds.append(item)
            return eds
        if section_name == "projects":
            projs = []
            for p in context.projects:
                item: dict = {"name": p.name}
                if p.description:
                    item["description"] = p.description
                if p.technologies:
                    item["technologies"] = list(p.technologies)
                projs.append(item)
            return projs
        if section_name == "languages":
            return [
                {"name": f"{l.name} ({l.proficiency.value if l.proficiency else 'N/A'})"}
                for l in context.languages
            ]
        if section_name == "certifications":
            certs = []
            for c in context.certifications:
                item: dict = {"name": c.name}
                if c.issuer:
                    item["description"] = f"Issued by {c.issuer}"
                certs.append(item)
            return certs
        return []

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> RGBColor:
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 3:
            hex_str = "".join(c * 2 for c in hex_str)
        return RGBColor(
            int(hex_str[0:2], 16),
            int(hex_str[2:4], 16),
            int(hex_str[4:6], 16),
        )

    @staticmethod
    def _align(alignment: str) -> int:
        return {
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
        }.get(alignment, WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def _apply_theme(template: TemplateDef, theme: ThemeDef) -> TemplateDef:
        return theme.apply_to(template)
