"""
Report Module Models
BioTime 9.5 compatible with POB extensions
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from ..core.database import Base


class ReportTemplate(Base):
    """Report templates and configurations"""
    __tablename__ = 'rpt_template'
    
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False)  # attendance, mustering, emergency, etc.
    report_code = Column(String(100), nullable=False)  # att.monthly, muster.event
    filters = Column(JSONB)  # default filters
    columns = Column(JSONB)  # [{field:"emp_name", label:"Name", show:true, width:120}]
    group_by = Column(String(50))
    chart_type = Column(String(20), default='none')  # bar, line, pie, heatmap, none
    is_system = Column(Boolean, default=False)  # cannot delete system templates
    created_by = Column(Integer, ForeignKey('auth_user.id'))
    is_public = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("AuthUser", foreign_keys=[created_by])
    schedules = relationship("ReportSchedule", back_populates="template")
    exports = relationship("ReportExportLog", back_populates="template")
    favorites = relationship("ReportFavorite", back_populates="template")
    presets = relationship("ReportUserPreset", back_populates="template")
    
    # Indexes
    __table_args__ = (
        Index('idx_rpt_template_module_code', 'module', 'report_code'),
        Index('idx_rpt_template_created_by', 'created_by'),
        Index('idx_rpt_template_is_public', 'is_public'),
    )


class ReportSchedule(Base):
    """Report scheduling and automation"""
    __tablename__ = 'rpt_schedule'
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('rpt_template.id'), nullable=False)
    schedule_name = Column(String(100), nullable=False)
    cron = Column(String(50), nullable=False)  # "0 8 * * 1" = Monday 8am
    format = Column(String(10), default='pdf')  # pdf, xlsx, csv
    recipients = Column(JSONB)  # {users:[1,2], emails:["a@b.com"], roles:[3]}
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    is_active = Column(Boolean, default=True)
    # Outcome of the last run (rpt_schedule runner in mustering_celery_tasks)
    report_code = Column(String(100))
    last_status = Column(String(20))       # ok | emailed | email_failed | failed
    last_error = Column(Text)
    last_file_path = Column(String(500))
    last_rows = Column(Integer)
    created_by = Column(Integer, ForeignKey('auth_user.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="schedules")
    creator = relationship("AuthUser", foreign_keys=[created_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_rpt_schedule_next_run_active', 'next_run', 'is_active'),
        Index('idx_rpt_schedule_template_id', 'template_id'),
    )


class ReportExportLog(Base):
    """Report export history and audit trail"""
    __tablename__ = 'rpt_export_log'
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('rpt_template.id'))
    user_id = Column(Integer, ForeignKey('auth_user.id'))
    export_time = Column(DateTime, default=datetime.utcnow)
    format = Column(String(10))  # pdf, xlsx, csv
    filters = Column(JSONB)  # filters used for export
    row_count = Column(Integer)
    file_path = Column(String(255))  # path to exported file
    file_size = Column(Integer)  # bytes
    ip_address = Column(String(45))
    status = Column(String(20), default='completed')  # completed, failed, pending
    error_message = Column(Text)
    task_id = Column(String(100))  # Celery task ID for async exports
    
    # Relationships
    template = relationship("ReportTemplate", back_populates="exports")
    user = relationship("AuthUser", foreign_keys=[user_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_rpt_export_log_export_time', 'export_time'),
        Index('idx_rpt_export_log_user_id', 'user_id'),
        Index('idx_rpt_export_log_template_id', 'template_id'),
    )


class ReportUserPreset(Base):
    """User-specific filter and column presets"""
    __tablename__ = 'rpt_user_preset'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('auth_user.id'), nullable=False)
    template_id = Column(Integer, ForeignKey('rpt_template.id'))
    preset_name = Column(String(100), nullable=False)
    preset_type = Column(String(20), nullable=False)  # filter, column, both
    filters = Column(JSONB)
    columns = Column(JSONB)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("AuthUser", foreign_keys=[user_id])
    template = relationship("ReportTemplate", back_populates="presets")
    
    # Indexes
    __table_args__ = (
        Index('idx_rpt_user_preset_user_id', 'user_id'),
        Index('idx_rpt_user_preset_template_id', 'template_id'),
    )


class ReportFavorite(Base):
    """User favorite reports"""
    __tablename__ = 'rpt_favorite'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('auth_user.id'), nullable=False)
    template_id = Column(Integer, ForeignKey('rpt_template.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("AuthUser", foreign_keys=[user_id])
    template = relationship("ReportTemplate", back_populates="favorites")
    
    # Indexes
    __table_args__ = (
        Index('idx_rpt_favorite_user_id', 'user_id'),
        Index('idx_rpt_favorite_template_id', 'template_id'),
        Index('idx_rpt_favorite_user_template', 'user_id', 'template_id', unique=True),
    )
