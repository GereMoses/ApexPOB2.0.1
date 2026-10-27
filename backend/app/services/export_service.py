"""
Export Service for Reports
Handles PDF, Excel, and CSV exports with company branding
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import io
import os
import uuid
from pathlib import Path
import logging

# PDF generation (optional dependency)
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False
    letter = A4 = colors = getSampleStyleSheet = ParagraphStyle = None  # type: ignore
    inch = SimpleDocTemplate = Table = TableStyle = Paragraph = Spacer = Image = None  # type: ignore
    TA_CENTER = TA_LEFT = TA_RIGHT = None  # type: ignore

# Excel generation (optional dependency)
try:
    import xlsxwriter
    from xlsxwriter.utility import xl_rowcol_to_cell
    _XLSXWRITER_AVAILABLE = True
except ImportError:
    xlsxwriter = None  # type: ignore
    xl_rowcol_to_cell = None  # type: ignore
    _XLSXWRITER_AVAILABLE = False

# CSV generation
import csv

# Celery for async processing (optional)
try:
    from celery import Celery
    _CELERY_AVAILABLE = True
except ImportError:
    Celery = None  # type: ignore
    _CELERY_AVAILABLE = False

# Database and services
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.report import ReportExportLog, ReportTemplate, ReportSchedule
from ..models.system import Company as BaseCompany
from .report_service import ReportService
from .email_service import ReportEmailService as EmailService

logger = logging.getLogger(__name__)

# Celery app configuration (only if celery is available)
celery_app = Celery('report_exports') if _CELERY_AVAILABLE else None


class ExportService:
    """Service for handling report exports in various formats"""
    
    def __init__(self, db: Session):
        self.db = db
        self.report_service = ReportService(db)
        self.email_service = EmailService(db)
        self.export_dir = Path("media/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def queue_export(self, export_id: int, report_code: str, filters: Dict[str, Any], 
                    format: str) -> str:
        """Queue export task for async processing"""
        task = export_report_task.delay(export_id, report_code, filters, format)
        return task.id
    
    def queue_scheduled_export(self, schedule_id: int) -> str:
        """Queue scheduled export task"""
        task = scheduled_export_task.delay(schedule_id)
        return task.id
    
    def generate_export(self, export_id: int, report_code: str, filters: Dict[str, Any], 
                       format: str) -> str:
        """Generate export file and return file path"""
        try:
            # Get report data
            result = self.report_service.get_report_data(report_code, filters, 1, 10000)
            
            # Generate file based on format
            if format.lower() == 'pdf':
                file_path = self._generate_pdf(result, report_code, filters)
            elif format.lower() == 'xlsx':
                file_path = self._generate_excel(result, report_code, filters)
            elif format.lower() == 'csv':
                file_path = self._generate_csv(result, report_code, filters)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            # Update export log
            export_log = self.db.query(ReportExportLog).filter(
                ReportExportLog.id == export_id
            ).first()
            
            if export_log:
                export_log.status = 'completed'
                export_log.file_path = file_path
                export_log.row_count = len(result.get('data', []))
                export_log.file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                self.db.commit()
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error generating export: {str(e)}")
            
            # Update export log with error
            export_log = self.db.query(ReportExportLog).filter(
                ReportExportLog.id == export_id
            ).first()
            
            if export_log:
                export_log.status = 'failed'
                export_log.error_message = str(e)
                self.db.commit()
            
            raise
    
    def _generate_pdf(self, result: Dict[str, Any], report_code: str, filters: Dict[str, Any]) -> str:
        """Generate PDF report with company branding"""
        # Generate unique filename
        filename = f"report_{report_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.export_dir / filename
        
        # Create PDF document
        # Landscape with modest margins: most reports have 8-14 columns.
        from reportlab.lib.pagesizes import landscape
        doc = SimpleDocTemplate(str(file_path), pagesize=landscape(A4), rightMargin=28, leftMargin=28,
                              topMargin=36, bottomMargin=36)
        
        # Get company info for header
        company = self.db.query(BaseCompany).first()
        company_name = company.company_name if company else "Apex POB"
        company_logo = company.logo_path if company and company.logo_path else None
        
        # Build story
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            alignment=TA_LEFT
        )
        
        # Company header
        if company_logo and os.path.exists(company_logo):
            logo = Image(company_logo, width=1.5*inch, height=0.75*inch)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 12))
        
        # Report title
        report_name = self._get_report_name(report_code)
        story.append(Paragraph(f"{company_name}", title_style))
        story.append(Paragraph(f"{report_name}", header_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Filters section
        if filters:
            story.append(Paragraph("Filters Applied:", header_style))
            for key, value in filters.items():
                story.append(Paragraph(f"  {key}: {value}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Summary section
        if result.get('summary'):
            story.append(Paragraph("Summary:", header_style))
            for key, value in result['summary'].items():
                story.append(Paragraph(f"  {key.replace('_', ' ').title()}: {value}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Data table
        columns = result.get('columns', [])
        rows = result.get('rows', [])
        
        if rows:
            # Prepare table data
            table_data = []
            
            # Header row
            header_row = [col['label'] for col in columns]
            table_data.append(header_row)
            
            # Data rows
            for row in rows:
                data_row = []
                for col in columns:
                    value = row.get(col['field'], '')
                    # Format based on type
                    if col.get('type') == 'currency' and isinstance(value, (int, float, Decimal)):
                        data_row.append(f"${value:,.2f}")
                    elif col.get('type') == 'percentage' and isinstance(value, (int, float, Decimal)):
                        data_row.append(f"{value:.1f}%")
                    elif col.get('type') == 'datetime' and value:
                        if isinstance(value, str):
                            data_row.append(value)
                        else:
                            data_row.append(value.strftime('%Y-%m-%d %H:%M'))
                    elif col.get('type') == 'date' and value:
                        if isinstance(value, str):
                            data_row.append(value)
                        else:
                            data_row.append(value.strftime('%Y-%m-%d'))
                    elif col.get('type') == 'boolean':
                        data_row.append('Yes' if value else 'No')
                    else:
                        data_row.append(str(value))
                table_data.append(data_row)
            
            # Create table
            table = Table(table_data, repeatRows=1)
            
            # Style the table
            table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                
                # Data rows
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            # Share the printable width across the columns (a fixed 1.5" per column ran
            # off the page for anything over ~7 columns).
            n = max(len(columns), 1)
            table._argW = [doc.width / n] * n
            
            story.append(table)
        
        # Page number + generated-at footer on every page. (Reading doc.page while the
        # story is still being assembled raised AttributeError: every PDF export failed.)
        def _footer(canvas, d):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(d.leftMargin, 18, f"{company_name} · generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            canvas.drawRightString(d.pagesize[0] - d.rightMargin, 18, f"Page {d.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        
        return str(file_path)
    
    def _generate_excel(self, result: Dict[str, Any], report_code: str, filters: Dict[str, Any]) -> str:
        """Generate Excel report with formatting"""
        # Generate unique filename
        filename = f"report_{report_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path = self.export_dir / filename
        
        # Create workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Create worksheet
        worksheet = workbook.add_worksheet('Report')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        company_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': '#2F5496',
            'align': 'center'
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': '#2F5496',
            'align': 'center'
        })
        
        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd hh:mm:ss',
            'align': 'center'
        })
        
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00',
            'align': 'center'
        })
        
        percentage_format = workbook.add_format({
            'num_format': '0.0%',
            'align': 'center'
        })
        
        # Get company info
        company = self.db.query(BaseCompany).first()
        company_name = company.company_name if company else "Apex POB"
        
        # Write headers
        row = 0
        worksheet.write(row, 0, company_name, company_format)
        worksheet.merge_range(row, 0, row, 5, company_name, company_format)
        row += 1
        
        report_name = self._get_report_name(report_code)
        worksheet.write(row, 0, report_name, title_format)
        worksheet.merge_range(row, 0, row, 5, report_name, title_format)
        row += 1
        
        worksheet.write(row, 0, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        row += 2
        
        # Write filters if any
        if filters:
            worksheet.write(row, 0, "Filters Applied:", title_format)
            row += 1
            for key, value in filters.items():
                worksheet.write(row, 0, f"  {key}:")
                worksheet.write(row, 1, str(value))
                row += 1
            row += 1
        
        # Write summary if any
        if result.get('summary'):
            worksheet.write(row, 0, "Summary:", title_format)
            row += 1
            for key, value in result['summary'].items():
                worksheet.write(row, 0, f"  {key.replace('_', ' ').title()}:")
                worksheet.write(row, 1, str(value))
                row += 1
            row += 1
        
        # Write data table
        columns = result.get('columns', [])
        rows = result.get('rows', [])
        
        if rows and columns:
            # Write column headers
            for col_idx, col in enumerate(columns):
                worksheet.write(row, col_idx, col['label'], header_format)
                # Set column width based on type
                if col.get('type') in ['datetime', 'date']:
                    worksheet.set_column(col_idx, col_idx, 20)
                elif col.get('type') == 'text':
                    worksheet.set_column(col_idx, col_idx, 15)
                else:
                    worksheet.set_column(col_idx, col_idx, 12)
            row += 1
            
            # Write data rows
            start_row = row
            for data_row in rows:
                for col_idx, col in enumerate(columns):
                    value = data_row.get(col['field'], '')
                    
                    # Format based on type
                    if col.get('type') == 'currency' and isinstance(value, (int, float, Decimal)):
                        worksheet.write(row, col_idx, float(value), currency_format)
                    elif col.get('type') == 'percentage' and isinstance(value, (int, float, Decimal)):
                        worksheet.write(row, col_idx, float(value) / 100, percentage_format)
                    elif col.get('type') == 'datetime' and value:
                        if isinstance(value, str):
                            worksheet.write(row, col_idx, value)
                        else:
                            worksheet.write(row, col_idx, value, date_format)
                    elif col.get('type') == 'date' and value:
                        if isinstance(value, str):
                            worksheet.write(row, col_idx, value)
                        else:
                            worksheet.write(row, col_idx, value, date_format)
                    elif col.get('type') == 'boolean':
                        worksheet.write(row, col_idx, 'Yes' if value else 'No')
                    else:
                        worksheet.write(row, col_idx, str(value))
                
                row += 1
            
            # Add borders to data range
            border_format = workbook.add_format({'border': 1})
            worksheet.conditional_format(
                start_row, 0, row - 1, len(columns) - 1,
                {'type': 'no_errors', 'format': border_format}
            )
            
            # Add alternating row colors
            for r in range(start_row, row):
                if (r - start_row) % 2 == 0:
                    for c in range(len(columns)):
                        worksheet.set_row(r, None, None, {'bg_color': '#F2F2F2'})
        
        # Close workbook
        workbook.close()
        
        # Save to file
        output.seek(0)
        with open(file_path, 'wb') as f:
            f.write(output.getvalue())
        
        return str(file_path)
    
    def _generate_csv(self, result: Dict[str, Any], report_code: str, filters: Dict[str, Any]) -> str:
        """Generate CSV report"""
        # Generate unique filename
        filename = f"report_{report_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = self.export_dir / filename
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header info
            company = self.db.query(BaseCompany).first()
            company_name = company.company_name if company else "Apex POB"
            report_name = self._get_report_name(report_code)
            
            writer.writerow([f"{company_name} - {report_name}"])
            writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            writer.writerow([])
            
            # Write filters if any
            if filters:
                writer.writerow(["Filters Applied:"])
                for key, value in filters.items():
                    writer.writerow([f"{key}: {value}"])
                writer.writerow([])
            
            # Write summary if any
            if result.get('summary'):
                writer.writerow(["Summary:"])
                for key, value in result['summary'].items():
                    writer.writerow([f"{key.replace('_', ' ').title()}: {value}"])
                writer.writerow([])
            
            # Write data table
            columns = result.get('columns', [])
            rows = result.get('rows', [])
            
            if rows and columns:
                # Write headers
                writer.writerow([col['label'] for col in columns])
                
                # Write data rows
                for data_row in rows:
                    csv_row = []
                    for col in columns:
                        value = data_row.get(col['field'], '')
                        
                        # Format based on type
                        if col.get('type') == 'currency' and isinstance(value, (int, float, Decimal)):
                            csv_row.append(f"${value:,.2f}")
                        elif col.get('type') == 'percentage' and isinstance(value, (int, float, Decimal)):
                            csv_row.append(f"{value:.1f}%")
                        elif col.get('type') in ['datetime', 'date'] and value:
                            if isinstance(value, str):
                                csv_row.append(value)
                            else:
                                csv_row.append(value.strftime('%Y-%m-%d %H:%M') if col.get('type') == 'datetime' else value.strftime('%Y-%m-%d'))
                        elif col.get('type') == 'boolean':
                            csv_row.append('Yes' if value else 'No')
                        else:
                            csv_row.append(str(value))
                    
                    writer.writerow(csv_row)
        
        return str(file_path)
    
    def _get_report_name(self, report_code: str) -> str:
        """Get readable report name from code"""
        report_names = {
            'personnel.employee_list': 'Employee List',
            'personnel.dept_summary': 'Department Summary',
            'personnel.birthday': 'Birthday List',
            'att.daily': 'Daily Attendance',
            'att.monthly': 'Monthly Attendance Summary',
            'att.late': 'Late Arrival Report',
            'muster.event': 'Mustering Event Report',
            'muster.compliance': 'Mustering Compliance Matrix',
            'emergency.events': 'Emergency Event Log',
            'pay.salary_summary': 'Salary Summary',
            'pay.zone_cost': 'Zone Cost Report',
            'visitor.daily_log': 'Daily Visitor Log',
            'visitor.overstay': 'Visitor Overstay Report',
            'mtd.compliance_matrix': 'MTD Compliance Matrix',
            'system.operation_log': 'System Operation Log',
        }
        
        return report_names.get(report_code, report_code.replace('.', ' ').title())


# Celery tasks for async processing (only registered when celery is available)

def _celery_task(func):
    if _CELERY_AVAILABLE and celery_app is not None:
        return celery_app.task(bind=True)(func)
    return func

@_celery_task
def export_report_task(self, export_id: int, report_code: str, filters: Dict[str, Any], format: str):
    """Async export report task"""
    try:
        db = next(get_db())
        export_service = ExportService(db)
        file_path = export_service.generate_export(export_id, report_code, filters, format)
        db.close()
        
        return {
            'status': 'completed',
            'export_id': export_id,
            'file_path': file_path
        }
        
    except Exception as e:
        logger.error(f"Export task failed: {str(e)}")
        return {
            'status': 'failed',
            'export_id': export_id,
            'error': str(e)
        }


@_celery_task
def scheduled_export_task(self, schedule_id: int):
    """Async scheduled export task"""
    try:
        db = next(get_db())
        
        # Get schedule details
        schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        # Get template
        template = db.query(ReportTemplate).filter(ReportTemplate.id == schedule.template_id).first()
        if not template:
            raise ValueError(f"Template {schedule.template_id} not found")
        
        # Create export log
        export_log = ReportExportLog(
            template_id=template.id,
            user_id=schedule.created_by,
            format=schedule.format,
            filters=template.filters or {},
            status='pending'
        )
        
        db.add(export_log)
        db.commit()
        db.refresh(export_log)
        
        # Generate export
        export_service = ExportService(db)
        file_path = export_service.generate_export(export_log.id, template.report_code, template.filters or {}, schedule.format)
        
        # Send email to recipients
        if schedule.recipients:
            export_service.email_service.send_report_email(
                schedule.recipients,
                template.template_name,
                file_path,
                schedule.format
            )
        
        # Update schedule
        schedule.last_run = datetime.utcnow()
        # Calculate next run time (simplified - would use croniter library)
        schedule.next_run = datetime.utcnow() + timedelta(days=1)  # Daily for now
        db.commit()
        
        db.close()
        
        return {
            'status': 'completed',
            'schedule_id': schedule_id,
            'export_id': export_log.id,
            'file_path': file_path
        }
        
    except Exception as e:
        logger.error(f"Scheduled export task failed: {str(e)}")
        return {
            'status': 'failed',
            'schedule_id': schedule_id,
            'error': str(e)
        }
