from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.rendering.abstract import DocumentRenderer
from app.rendering.models import CoverLetterData, DocumentOutput, RenderContext
from app.rendering.template_loader import TemplateDef
from app.rendering.theme_loader import ThemeDef


class PdfRenderer(DocumentRenderer):
    """PDF document renderer using ReportLab."""

    def render_resume(
        self,
        context: RenderContext,
        template: TemplateDef,
        theme: ThemeDef,
        output_path: Path,
    ) -> DocumentOutput:
        effective = self._apply_theme(template, theme)
        page_w, page_h = self._page_size(effective.page_size)
        mul = mm / 10
        margin_l = effective.spacing.page_margin_left * mul
        margin_r = effective.spacing.page_margin_right * mul
        margin_t = effective.spacing.page_margin_top * mul
        margin_b = effective.spacing.page_margin_bottom * mul

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=(page_w, page_h),
            leftMargin=margin_l, rightMargin=margin_r,
            topMargin=margin_t, bottomMargin=margin_b,
            title=f"Resume - {context.personal_info.full_name}",
            author="StagePilot Automation",
        )

        styles = self._build_styles(effective)
        story: list = []
        sections_rendered = 0

        story.extend(self._build_header(context, effective, styles))
        for section_name in effective.section_order:
            items = self._get_section_items(context, section_name)
            if not items:
                continue
            sec_style = effective.section_styles.get(section_name)
            show_div = sec_style.show_divider if sec_style else True
            layout = sec_style.layout if sec_style else "standard"

            story.append(Spacer(1, effective.spacing.section_gap * mul))
            story.append(self._section_title(section_name, effective, styles))
            if show_div:
                story.append(self._divider(effective))
                story.append(Spacer(1, 4))

            if layout == "compact":
                story.append(self._render_compact(items, effective, styles))
            elif layout == "detailed":
                story.extend(self._render_detailed(items, effective, styles))
            else:
                story.append(self._render_standard(items, effective, styles))
            sections_rendered += 1

        doc.build(story)
        return DocumentOutput(
            path=output_path, format="pdf",
            page_count=1, sections_rendered=sections_rendered,
            template_used=effective.name, theme_used=theme.name,
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
        page_w, page_h = self._page_size(effective.page_size)
        mul = mm / 10
        margin_l = effective.spacing.page_margin_left * mul
        margin_r = effective.spacing.page_margin_right * mul
        margin_t = effective.spacing.page_margin_top * mul
        margin_b = effective.spacing.page_margin_bottom * mul

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=(page_w, page_h),
            leftMargin=margin_l, rightMargin=margin_r,
            topMargin=margin_t, bottomMargin=margin_b,
            title=f"Cover Letter - {context.personal_info.full_name}",
            author="StagePilot Automation",
        )

        styles = self._build_styles(effective)
        story: list = []
        candidate = cover_data.candidate_name or context.personal_info.full_name

        story.append(Paragraph(candidate, styles["heading"]))
        story.append(Spacer(1, 6))
        title = cover_data.job_title or "Job Application"
        story.append(Paragraph(f"Re: {title}", styles["subheading"]))
        story.append(Spacer(1, 6))
        if cover_data.recipient_name:
            story.append(Paragraph(f"Dear {cover_data.recipient_name},", styles["body"]))
        story.append(Spacer(1, 6))

        for para in cover_data.body.strip().split("\n\n"):
            story.append(Paragraph(para.strip(), styles["body"]))
            story.append(Spacer(1, 6))

        if cover_data.recipient_name:
            story.append(Paragraph("Sincerely,", styles["body"]))
            story.append(Paragraph(candidate, styles["body"]))

        doc.build(story)
        return DocumentOutput(
            path=output_path, format="pdf",
            page_count=1, sections_rendered=1,
            template_used=effective.name, theme_used=theme.name,
        )

    def _build_header(
        self, context: RenderContext, _template: TemplateDef, styles: dict
    ) -> list:
        result: list = []
        name = context.personal_info.full_name
        result.append(Paragraph(name, styles["heading"]))
        contact_parts: list[str] = []
        if context.personal_info.email:
            contact_parts.append(context.personal_info.email)
        if context.personal_info.phone:
            contact_parts.append(context.personal_info.phone)
        if context.personal_info.location:
            contact_parts.append(context.personal_info.location)
        if contact_parts:
            result.append(Paragraph(" | ".join(contact_parts), styles["subheading"]))
        result.append(Spacer(1, 8))
        return result

    def _section_title(
        self, name: str, _template: TemplateDef, styles: dict
    ) -> Paragraph:
        label = name.replace("_", " ").title()
        return Paragraph(label, styles["section_title"])

    def _divider(self, template: TemplateDef) -> Table:
        color = HexColor(template.colors.section_divider)
        t = Table([[""]], colWidths=[450], rowHeights=[1])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 1, color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    def _render_compact(
        self, items: list[dict], _template: TemplateDef, styles: dict
    ) -> Paragraph:
        names = [item.get("name", "") for item in items if item.get("name")]
        return Paragraph(", ".join(names), styles["body"])

    def _render_standard(
        self, items: list[dict], _template: TemplateDef, styles: dict
    ) -> Paragraph:
        parts = []
        for item in items:
            name = item.get("name", "")
            desc = item.get("description", "")
            if name:
                parts.append(name)
            if desc:
                parts.append(desc)
        return Paragraph("; ".join(parts), styles["body"])

    def _render_detailed(
        self, items: list[dict], _template: TemplateDef, styles: dict
    ) -> list:
        result: list = []
        for item in items:
            name = item.get("name", "")
            title = item.get("title", "")
            company = item.get("company", "")
            institution = item.get("institution", "")
            degree = item.get("degree", "")
            field = item.get("field_of_study", "")
            start = item.get("start_date", "")
            end = item.get("end_date", "")
            desc = item.get("description", "")
            technologies = item.get("technologies", [])

            line_parts: list[str] = []
            if title and company:
                line_parts.append(f"<b>{title}</b> at {company}")
            elif company:
                line_parts.append(company)
            elif title:
                line_parts.append(title)
            if degree and field:
                line_parts.append(f"{degree} in {field}")
            elif institution:
                line_parts.append(institution)
            if name and not line_parts:
                line_parts.append(name)

            date_str = ""
            if start and end:
                date_str = f"{start} - {end}"
            elif start:
                date_str = f"{start} - Present"
            header = " | ".join(line_parts)
            if date_str:
                header = f"{header} | {date_str}"

            if header:
                result.append(Paragraph(header, styles["subheading"]))
            if desc:
                result.append(Paragraph(desc, styles["body"]))
            if technologies:
                tech_str = ", ".join(str(t) for t in technologies)
                txt = f"<i>Technologies: {tech_str}</i>"
                result.append(Paragraph(txt, styles["body_small"]))
            result.append(Spacer(1, 4))
        return result

    def _get_section_items(
        self, context: RenderContext, section_name: str
    ) -> list[dict]:
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

    def _build_styles(self, template: TemplateDef) -> dict:
        hc = template.colors.primary
        sc = template.colors.secondary
        bc = template.colors.text
        ff = template.fonts.family
        hs = template.fonts.heading.size
        ss = template.fonts.subheading.size
        bs = template.fonts.body.size
        lh = template.spacing.line_height
        return {
            "heading": ParagraphStyle(
                "Heading", fontName=ff, fontSize=hs,
                leading=hs * 1.3, textColor=HexColor(hc),
                alignment=TA_CENTER, spaceAfter=4,
            ),
            "subheading": ParagraphStyle(
                "Subheading", fontName=ff, fontSize=ss,
                leading=ss * 1.3, textColor=HexColor(sc),
                alignment=TA_LEFT, spaceAfter=2,
            ),
            "section_title": ParagraphStyle(
                "SectionTitle", fontName=ff, fontSize=ss + 1,
                leading=(ss + 1) * 1.3, textColor=HexColor(hc),
                alignment=TA_LEFT, spaceBefore=4, spaceAfter=2,
            ),
            "body": ParagraphStyle(
                "Body", fontName=ff, fontSize=bs,
                leading=bs * lh, textColor=HexColor(bc),
                alignment=TA_LEFT, spaceAfter=4,
            ),
            "body_small": ParagraphStyle(
                "BodySmall", fontName=ff, fontSize=max(bs - 1, 8),
                leading=max(bs - 1, 8) * 1.2, textColor=HexColor(bc),
                alignment=TA_LEFT, spaceAfter=2,
            ),
        }

    @staticmethod
    def _page_size(size: str) -> tuple[float, float]:
        if size.lower() == "letter":
            return letter
        return A4

    @staticmethod
    def _apply_theme(template: TemplateDef, theme: ThemeDef) -> TemplateDef:
        return theme.apply_to(template)
