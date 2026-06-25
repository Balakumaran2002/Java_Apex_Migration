import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import json
import html
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle
from app.models import MigrationResponse, ConversionResponse

class ReportService:
    def generate_migration_pdf(self, response: MigrationResponse) -> bytes:
        buffer = io.BytesIO()
        # Set margins to 0.75 inch (54 points)
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        styles = getSampleStyleSheet()
        
        # Define Times-Roman Styles
        title_style = ParagraphStyle(
            'DocTitle',
            fontName='Times-Bold',
            fontSize=26,
            leading=30,
            textColor=colors.HexColor('#1A365D'), # Deep Navy
            alignment=0, # Left-aligned
            spaceAfter=15
        )
        
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            fontName='Times-Italic',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#4A5568'), # Slate Grey
            spaceAfter=25
        )
        
        h1_style = ParagraphStyle(
            'Heading1_Times',
            fontName='Times-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#2C5282'),
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True
        )
        
        h2_style = ParagraphStyle(
            'Heading2_Times',
            fontName='Times-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#2B6CB0'),
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'Body_Times',
            fontName='Times-Roman',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#2D3748'),
            spaceAfter=8
        )
        
        body_bold = ParagraphStyle(
            'BodyBold_Times',
            parent=body_style,
            fontName='Times-Bold'
        )
        
        code_style = ParagraphStyle(
            'Code_Courier',
            fontName='Courier',
            fontSize=8,
            leading=10,
            backColor=colors.HexColor('#F7FAFC'),
            borderColor=colors.HexColor('#E2E8F0'),
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=10
        )
        
        elements = []
        
        # --- TITLE BLOCK ---
        elements.append(Paragraph("Java Migration & Upgrade Report", title_style))
        elements.append(Paragraph(f"AI-Powered AST Transformations and Compilation Analysis", subtitle_style))
        
        # Divider Line
        divider = Table([[""]], colWidths=[504], rowHeights=[2])
        divider.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#3182CE')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0)
        ]))
        elements.append(divider)
        elements.append(Spacer(1, 15))
        
        # --- METADATA SUMMARY TABLE ---
        meta_data = [
            [Paragraph("Target Java Version", body_bold), Paragraph(response.targetVersion, body_style)],
            [Paragraph("Overall Success Status", body_bold), Paragraph("SUCCESS" if response.success else "FAILED", body_bold if response.success else ParagraphStyle('RedBody', parent=body_bold, textColor=colors.HexColor('#E53E3E')))],
            [Paragraph("Build/Compilation Status", body_bold), Paragraph(response.buildStatus, body_style)]
        ]
        
        meta_table = Table(meta_data, colWidths=[200, 304])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F7FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 20))
        
        # --- MODIFIED FILES ---
        if response.modifiedFiles:
            elements.append(Paragraph("Modified Files Summary", h1_style))
            files_content = ""
            for f in response.modifiedFiles:
                files_content += f"• {f}<br/>"
            elements.append(Paragraph(files_content, body_style))
            elements.append(Spacer(1, 10))
            
        # --- AI SUGGESTED FIXES FOR COMPILER ERRORS ---
        if response.suggestedFixes:
            elements.append(Paragraph("AI Self-Healing Recommendations", h1_style))
            elements.append(Preformatted(response.suggestedFixes, code_style))
            elements.append(Spacer(1, 10))
            
        # --- DETAILED CODE MIGRATION REPORT ---
        if response.detailedReport:
            elements.append(Paragraph("Code Difference & Migration Analysis", h1_style))
            try:
                # Cleanup JSON from AI wrapper codeblocks
                clean_json = response.detailedReport.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:].strip()
                elif clean_json.startswith("```"):
                    clean_json = clean_json[3:].strip()
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3].strip()
                
                report_data = json.loads(clean_json)
                
                # Accuracy Metrics
                acc = report_data.get("accuracy", "N/A")
                pct = report_data.get("percentage_migrated", "N/A")
                
                metrics_data = [
                    [Paragraph(f"<b>Estimated AI Accuracy:</b> {acc}%", body_style),
                     Paragraph(f"<b>Migration Completion:</b> {pct}%", body_style)]
                ]
                metrics_table = Table(metrics_data, colWidths=[252, 252])
                metrics_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ]))
                elements.append(metrics_table)
                elements.append(Spacer(1, 10))
                
                # Code blocks styling
                dark_code_style = ParagraphStyle(
                    'DarkCode_Courier',
                    fontName='Courier',
                    fontSize=6.5,
                    leading=8,
                    textColor=colors.HexColor('#E2E8F0'), # Light grey text on dark background
                    wordWrap='CJK'
                )
                
                table_header_style = ParagraphStyle(
                    'TableHeader_Times',
                    fontName='Times-Bold',
                    fontSize=10,
                    textColor=colors.white,
                    alignment=1, # Center
                    spaceAfter=4
                )
                
                for f in report_data.get("files", []):
                    elements.append(Paragraph(f"File: <b>{f.get('filename')}</b>", h2_style))
                    
                    before_code = f.get("before_code", "")
                    after_code = f.get("after_code", "")
                    
                    # Convert to HTML-safe to render properly inside Paragraph
                    before_html = html.escape(before_code[:2000]).replace('\n', '<br/>').replace('  ', '&nbsp;&nbsp;')
                    after_html = html.escape(after_code[:2000]).replace('\n', '<br/>').replace('  ', '&nbsp;&nbsp;')
                    
                    code_data = [
                        [Paragraph("Before Migration", table_header_style), Paragraph("After Migration", table_header_style)],
                        [Paragraph(before_html, dark_code_style), Paragraph(after_html, dark_code_style)]
                    ]
                    
                    # Table width is exactly 500pt (fitting inside 504pt printable area)
                    code_table = Table(code_data, colWidths=[250, 250], hAlign='CENTER')
                    code_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1A202C')), # Dark background
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2D3748')),  # Header background
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#4A5568')),
                        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2D3748')),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ]))
                    elements.append(code_table)
                    elements.append(Spacer(1, 6))
                    
                    explanation_text = f.get('explanation', '')
                    if explanation_text:
                        elements.append(Paragraph(f"<i>AI Explanation:</i> {explanation_text}", body_style))
                    elements.append(Spacer(1, 15))
                    
            except Exception as e:
                # Fallback if parsing fails
                elements.append(Paragraph("AI Detailed Reasoning:", h2_style))
                elements.append(Preformatted(response.detailedReport, code_style))
            
            elements.append(Spacer(1, 10))

        # --- COMPILER ERROR LOGS ---
        if response.buildErrors:
            elements.append(Paragraph("Compilation Errors Log", h1_style))
            log = response.buildErrors[:4000] + "\n...(truncated for report readability)" if len(response.buildErrors) > 4000 else response.buildErrors
            elements.append(Preformatted(log, code_style))
            
        doc.build(elements)
        return buffer.getvalue()

    def generate_conversion_pdf(self, response: ConversionResponse) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        styles = getSampleStyleSheet()
        
        # Times-Roman Styles
        title_style = ParagraphStyle(
            'DocTitle',
            fontName='Times-Bold',
            fontSize=26,
            leading=30,
            textColor=colors.HexColor('#2C5282'),
            alignment=0,
            spaceAfter=15
        )
        
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            fontName='Times-Italic',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#4A5568'),
            spaceAfter=25
        )
        
        h1_style = ParagraphStyle(
            'Heading1_Times',
            fontName='Times-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#2B6CB0'),
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True
        )
        
        body_style = ParagraphStyle(
            'Body_Times',
            fontName='Times-Roman',
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#2D3748'),
            spaceAfter=8
        )
        
        body_bold = ParagraphStyle(
            'BodyBold_Times',
            parent=body_style,
            fontName='Times-Bold'
        )
        
        code_style = ParagraphStyle(
            'Code_Courier',
            fontName='Courier',
            fontSize=7,
            leading=9,
            backColor=colors.HexColor('#1A202C'),
            textColor=colors.HexColor('#E2E8F0'),
            borderPadding=8,
            spaceAfter=15
        )
        
        elements = []
        elements.append(Paragraph("Code Conversion Report", title_style))
        elements.append(Paragraph("Java Source Code converted to Idiomatic Python", subtitle_style))
        
        # Divider Line
        divider = Table([[""]], colWidths=[504], rowHeights=[2])
        divider.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#3182CE')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0)
        ]))
        elements.append(divider)
        elements.append(Spacer(1, 15))
        
        # Success status metadata
        meta_data = [
            [Paragraph("Overall Conversion Status", body_bold), Paragraph("SUCCESS" if response.success else "FAILED", body_bold if response.success else ParagraphStyle('RedBody', parent=body_bold, textColor=colors.HexColor('#E53E3E')))]
        ]
        meta_table = Table(meta_data, colWidths=[200, 304])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F7FAFC')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 20))
        
        if response.convertedFiles:
            for f in response.convertedFiles:
                elements.append(Paragraph(f"File: <b>{f.originalName}</b> → <b>{f.newName}</b>", h1_style))
                if f.explanation:
                    elements.append(Paragraph(f"<i>Explanation:</i> {f.explanation}", body_style))
                
                # Show Python code
                elements.append(Spacer(1, 5))
                elements.append(Preformatted(f.content, code_style))
                elements.append(Spacer(1, 10))
                
        if response.errorMessage:
            elements.append(Paragraph(f"Error Details:", h1_style))
            elements.append(Paragraph(response.errorMessage, body_style))
            
        doc.build(elements)
        return buffer.getvalue()

report_service = ReportService()
