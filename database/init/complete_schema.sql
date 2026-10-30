--
-- PostgreSQL database dump
--

\restrict 8sJI45dH4qooY6FT7uA37453EhKUo2n9tN01iotzWdjYJSMq8eRDNbNat367Mv5

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: appraisalstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appraisalstatus AS ENUM (
    'DRAFT',
    'SUBMITTED',
    'IN_PROGRESS',
    'COMPLETED',
    'APPROVED',
    'REJECTED'
);


--
-- Name: assignmentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.assignmentstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'MAINTENANCE',
    'ERROR'
);


--
-- Name: attributetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.attributetype AS ENUM (
    'TEXT',
    'NUMBER',
    'DATE',
    'BOOLEAN',
    'SELECT',
    'MULTI_SELECT',
    'FILE',
    'EMAIL',
    'PHONE',
    'URL'
);


--
-- Name: benefiteligibility; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.benefiteligibility AS ENUM (
    'ALL_EMPLOYEES',
    'FULL_TIME_ONLY',
    'PART_TIME_ONLY',
    'PER_DEPARTMENT',
    'PER_POSITION',
    'TENURE_BASED',
    'SALARY_BASED'
);


--
-- Name: benefittype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.benefittype AS ENUM (
    'HEALTH_INSURANCE',
    'DENTAL_INSURANCE',
    'VISION_INSURANCE',
    'LIFE_INSURANCE',
    'RETIREMENT_401K',
    'RETIREMENT_PENSION',
    'PAID_TIME_OFF',
    'SICK_LEAVE',
    'MATERNITY_LEAVE',
    'PATERNITY_LEAVE',
    'DISABILITY_INSURANCE',
    'TUITION_REIMBURSEMENT',
    'GYM_MEMBERSHIP',
    'TRANSPORTATION',
    'HOUSING_ALLOWANCE',
    'MEAL_ALLOWANCE',
    'OTHER'
);


--
-- Name: certificationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.certificationstatus AS ENUM (
    'ACTIVE',
    'EXPIRED',
    'SUSPENDED',
    'REVOKED'
);


--
-- Name: certificationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.certificationtype AS ENUM (
    'OPITO',
    'NOPSEMA',
    'COMPANY',
    'OTHER'
);


--
-- Name: companytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.companytype AS ENUM (
    'HOLDING',
    'SUBSIDIARY',
    'BRANCH'
);


--
-- Name: compliancestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.compliancestatus AS ENUM (
    'COMPLIANT',
    'PENDING_REVIEW',
    'NON_COMPLIANT',
    'EXPIRED',
    'SUSPENDED'
);


--
-- Name: contractstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contractstatus AS ENUM (
    'DRAFT',
    'ACTIVE',
    'EXPIRED',
    'TERMINATED',
    'SUSPENDED',
    'RENEWED'
);


--
-- Name: contracttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contracttype AS ENUM (
    'PERMANENT',
    'FIXED_TERM',
    'CONTRACTOR',
    'INTERN',
    'APPRENTICE',
    'TEMPORARY'
);


--
-- Name: departmentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.departmentstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'TEMPORARY',
    'UNDER_REVIEW'
);


--
-- Name: departmenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.departmenttype AS ENUM (
    'OPERATIONS',
    'MAINTENANCE',
    'SAFETY',
    'SECURITY',
    'ADMINISTRATION',
    'LOGISTICS',
    'TECHNICAL',
    'MEDICAL',
    'TRAINING',
    'CONTRACTOR',
    'MANAGEMENT',
    'SUPPORT'
);


--
-- Name: devicestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.devicestatus AS ENUM (
    'ONLINE',
    'OFFLINE',
    'MAINTENANCE',
    'ERROR',
    'DISCONNECTED'
);


--
-- Name: devicetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.devicetype AS ENUM (
    'BIOMETRIC_READER',
    'CARD_READER',
    'TURNSTILE',
    'DOOR_CONTROLLER',
    'GATE_CONTROLLER'
);


--
-- Name: disciplinaryactiontype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.disciplinaryactiontype AS ENUM (
    'VERBAL_WARNING',
    'WRITTEN_WARNING',
    'FINAL_WARNING',
    'SUSPENSION',
    'DEMOTION',
    'TERMINATION',
    'OTHER'
);


--
-- Name: disciplinarystatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.disciplinarystatus AS ENUM (
    'OPEN',
    'UNDER_INVESTIGATION',
    'HEARING_SCHEDULED',
    'CLOSED',
    'APPEALED',
    'RESOLVED'
);


--
-- Name: leavestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.leavestatus AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'CANCELLED',
    'ON_LEAVE',
    'COMPLETED'
);


--
-- Name: leavetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.leavetype AS ENUM (
    'ANNUAL',
    'SICK',
    'MATERNITY',
    'PATERNITY',
    'UNPAID',
    'COMPASSIONATE',
    'STUDY',
    'MILITARY',
    'JURY_DUTY',
    'FAMILY_CARE',
    'PERSONAL',
    'OTHER'
);


--
-- Name: licensetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.licensetype AS ENUM (
    'TRIAL',
    'STANDARD',
    'ENTERPRISE'
);


--
-- Name: onboardingstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.onboardingstatus AS ENUM (
    'NOT_STARTED',
    'IN_PROGRESS',
    'PENDING_REVIEW',
    'APPROVED',
    'REJECTED',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: onboardingtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.onboardingtype AS ENUM (
    'NEW_HIRE',
    'REHIRE',
    'INTERNAL_TRANSFER',
    'PROMOTION',
    'CONTRACT_RENEWAL'
);


--
-- Name: overtimecompensation; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.overtimecompensation AS ENUM (
    'PAY',
    'TIME_OFF',
    'MIXED'
);


--
-- Name: overtimestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.overtimestatus AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'CANCELLED',
    'PROCESSED'
);


--
-- Name: overtimetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.overtimetype AS ENUM (
    'DAILY',
    'WEEKLY',
    'MONTHLY',
    'HOLIDAY',
    'WEEKEND',
    'SPECIAL'
);


--
-- Name: paycalcstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paycalcstatus AS ENUM (
    'PENDING',
    'CALCULATED',
    'VERIFIED',
    'APPROVED'
);


--
-- Name: paycalctype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paycalctype AS ENUM (
    'FIXED',
    'FORMULA',
    'ATTENDANCE'
);


--
-- Name: payitemtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payitemtype AS ENUM (
    'EARNING',
    'DEDUCTION',
    'ATTENDANCE'
);


--
-- Name: payloanstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payloanstatus AS ENUM (
    'PENDING',
    'ACTIVE',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: payperiodstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payperiodstatus AS ENUM (
    'OPEN',
    'CALCULATING',
    'CLOSED',
    'CANCELLED'
);


--
-- Name: paystructuretype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paystructuretype AS ENUM (
    'MONTHLY',
    'DAILY',
    'HOURLY'
);


--
-- Name: performancerating; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.performancerating AS ENUM (
    'EXCELLENT',
    'VERY_GOOD',
    'GOOD',
    'SATISFACTORY',
    'NEEDS_IMPROVEMENT',
    'POOR'
);


--
-- Name: personnelstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.personnelstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'ON_LEAVE',
    'TRANSIT',
    'OFFSHORE',
    'ONSHORE'
);


--
-- Name: resignationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.resignationstatus AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'PROCESSING',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: resignationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.resignationtype AS ENUM (
    'VOLUNTARY',
    'RETIREMENT',
    'TERMINATION',
    'CONTRACT_END'
);


--
-- Name: shifttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.shifttype AS ENUM (
    'MORNING',
    'EVENING',
    'NIGHT',
    'CUSTOM',
    'ROTATING'
);


--
-- Name: ssotype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ssotype AS ENUM (
    'LDAP',
    'SAML'
);


--
-- Name: taskpriority; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.taskpriority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);


--
-- Name: tasktype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tasktype AS ENUM (
    'DOCUMENT_UPLOAD',
    'TRAINING',
    'REVIEW',
    'APPROVAL',
    'BACKGROUND_CHECK',
    'MEDICAL_CHECK',
    'ASSET_RETURN',
    'SYSTEM_ACCESS'
);


--
-- Name: trainingcategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.trainingcategory AS ENUM (
    'SAFETY',
    'TECHNICAL',
    'COMPLIANCE',
    'SOFT_SKILLS',
    'LEADERSHIP',
    'INDUCTION',
    'REFRESHER',
    'CERTIFICATION'
);


--
-- Name: trainingstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.trainingstatus AS ENUM (
    'ENROLLED',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'CANCELLED',
    'CERTIFIED'
);


--
-- Name: transferstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transferstatus AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: transfertype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transfertype AS ENUM (
    'DEPARTMENT',
    'LOCATION',
    'POSITION',
    'ROLE'
);


--
-- Name: validationrule; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.validationrule AS ENUM (
    'REQUIRED',
    'OPTIONAL',
    'MIN_LENGTH',
    'MAX_LENGTH',
    'MIN_VALUE',
    'MAX_VALUE',
    'EMAIL_FORMAT',
    'PHONE_FORMAT',
    'REGEX_PATTERN'
);


--
-- Name: vendorstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.vendorstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED',
    'UNDER_REVIEW',
    'BLACKLISTED'
);


--
-- Name: vendortype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.vendortype AS ENUM (
    'SERVICE_PROVIDER',
    'EQUIPMENT_SUPPLIER',
    'CONSULTING_FIRM',
    'STAFFING_AGENCY',
    'TRAINING_PROVIDER',
    'SOFTWARE_VENDOR',
    'MAINTENANCE_PROVIDER'
);


--
-- Name: zonestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.zonestatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'MAINTENANCE',
    'EMERGENCY',
    'LOCKDOWN'
);


--
-- Name: zonetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.zonetype AS ENUM (
    'RESTRICTED',
    'PUBLIC',
    'SAFE_HAVEN',
    'WORK_AREA',
    'ACCOMMODATION',
    'HELIPAD',
    'CONTROL_ROOM',
    'STORAGE',
    'EMERGENCY'
);


--
-- Name: calculate_attendance(character varying, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_attendance(emp_code_param character varying, date_param date) RETURNS TABLE(check_in_time timestamp with time zone, check_out_time timestamp with time zone, work_hours double precision, late_minutes integer, early_departure integer, status character varying)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        MIN(punch_time) as check_in_time,
                        MAX(punch_time) as check_out_time,
                        EXTRACT(EPOCH FROM (MAX(punch_time) - MIN(punch_time)))/3600 as work_hours,
                        0 as late_minutes,
                        0 as early_departure,
                        'PRESENT' as status
                    FROM iclock_transaction
                    WHERE emp_code = emp_code_param
                    AND DATE(punch_time) = date_param
                    GROUP BY DATE(punch_time);
                END;
                $$;


--
-- Name: calculate_early_departure(timestamp without time zone, time without time zone, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_early_departure(check_out_time timestamp without time zone, shift_end_time time without time zone, grace_minutes integer DEFAULT 0) RETURNS integer
    LANGUAGE plpgsql
    AS $$
                DECLARE
                    early_mins INTEGER;
                BEGIN
                    IF check_out_time IS NULL OR shift_end_time IS NULL THEN
                        RETURN 0;
                    END IF;
                    
                    early_mins := EXTRACT(EPOCH FROM (shift_end_time - check_out_time::time))/60;
                    
                    IF early_mins > grace_minutes THEN
                        RETURN early_mins;
                    ELSE
                        RETURN 0;
                    END IF;
                END;
                $$;


--
-- Name: calculate_late_arrival(timestamp without time zone, time without time zone, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_late_arrival(check_in_time timestamp without time zone, shift_start_time time without time zone, grace_minutes integer DEFAULT 0) RETURNS integer
    LANGUAGE plpgsql
    AS $$
                DECLARE
                    late_mins INTEGER;
                BEGIN
                    IF check_in_time IS NULL OR shift_start_time IS NULL THEN
                        RETURN 0;
                    END IF;
                    
                    late_mins := EXTRACT(EPOCH FROM (check_in_time::time - shift_start_time))/60;
                    
                    IF late_mins > grace_minutes THEN
                        RETURN late_mins;
                    ELSE
                        RETURN 0;
                    END IF;
                END;
                $$;


--
-- Name: calculate_overtime(character varying, date, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_overtime(emp_code_param character varying, date_param date, shift_id integer) RETURNS TABLE(daily_overtime double precision, daily_overtime_minutes integer, overtime_rate double precision)
    LANGUAGE plpgsql
    AS $$
                DECLARE
                    work_hours FLOAT;
                    shift_hours FLOAT;
                    overtime FLOAT;
                BEGIN
                    -- Get actual work hours
                    SELECT EXTRACT(EPOCH FROM (MAX(punch_time) - MIN(punch_time)))/3600 INTO work_hours
                    FROM iclock_transaction
                    WHERE emp_code = emp_code_param
                    AND DATE(punch_time) = date_param;
                    
                    -- Get shift hours
                    SELECT EXTRACT(EPOCH FROM (end_time - start_time))/3600 INTO shift_hours
                    FROM att_timetable t
                    JOIN att_shift s ON t.id = s.timetable_id
                    WHERE s.id = shift_id;
                    
                    -- Calculate overtime
                    IF work_hours > shift_hours THEN
                        overtime := work_hours - shift_hours;
                    ELSE
                        overtime := 0;
                    END IF;
                    
                    RETURN QUERY
                    SELECT 
                        overtime as daily_overtime,
                        ROUND(overtime * 60) as daily_overtime_minutes,
                        1.5 as overtime_rate;
                END;
                $$;


--
-- Name: get_attendance_summary(character varying, date, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_attendance_summary(emp_code_param character varying, start_date date, end_date date) RETURNS TABLE(date date, check_in_time timestamp with time zone, check_out_time timestamp with time zone, work_hours double precision, late_minutes integer, early_departure integer, status character varying, is_holiday boolean)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        DATE(t.punch_time) as date,
                        MIN(t.punch_time) as check_in_time,
                        MAX(t.punch_time) as check_out_time,
                        EXTRACT(EPOCH FROM (MAX(t.punch_time) - MIN(t.punch_time)))/3600 as work_hours,
                        0 as late_minutes,
                        0 as early_departure,
                        'PRESENT' as status,
                        is_holiday(DATE(t.punch_time)) as is_holiday
                    FROM iclock_transaction t
                    WHERE t.emp_code = emp_code_param
                    AND DATE(t.punch_time) BETWEEN start_date AND end_date
                    GROUP BY DATE(t.punch_time)
                    ORDER BY DATE(t.punch_time);
                END;
                $$;


--
-- Name: get_device_statistics(character varying, date, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_device_statistics(device_sn_param character varying, start_date date, end_date date) RETURNS TABLE(total_transactions bigint, unique_employees integer, first_transaction timestamp with time zone, last_transaction timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        COUNT(*) as total_transactions,
                        COUNT(DISTINCT emp_code) as unique_employees,
                        MIN(punch_time) as first_transaction,
                        MAX(punch_time) as last_transaction
                    FROM iclock_transaction
                    WHERE terminal_sn = device_sn_param
                    AND DATE(punch_time) BETWEEN start_date AND end_date;
                END;
                $$;


--
-- Name: get_employee_shift(character varying, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_employee_shift(emp_code_param character varying, date_param date) RETURNS TABLE(shift_id integer, shift_name character varying, timetable_id integer, start_time time without time zone, end_time time without time zone)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        s.id as shift_id,
                        s.name as shift_name,
                        s.timetable_id,
                        t.start_time,
                        t.end_time
                    FROM att_schedule sch
                    JOIN att_shift s ON sch.shift_id = s.id
                    JOIN att_timetable t ON s.timetable_id = t.id
                    WHERE sch.emp_code = emp_code_param
                    AND date_param >= sch.start_date
                    AND (sch.end_date IS NULL OR date_param <= sch.end_date);
                END;
                $$;


--
-- Name: is_holiday(date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.is_holiday(date_param date) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
                DECLARE
                    holiday_count INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO holiday_count
                    FROM holiday
                    WHERE is_active = TRUE
                    AND (
                        holiday_date = date_param
                        OR (is_repeatable = TRUE AND repeat_month = EXTRACT(MONTH FROM date_param) AND repeat_day = EXTRACT(DAY FROM date_param))
                    );
                    
                    RETURN holiday_count > 0;
                END;
                $$;


--
-- Name: process_attendance_records(date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.process_attendance_records(date_param date) RETURNS integer
    LANGUAGE plpgsql
    AS $$
                DECLARE
                    processed_count INTEGER;
                BEGIN
                    -- Mark checkinout records as processed
                    UPDATE checkinout
                    SET processed = TRUE
                    WHERE DATE(check_time) = date_param
                    AND processed = FALSE;
                    
                    GET DIAGNOSTICS processed_count = ROW_COUNT;
                    
                    RETURN processed_count;
                END;
                $$;


--
-- Name: sync_personnel_to_employee(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sync_personnel_to_employee() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    DELETE FROM personnel_employee WHERE emp_code = OLD.emp_code;
    RETURN OLD;
  END IF;

  INSERT INTO personnel_employee (id, emp_code, first_name, last_name, status, hire_date, card_no, created_at, updated_at)
  VALUES (
    NEW.id,
    NEW.emp_code,
    NEW.first_name,
    NEW.last_name,
    CASE WHEN NEW.status::text IN ('active','ACTIVE','onshore','offshore','transit','on_leave') THEN 0 ELSE 1 END,
    NULL,
    CASE WHEN NEW.card_number IS NOT NULL THEN NEW.card_number::text ELSE NULL END,
    NOW(),
    NOW()
  )
  ON CONFLICT (emp_code) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name  = EXCLUDED.last_name,
    status     = EXCLUDED.status,
    card_no    = EXCLUDED.card_no,
    updated_at = NOW();

  RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acc_antipassback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_antipassback (
    id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    door_id integer NOT NULL,
    last_event_time timestamp with time zone NOT NULL,
    last_event_type smallint NOT NULL,
    last_terminal_sn character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_antipassback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_antipassback_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_antipassback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_antipassback_id_seq OWNED BY public.acc_antipassback.id;


--
-- Name: acc_door; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_door (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    terminal_sn character varying(20),
    acc_level_id integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    mustering_mode boolean DEFAULT false,
    emergency_action smallint DEFAULT 0,
    relay_time integer DEFAULT 5,
    door_sensor_type smallint DEFAULT 0,
    alarm_delay integer DEFAULT 30,
    open_duration integer DEFAULT 15,
    anti_passback smallint DEFAULT 0,
    first_card_open boolean DEFAULT false,
    interlock_group integer DEFAULT 0,
    fire_linkage boolean DEFAULT false
);


--
-- Name: acc_door_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_door_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_door_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_door_id_seq OWNED BY public.acc_door.id;


--
-- Name: acc_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_event (
    id bigint NOT NULL,
    event_time timestamp with time zone NOT NULL,
    terminal_sn character varying(20) NOT NULL,
    door_id integer,
    emp_code character varying(20),
    emp_name character varying(50),
    event_type smallint NOT NULL,
    verify_type smallint,
    in_out smallint,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    photo_url text
);


--
-- Name: acc_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_event_id_seq OWNED BY public.acc_event.id;


--
-- Name: acc_first_card; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_first_card (
    id bigint NOT NULL,
    door_id integer NOT NULL,
    timezone_id integer NOT NULL,
    first_card_time timestamp with time zone NOT NULL,
    emp_code character varying(20) NOT NULL,
    zone_end_time timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_first_card_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_first_card_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_first_card_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_first_card_id_seq OWNED BY public.acc_first_card.id;


--
-- Name: acc_guard_tour; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_guard_tour (
    id integer NOT NULL,
    tour_name character varying(100) NOT NULL,
    description text,
    interval_minutes integer DEFAULT 60,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_guard_tour_checkpoint; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_guard_tour_checkpoint (
    id integer NOT NULL,
    tour_id integer,
    door_id integer,
    sequence_order integer NOT NULL,
    time_window_minutes integer DEFAULT 10,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_guard_tour_checkpoint_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_guard_tour_checkpoint_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_guard_tour_checkpoint_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_guard_tour_checkpoint_id_seq OWNED BY public.acc_guard_tour_checkpoint.id;


--
-- Name: acc_guard_tour_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_guard_tour_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_guard_tour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_guard_tour_id_seq OWNED BY public.acc_guard_tour.id;


--
-- Name: acc_guard_tour_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_guard_tour_log (
    id bigint NOT NULL,
    schedule_id integer,
    checkpoint_id integer,
    emp_code character varying(20),
    scan_time timestamp with time zone NOT NULL,
    is_on_time boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_guard_tour_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_guard_tour_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_guard_tour_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_guard_tour_log_id_seq OWNED BY public.acc_guard_tour_log.id;


--
-- Name: acc_guard_tour_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_guard_tour_schedule (
    id integer NOT NULL,
    tour_id integer,
    guard_emp_code character varying(20),
    guard_name character varying(100),
    scheduled_start timestamp with time zone NOT NULL,
    scheduled_end timestamp with time zone,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_guard_tour_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_guard_tour_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_guard_tour_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_guard_tour_schedule_id_seq OWNED BY public.acc_guard_tour_schedule.id;


--
-- Name: acc_interlock_door; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_interlock_door (
    id integer NOT NULL,
    group_id integer NOT NULL,
    door_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_interlock_door_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_interlock_door_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_interlock_door_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_interlock_door_id_seq OWNED BY public.acc_interlock_door.id;


--
-- Name: acc_interlock_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_interlock_group (
    id integer NOT NULL,
    group_name character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_interlock_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_interlock_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_interlock_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_interlock_group_id_seq OWNED BY public.acc_interlock_group.id;


--
-- Name: acc_level; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_level (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    time_zone character varying(50) DEFAULT 'UTC'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    mustering_only boolean DEFAULT false,
    is_active boolean DEFAULT true
);


--
-- Name: acc_level_door; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_level_door (
    id integer NOT NULL,
    level_id integer NOT NULL,
    door_id integer NOT NULL,
    timezone_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_level_door_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_level_door_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_level_door_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_level_door_id_seq OWNED BY public.acc_level_door.id;


--
-- Name: acc_level_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_level_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_level_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_level_id_seq OWNED BY public.acc_level.id;


--
-- Name: acc_linkage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_linkage (
    id integer NOT NULL,
    terminal_sn character varying(20) NOT NULL,
    input_type smallint,
    output_action smallint,
    output_door_id integer,
    output_terminal_sn character varying(20),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_linkage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_linkage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_linkage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_linkage_id_seq OWNED BY public.acc_linkage.id;


--
-- Name: acc_multi_card; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_multi_card (
    id integer NOT NULL,
    door_id integer,
    min_cards smallint DEFAULT 2 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_multi_card_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_multi_card_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_multi_card_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_multi_card_id_seq OWNED BY public.acc_multi_card.id;


--
-- Name: acc_multi_card_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_multi_card_user (
    id integer NOT NULL,
    multi_card_id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_multi_card_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_multi_card_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_multi_card_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_multi_card_user_id_seq OWNED BY public.acc_multi_card_user.id;


--
-- Name: acc_passback_rule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_passback_rule (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    in_door_id integer,
    out_door_id integer,
    mode smallint,
    is_active boolean,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_passback_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_passback_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_passback_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_passback_rule_id_seq OWNED BY public.acc_passback_rule.id;


--
-- Name: acc_timezone; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_timezone (
    id integer NOT NULL,
    timezone_name character varying(50) NOT NULL,
    sun_time1 character varying(11),
    sun_time2 character varying(11),
    sun_time3 character varying(11),
    mon_time1 character varying(11),
    mon_time2 character varying(11),
    mon_time3 character varying(11),
    tue_time1 character varying(11),
    tue_time2 character varying(11),
    tue_time3 character varying(11),
    wed_time1 character varying(11),
    wed_time2 character varying(11),
    wed_time3 character varying(11),
    thu_time1 character varying(11),
    thu_time2 character varying(11),
    thu_time3 character varying(11),
    fri_time1 character varying(11),
    fri_time2 character varying(11),
    fri_time3 character varying(11),
    sat_time1 character varying(11),
    sat_time2 character varying(11),
    sat_time3 character varying(11),
    hol1_time1 character varying(11),
    hol1_time2 character varying(11),
    hol1_time3 character varying(11),
    hol2_time1 character varying(11),
    hol2_time2 character varying(11),
    hol2_time3 character varying(11),
    hol3_time1 character varying(11),
    hol3_time2 character varying(11),
    hol3_time3 character varying(11),
    emergency_override boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_timezone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_timezone_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_timezone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_timezone_id_seq OWNED BY public.acc_timezone.id;


--
-- Name: acc_userauthorize; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_userauthorize (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    acc_level_id integer,
    start_time time without time zone,
    end_time time without time zone,
    valid_days character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    valid_from date,
    valid_to date
);


--
-- Name: acc_userauthorize_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_userauthorize_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_userauthorize_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_userauthorize_id_seq OWNED BY public.acc_userauthorize.id;


--
-- Name: acc_visitor_access; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_visitor_access (
    id integer NOT NULL,
    visitor_name character varying(100),
    visitor_company character varying(100),
    visitor_phone character varying(20),
    host_emp_code character varying(20),
    host_name character varying(100),
    acc_level_id integer,
    card_number character varying(50),
    valid_from timestamp with time zone NOT NULL,
    valid_to timestamp with time zone NOT NULL,
    purpose text,
    status character varying(20) DEFAULT 'active'::character varying,
    created_by_username character varying(150),
    created_at timestamp with time zone DEFAULT now(),
    emp_code character varying(20),
    note text,
    door_ids jsonb DEFAULT '[]'::jsonb,
    is_revoked boolean DEFAULT false,
    level_id integer
);


--
-- Name: acc_visitor_access_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_visitor_access_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_visitor_access_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_visitor_access_id_seq OWNED BY public.acc_visitor_access.id;


--
-- Name: acc_zone; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_zone (
    id integer NOT NULL,
    zone_name character varying(100) NOT NULL,
    description text,
    is_mustering_zone boolean DEFAULT false,
    capacity integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: acc_zone_door; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acc_zone_door (
    id integer NOT NULL,
    zone_id integer,
    door_id integer,
    direction smallint DEFAULT 0
);


--
-- Name: acc_zone_door_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_zone_door_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_zone_door_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_zone_door_id_seq OWNED BY public.acc_zone_door.id;


--
-- Name: acc_zone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acc_zone_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acc_zone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acc_zone_id_seq OWNED BY public.acc_zone.id;


--
-- Name: access_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.access_logs (
    id integer NOT NULL,
    personnel_id integer,
    device_id character varying(100),
    event_type character varying(50) NOT NULL,
    access_granted boolean NOT NULL,
    access_method character varying(50),
    "timestamp" timestamp with time zone NOT NULL,
    duration integer,
    biometric_data json,
    denial_reason character varying(255),
    error_code character varying(50),
    zone_id integer,
    notes text,
    verification_method character varying(50),
    ip_address character varying(45),
    user_agent character varying(500),
    direction character varying(10),
    CONSTRAINT access_logs_direction_check CHECK (((direction)::text = ANY ((ARRAY['ENTRY'::character varying, 'EXIT'::character varying])::text[])))
);


--
-- Name: access_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.access_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: access_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.access_logs_id_seq OWNED BY public.access_logs.id;


--
-- Name: acgroup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acgroup (
    id integer NOT NULL,
    group_name character varying(50) NOT NULL,
    description text,
    parent_id integer,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: acgroup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acgroup_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acgroup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acgroup_id_seq OWNED BY public.acgroup.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: appraisal_cycles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appraisal_cycles (
    id integer NOT NULL,
    cycle_name character varying(100) NOT NULL,
    cycle_code character varying(20) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status character varying(20) DEFAULT 'draft'::character varying,
    description text,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: appraisal_cycles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.appraisal_cycles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appraisal_cycles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.appraisal_cycles_id_seq OWNED BY public.appraisal_cycles.id;


--
-- Name: att_exception; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_exception (
    id integer NOT NULL,
    emp_id integer,
    att_date date NOT NULL,
    exception_type character varying(50) NOT NULL,
    deviation_minutes integer DEFAULT 0,
    exception_note text,
    department_id integer,
    handled_at timestamp with time zone,
    handle_action character varying(50),
    handle_note text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: att_exception_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_exception_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_exception_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_exception_id_seq OWNED BY public.att_exception.id;


--
-- Name: att_holiday; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_holiday (
    id integer NOT NULL,
    holiday_name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    holiday_type smallint DEFAULT 0,
    description text,
    area_id integer,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: att_holiday_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_holiday_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_holiday_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_holiday_id_seq OWNED BY public.att_holiday.id;


--
-- Name: att_leave; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_leave (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    leave_type_id integer,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    reason text,
    apply_time timestamp with time zone DEFAULT now(),
    approval_status smallint DEFAULT 0,
    approver_id integer,
    approved_at timestamp with time zone,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: att_leave_old; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_leave_old (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    leave_type character varying(20) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    days_count double precision DEFAULT 0,
    status smallint DEFAULT 0,
    approved_by character varying(20),
    approved_time timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: att_leave_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_leave_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_leave_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_leave_id_seq OWNED BY public.att_leave_old.id;


--
-- Name: att_leave_id_seq1; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_leave_id_seq1
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_leave_id_seq1; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_leave_id_seq1 OWNED BY public.att_leave.id;


--
-- Name: att_leave_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_leave_type (
    id integer NOT NULL,
    leave_name character varying(100) NOT NULL,
    unit smallint DEFAULT 0,
    accrual_rule text,
    affects_mustering boolean DEFAULT true,
    max_days_per_year numeric(6,2),
    requires_approval boolean DEFAULT true,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true
);


--
-- Name: att_leave_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_leave_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_leave_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_leave_type_id_seq OWNED BY public.att_leave_type.id;


--
-- Name: att_manual_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_manual_log (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    punch_time timestamp with time zone NOT NULL,
    punch_state smallint DEFAULT 0,
    reason text,
    attachment character varying(255),
    apply_time timestamp with time zone DEFAULT now(),
    approval_status smallint DEFAULT 0,
    approver_id integer,
    approved_at timestamp with time zone,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: att_manual_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_manual_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_manual_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_manual_log_id_seq OWNED BY public.att_manual_log.id;


--
-- Name: att_overtime; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_overtime (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    ot_date date NOT NULL,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    minutes integer DEFAULT 0 NOT NULL,
    reason text,
    apply_time timestamp with time zone DEFAULT now(),
    approval_status smallint DEFAULT 0,
    approver_id integer,
    approved_at timestamp with time zone,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    overtime_type character varying(20) DEFAULT 'daily'::character varying,
    hours_worked numeric(5,2),
    overtime_hours numeric(5,2),
    compensation_type character varying(20),
    rejection_reason text
);


--
-- Name: att_overtime_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_overtime_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_overtime_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_overtime_id_seq OWNED BY public.att_overtime.id;


--
-- Name: att_overtime_rule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_overtime_rule (
    id integer NOT NULL,
    rule_name character varying(100) NOT NULL,
    ot_type smallint DEFAULT 0,
    min_minutes integer DEFAULT 30,
    rate numeric(4,2) DEFAULT 1.5,
    area_id integer,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true
);


--
-- Name: att_overtime_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_overtime_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_overtime_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_overtime_rule_id_seq OWNED BY public.att_overtime_rule.id;


--
-- Name: att_report; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_report (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    att_date date NOT NULL,
    shift_id integer,
    timetable_id integer,
    check_in timestamp with time zone,
    check_out timestamp with time zone,
    work_hours numeric(6,2) DEFAULT 0,
    work_minutes integer DEFAULT 0,
    late_minutes integer DEFAULT 0,
    early_minutes integer DEFAULT 0,
    ot_minutes integer DEFAULT 0,
    att_status smallint DEFAULT 0,
    exception_count integer DEFAULT 0,
    area_compliance boolean DEFAULT true,
    department_id integer,
    scheduled_minutes integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    overtime_minutes integer DEFAULT 0
);


--
-- Name: att_report_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_report_id_seq OWNED BY public.att_report.id;


--
-- Name: att_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_rules (
    rule_key character varying(100) NOT NULL,
    rule_value text,
    updated_by integer,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: att_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_schedule (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    shift_id integer,
    start_date date NOT NULL,
    end_date date,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    status character varying(20) DEFAULT 'scheduled'::character varying,
    notes text
);


--
-- Name: att_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_schedule_id_seq OWNED BY public.att_schedule.id;


--
-- Name: att_shift; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_shift (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    timetable_id integer,
    days_of_week character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    alias character varying(100),
    work_days character varying(20) DEFAULT '12345'::character varying,
    cycle_unit smallint DEFAULT 1,
    cycle_count smallint DEFAULT 1,
    roster_type smallint DEFAULT 0,
    created_by integer,
    shift_code character varying(20),
    shift_type character varying(20) DEFAULT 'CUSTOM'::character varying,
    start_time time without time zone,
    end_time time without time zone,
    break_duration integer DEFAULT 0,
    working_hours integer DEFAULT 8,
    is_night_shift boolean DEFAULT false,
    is_weekend_shift boolean DEFAULT false,
    is_flexible boolean DEFAULT false,
    rotation_pattern jsonb,
    rotation_cycle_days integer,
    grace_period_minutes integer DEFAULT 15,
    max_late_minutes integer DEFAULT 60,
    max_early_departure_minutes integer DEFAULT 30,
    overtime_threshold_minutes integer DEFAULT 30,
    description text,
    is_active boolean DEFAULT true
);


--
-- Name: att_shift_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_shift_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_shift_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_shift_id_seq OWNED BY public.att_shift.id;


--
-- Name: att_shift_timetable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_shift_timetable (
    id integer NOT NULL,
    shift_id integer NOT NULL,
    day_of_week smallint NOT NULL,
    timetable_id integer NOT NULL
);


--
-- Name: att_shift_timetable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_shift_timetable_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_shift_timetable_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_shift_timetable_id_seq OWNED BY public.att_shift_timetable.id;


--
-- Name: att_timetable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.att_timetable (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    late_grace_minutes integer DEFAULT 0,
    early_exit_minutes integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    alias character varying(100),
    work_day numeric(4,2) DEFAULT 1.0,
    color character varying(20) DEFAULT '#1890ff'::character varying,
    break_time_start time without time zone,
    break_time_end time without time zone,
    must_checkin boolean DEFAULT true,
    must_checkout boolean DEFAULT true,
    area_id integer,
    created_by integer,
    updated_by integer,
    is_active boolean DEFAULT true
);


--
-- Name: att_timetable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.att_timetable_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: att_timetable_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.att_timetable_id_seq OWNED BY public.att_timetable.id;


--
-- Name: attendance_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attendance_logs (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    device_id character varying(50),
    event_type character varying(20) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    verification_method character varying(50),
    verification_score double precision,
    device_type character varying(50),
    network_type character varying(20),
    raw_data jsonb,
    is_processed boolean DEFAULT false,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: attendance_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attendance_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attendance_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attendance_logs_id_seq OWNED BY public.attendance_logs.id;


--
-- Name: attribute_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribute_templates (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    template_code character varying(50) NOT NULL,
    description text,
    attributes json NOT NULL,
    category character varying(50),
    is_system_template boolean,
    is_active boolean,
    usage_count integer,
    last_used timestamp with time zone,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: attribute_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attribute_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attribute_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attribute_templates_id_seq OWNED BY public.attribute_templates.id;


--
-- Name: attribute_validations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attribute_validations (
    id integer NOT NULL,
    attribute_value_id integer NOT NULL,
    validation_rule public.validationrule NOT NULL,
    validation_parameters json,
    is_valid boolean,
    error_message text,
    validated_at timestamp with time zone DEFAULT now()
);


--
-- Name: attribute_validations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attribute_validations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attribute_validations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attribute_validations_id_seq OWNED BY public.attribute_validations.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    codename character varying(50) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_permission_id_seq OWNED BY public.auth_permission.id;


--
-- Name: auth_role; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_role (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: auth_role_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_role_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_role_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_role_id_seq OWNED BY public.auth_role.id;


--
-- Name: auth_role_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_role_permission (
    id integer NOT NULL,
    role_id integer NOT NULL,
    permission_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: auth_role_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_role_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_role_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_role_permission_id_seq OWNED BY public.auth_role_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    username character varying(150) NOT NULL,
    password character varying(128) NOT NULL,
    email character varying(100),
    first_name character varying(50),
    last_name character varying(50),
    is_superuser boolean DEFAULT false,
    is_active boolean DEFAULT true,
    last_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_global_admin boolean DEFAULT false,
    totp_secret text,
    totp_enabled boolean DEFAULT false NOT NULL
);


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;


--
-- Name: auth_user_role; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_role (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: auth_user_role_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_role_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_role_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_role_id_seq OWNED BY public.auth_user_role.id;


--
-- Name: base_company; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.base_company (
    id integer NOT NULL,
    company_name character varying(100) NOT NULL,
    address text,
    phone character varying(20),
    email character varying(100),
    logo character varying(255),
    website character varying(100),
    work_days character varying(7),
    timezone character varying(50),
    date_format character varying(20),
    currency character varying(10),
    emergency_contact json,
    evac_map_pdf character varying(255),
    parent_company_id integer,
    company_type public.companytype,
    is_active boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: base_company_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.base_company_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: base_company_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.base_company_id_seq OWNED BY public.base_company.id;


--
-- Name: base_operationlog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.base_operationlog (
    id bigint NOT NULL,
    user_id integer,
    action character varying(50) NOT NULL,
    table_name character varying(50),
    record_id integer,
    old_values text,
    new_values text,
    ip_address character varying(45),
    user_agent text,
    created_at timestamp with time zone DEFAULT now(),
    ip_addr text,
    remark text
);


--
-- Name: base_operationlog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.base_operationlog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: base_operationlog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.base_operationlog_id_seq OWNED BY public.base_operationlog.id;


--
-- Name: bc_integration_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bc_integration_config (
    id integer NOT NULL,
    tenant_id character varying(200),
    client_id character varying(200),
    client_secret character varying(500),
    environment character varying(50) DEFAULT 'Production'::character varying,
    company_id character varying(100),
    company_name character varying(200),
    is_enabled boolean DEFAULT false,
    sync_time character varying(10) DEFAULT '01:00'::character varying,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: bc_integration_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bc_integration_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bc_integration_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bc_integration_config_id_seq OWNED BY public.bc_integration_config.id;


--
-- Name: bc_sync_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bc_sync_log (
    id integer NOT NULL,
    sync_date date,
    triggered_by character varying(50),
    status character varying(20),
    records_built integer DEFAULT 0,
    records_sent integer DEFAULT 0,
    records_failed integer DEFAULT 0,
    message character varying(500),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: bc_sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bc_sync_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bc_sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bc_sync_log_id_seq OWNED BY public.bc_sync_log.id;


--
-- Name: benefit_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.benefit_plans (
    id integer NOT NULL,
    plan_code character varying(20) NOT NULL,
    plan_name character varying(100) NOT NULL,
    benefit_type character varying(50) NOT NULL,
    description text,
    eligibility character varying(20) DEFAULT 'all_employees'::character varying,
    employer_contribution numeric(5,2),
    employee_contribution numeric(5,2),
    max_coverage numeric(10,2),
    currency character varying(3) DEFAULT 'USD'::character varying,
    enrollment_period_start date,
    enrollment_period_end date,
    effective_date date,
    is_active boolean DEFAULT true,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: benefit_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.benefit_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: benefit_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.benefit_plans_id_seq OWNED BY public.benefit_plans.id;


--
-- Name: biometric_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biometric_devices (
    id integer NOT NULL,
    device_serial character varying(50) NOT NULL,
    device_name character varying(100) NOT NULL,
    device_type character varying(20) NOT NULL,
    manufacturer character varying(50),
    model character varying(50),
    firmware_version character varying(20),
    ip_address character varying(15),
    port integer,
    communication_key character varying(50),
    supported_templates json,
    max_templates_per_user integer,
    enrollment_quality_threshold double precision,
    is_online boolean,
    is_active boolean,
    last_heartbeat timestamp with time zone,
    configuration json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_sync timestamp with time zone
);


--
-- Name: biometric_devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biometric_devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biometric_devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biometric_devices_id_seq OWNED BY public.biometric_devices.id;


--
-- Name: biometric_enrollment_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biometric_enrollment_sessions (
    id integer NOT NULL,
    session_id character varying(100) NOT NULL,
    personnel_id integer NOT NULL,
    template_type character varying(20) NOT NULL,
    device_serial character varying(50),
    status character varying(20),
    progress_percentage double precision,
    current_step character varying(50),
    templates_collected integer,
    templates_required integer,
    quality_threshold double precision,
    error_message text,
    retry_count integer,
    max_retries integer,
    started_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone,
    last_activity timestamp with time zone DEFAULT now()
);


--
-- Name: biometric_enrollment_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biometric_enrollment_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biometric_enrollment_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biometric_enrollment_sessions_id_seq OWNED BY public.biometric_enrollment_sessions.id;


--
-- Name: biometric_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biometric_templates (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    template_type character varying(20) NOT NULL,
    template_data text NOT NULL,
    template_quality double precision,
    finger_index integer,
    hand character varying(10),
    device_serial character varying(50),
    enrollment_method character varying(20),
    is_active boolean,
    is_verified boolean,
    verification_count integer,
    last_used timestamp with time zone,
    enrolled_by integer,
    enrolled_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: biometric_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biometric_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biometric_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biometric_templates_id_seq OWNED BY public.biometric_templates.id;


--
-- Name: biometric_verification_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biometric_verification_logs (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    template_type character varying(20) NOT NULL,
    device_serial character varying(50),
    is_successful boolean NOT NULL,
    confidence_score double precision,
    response_time_ms integer,
    verification_method character varying(20),
    template_used integer,
    error_code character varying(20),
    error_message text,
    location character varying(100),
    purpose character varying(50),
    verified_at timestamp with time zone DEFAULT now()
);


--
-- Name: biometric_verification_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biometric_verification_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biometric_verification_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biometric_verification_logs_id_seq OWNED BY public.biometric_verification_logs.id;


--
-- Name: biotime_access_levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_access_levels (
    id integer NOT NULL,
    level_name character varying(100) NOT NULL,
    level_code character varying(20) NOT NULL,
    priority integer NOT NULL,
    time_restrictions json,
    location_restrictions json,
    device_restrictions json,
    required_biometric_types json,
    min_biometric_quality double precision,
    multi_factor_required boolean DEFAULT false,
    access_permissions json,
    door_permissions json,
    area_permissions json,
    personnel_ids json NOT NULL,
    device_group_ids json NOT NULL,
    biotime_access_level_id character varying(100),
    biotime_configuration json,
    biotime_last_sync timestamp with time zone,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_access_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_access_levels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_access_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_access_levels_id_seq OWNED BY public.biotime_access_levels.id;


--
-- Name: biotime_access_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_access_schedules (
    id integer NOT NULL,
    schedule_name character varying(100) NOT NULL,
    schedule_type character varying(20) NOT NULL,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone NOT NULL,
    monday_enabled boolean DEFAULT true,
    tuesday_enabled boolean DEFAULT true,
    wednesday_enabled boolean DEFAULT true,
    thursday_enabled boolean DEFAULT true,
    friday_enabled boolean DEFAULT true,
    saturday_enabled boolean DEFAULT false,
    sunday_enabled boolean DEFAULT false,
    monday_start_time character varying(5),
    monday_end_time character varying(5),
    tuesday_start_time character varying(5),
    tuesday_end_time character varying(5),
    wednesday_start_time character varying(5),
    wednesday_end_time character varying(5),
    thursday_start_time character varying(5),
    thursday_end_time character varying(5),
    friday_start_time character varying(5),
    friday_end_time character varying(5),
    saturday_start_time character varying(5),
    saturday_end_time character varying(5),
    sunday_start_time character varying(5),
    sunday_end_time character varying(5),
    personnel_ids json NOT NULL,
    device_group_ids json NOT NULL,
    access_levels json NOT NULL,
    biotime_schedule_id character varying(100),
    biotime_sync_enabled boolean DEFAULT true,
    biotime_last_sync timestamp with time zone,
    holiday_overrides json,
    emergency_override json,
    temporary_override json,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_access_schedules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_access_schedules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_access_schedules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_access_schedules_id_seq OWNED BY public.biotime_access_schedules.id;


--
-- Name: biotime_biometric_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_biometric_templates (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    template_type character varying(20) NOT NULL,
    template_id character varying(100) NOT NULL,
    quality_score double precision NOT NULL,
    enrollment_date timestamp with time zone NOT NULL,
    last_used timestamp with time zone,
    device_id character varying(50),
    biotime_template_hash character varying(255),
    template_data json,
    is_active boolean DEFAULT true,
    backup_count integer,
    verification_count integer,
    failure_count integer,
    last_verification_score double precision,
    biotime_template_version character varying(20),
    biotime_device_type character varying(50),
    biotime_enrollment_method character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_biometric_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_biometric_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_biometric_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_biometric_templates_id_seq OWNED BY public.biotime_biometric_templates.id;


--
-- Name: biotime_conflict_resolutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_conflict_resolutions (
    id integer NOT NULL,
    conflict_id character varying(100) NOT NULL,
    conflict_type character varying(50) NOT NULL,
    conflict_description text NOT NULL,
    detected_at timestamp with time zone NOT NULL,
    resolution_strategy character varying(50) NOT NULL,
    resolution_details json,
    resolved_at timestamp with time zone,
    resolved_by integer,
    impact_level character varying(20) NOT NULL,
    affected_records json,
    prevention_measures json,
    biotime_conflict_id character varying(100),
    biotime_resolution_data json,
    status character varying(20),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_conflict_resolutions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_conflict_resolutions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_conflict_resolutions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_conflict_resolutions_id_seq OWNED BY public.biotime_conflict_resolutions.id;


--
-- Name: biotime_device_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_device_groups (
    id integer NOT NULL,
    group_name character varying(100) NOT NULL,
    group_type character varying(50) NOT NULL,
    device_ids json NOT NULL,
    configuration json,
    is_active boolean DEFAULT true,
    parent_group_id integer,
    priority integer,
    description text,
    biotime_group_id character varying(100),
    biotime_sync_enabled boolean DEFAULT true,
    biotime_last_sync timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_device_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_device_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_device_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_device_groups_id_seq OWNED BY public.biotime_device_groups.id;


--
-- Name: biotime_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_devices (
    id integer NOT NULL,
    device_id character varying(100) NOT NULL,
    device_name character varying(100) NOT NULL,
    device_type character varying(50) NOT NULL,
    manufacturer character varying(100),
    model character varying(100),
    firmware_version character varying(50),
    hardware_version character varying(50),
    serial_number character varying(100),
    ip_address character varying(45),
    mac_address character varying(17),
    port integer,
    network_type character varying(20),
    biotime_device_id character varying(100),
    biotime_configuration json,
    biotime_last_config_sync timestamp with time zone,
    biotime_api_version character varying(20),
    supported_biometric_types json,
    max_templates_per_type json,
    supported_verification_methods json,
    anti_passback_enabled boolean DEFAULT false,
    multi_factor_enabled boolean DEFAULT false,
    status character varying(20) NOT NULL,
    last_seen timestamp with time zone,
    last_heartbeat timestamp with time zone,
    battery_level integer,
    signal_strength integer,
    device_group_id integer,
    location character varying(100),
    zone character varying(100),
    installation_date timestamp with time zone,
    warranty_expiry timestamp with time zone,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_devices_id_seq OWNED BY public.biotime_devices.id;


--
-- Name: biotime_sync_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.biotime_sync_logs (
    id integer NOT NULL,
    sync_type character varying(50) NOT NULL,
    sync_direction character varying(20) NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    duration_seconds integer,
    total_records integer,
    successful_records integer,
    failed_records integer,
    conflict_records integer,
    skipped_records integer,
    sync_details json,
    error_details json,
    conflict_resolution json,
    biotime_sync_id character varying(100),
    biotime_api_version character varying(20),
    biotime_server_url character varying(255),
    biotime_last_successful_sync timestamp with time zone,
    status character varying(20),
    retry_count integer,
    max_retries integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: biotime_sync_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.biotime_sync_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: biotime_sync_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.biotime_sync_logs_id_seq OWNED BY public.biotime_sync_logs.id;


--
-- Name: certification_audits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certification_audits (
    id integer NOT NULL,
    certification_id integer NOT NULL,
    personnel_id integer NOT NULL,
    action character varying(50) NOT NULL,
    old_values text,
    new_values text,
    performed_by integer,
    performed_at timestamp with time zone DEFAULT now(),
    reason text,
    ip_address character varying(45),
    user_agent character varying(500)
);


--
-- Name: certification_audits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.certification_audits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certification_audits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certification_audits_id_seq OWNED BY public.certification_audits.id;


--
-- Name: certification_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certification_templates (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    certification_type public.certificationtype NOT NULL,
    issuer character varying(255) NOT NULL,
    description text,
    validity_days integer NOT NULL,
    renewal_required boolean,
    requirements text,
    prerequisites text,
    personnel_types character varying(100),
    roles character varying(500),
    locations character varying(500),
    is_mandatory boolean,
    compliance_weight integer,
    expiry_notification_days integer,
    renewal_notification_days integer,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: certification_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.certification_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certification_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certification_templates_id_seq OWNED BY public.certification_templates.id;


--
-- Name: certifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certifications (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    name character varying(255) NOT NULL,
    certification_type public.certificationtype,
    issuer character varying(255) NOT NULL,
    certificate_number character varying(100) NOT NULL,
    issue_date timestamp with time zone NOT NULL,
    expire_date timestamp with time zone NOT NULL,
    verified_date timestamp with time zone,
    status public.certificationstatus,
    verified boolean,
    verification_data text,
    description text,
    requirements text,
    training_provider character varying(255),
    location character varying(255),
    certificate_file character varying(500),
    verification_file character varying(500),
    notes text,
    tags character varying(500),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: certifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.certifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: certifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.certifications_id_seq OWNED BY public.certifications.id;


--
-- Name: checkinout; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checkinout (
    id bigint NOT NULL,
    user_id integer,
    emp_code character varying(20) NOT NULL,
    check_time timestamp with time zone NOT NULL,
    check_type smallint NOT NULL,
    verify_type smallint,
    sensor_id character varying(20),
    terminal_sn character varying(20),
    work_code integer,
    processed boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: checkinout_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.checkinout_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: checkinout_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.checkinout_id_seq OWNED BY public.checkinout.id;


--
-- Name: contract_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contract_assignments (
    id integer NOT NULL,
    contract_id integer NOT NULL,
    contractor_id integer NOT NULL,
    personnel_id integer,
    project_name character varying(200),
    project_code character varying(50),
    role character varying(100) NOT NULL,
    department_id integer,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone,
    actual_end_date timestamp with time zone,
    hourly_rate double precision,
    daily_rate double precision,
    overtime_rate double precision,
    currency character varying(3) DEFAULT 'USD'::character varying,
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    performance_rating character varying(10),
    completion_status character varying(20) DEFAULT 'IN_PROGRESS'::character varying,
    assigned_by integer,
    supervisor_id integer,
    approved_by integer,
    approved_at timestamp with time zone,
    created_by integer NOT NULL,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: contract_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contract_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contract_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contract_assignments_id_seq OWNED BY public.contract_assignments.id;


--
-- Name: contractor_compliance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contractor_compliance (
    id integer NOT NULL,
    contractor_id integer NOT NULL,
    compliance_type character varying(50) NOT NULL,
    compliance_status character varying(20) NOT NULL,
    compliance_date timestamp with time zone NOT NULL,
    expiry_date timestamp with time zone,
    certifying_authority character varying(100),
    certificate_number character varying(100),
    assessment_score double precision,
    assessment_notes text,
    requirements_met json,
    next_review_date timestamp with time zone,
    certificate_path character varying(500),
    supporting_documents json,
    assessed_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: contractor_compliance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contractor_compliance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contractor_compliance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contractor_compliance_id_seq OWNED BY public.contractor_compliance.id;


--
-- Name: contractors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contractors (
    id integer NOT NULL,
    vendor_id integer,
    contractor_code character varying(50) NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    email character varying(100),
    phone character varying(20),
    date_of_birth timestamp with time zone,
    national_id character varying(50),
    passport_number character varying(50),
    work_permit_number character varying(50),
    work_permit_expiry timestamp with time zone,
    job_title character varying(100),
    specialization character varying(100),
    experience_years integer DEFAULT 0,
    hourly_rate double precision,
    daily_rate double precision,
    currency character varying(3) DEFAULT 'USD'::character varying,
    skills json,
    certifications json,
    security_clearance character varying(50),
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    availability_status character varying(20) DEFAULT 'AVAILABLE'::character varying,
    preferred_work_locations json,
    background_check_status character varying(20) DEFAULT 'PENDING'::character varying,
    background_check_date timestamp with time zone,
    medical_clearance_status character varying(20) DEFAULT 'PENDING'::character varying,
    medical_clearance_date timestamp with time zone,
    created_by integer NOT NULL,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: contractors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contractors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: contractors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contractors_id_seq OWNED BY public.contractors.id;


--
-- Name: custom_attribute_values; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_attribute_values (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    attribute_id integer NOT NULL,
    value_text text,
    value_number double precision,
    value_date timestamp with time zone,
    value_boolean boolean,
    value_json json,
    file_path character varying(500),
    file_name character varying(255),
    file_size integer,
    mime_type character varying(100),
    is_valid boolean,
    validation_errors json,
    created_by integer,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: custom_attribute_values_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.custom_attribute_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: custom_attribute_values_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.custom_attribute_values_id_seq OWNED BY public.custom_attribute_values.id;


--
-- Name: custom_attributes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_attributes (
    id integer NOT NULL,
    attribute_code character varying(50) NOT NULL,
    attribute_name character varying(100) NOT NULL,
    attribute_type public.attributetype NOT NULL,
    description text,
    validation_rules json,
    default_value json,
    display_options json,
    placeholder_text character varying(100),
    category character varying(50),
    group_name character varying(50),
    sort_order integer,
    is_active boolean,
    is_required boolean,
    is_searchable boolean,
    is_visible_in_list boolean,
    read_permissions json,
    write_permissions json,
    created_by integer,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: custom_attributes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.custom_attributes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: custom_attributes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.custom_attributes_id_seq OWNED BY public.custom_attributes.id;


--
-- Name: department_personnel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.department_personnel (
    id integer NOT NULL,
    department_id integer NOT NULL,
    personnel_id integer NOT NULL,
    role character varying(100) NOT NULL,
    "position" character varying(100),
    is_primary boolean,
    is_manager boolean,
    assigned_at timestamp with time zone DEFAULT now(),
    unassigned_at timestamp with time zone,
    approved_by integer,
    approved_at timestamp with time zone,
    status character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: department_personnel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.department_personnel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: department_personnel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.department_personnel_id_seq OWNED BY public.department_personnel.id;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    code character varying(20) NOT NULL,
    description text,
    parent_id integer,
    manager_id integer,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    department_type character varying(50),
    level integer DEFAULT 0,
    sort_order integer DEFAULT 0,
    zone_id integer,
    contact_person character varying(100),
    contact_email character varying(100),
    contact_phone character varying(20),
    max_personnel integer DEFAULT 0,
    current_personnel_count integer DEFAULT 0,
    budget_allocated numeric(15,2),
    budget_used numeric(15,2),
    safety_critical boolean DEFAULT false,
    required_certifications json,
    safety_protocols json,
    access_levels json,
    security_clearance_required boolean DEFAULT false,
    zkteco_department_id integer,
    zkteco_sync_enabled boolean DEFAULT false,
    last_sync_at timestamp with time zone,
    created_by integer,
    updated_by integer,
    status character varying(20),
    default_shift_id integer
);


--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: device_blacklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_blacklist (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    reason text,
    blocked_at timestamp with time zone DEFAULT now(),
    blocked_by integer,
    is_active boolean,
    expires_at timestamp with time zone
);


--
-- Name: device_blacklist_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_blacklist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_blacklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_blacklist_id_seq OWNED BY public.device_blacklist.id;


--
-- Name: device_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_events (
    id integer NOT NULL,
    device_id character varying(100) NOT NULL,
    event_type character varying(50) NOT NULL,
    event_severity character varying(20),
    event_data json,
    old_values json,
    new_values json,
    "timestamp" timestamp with time zone DEFAULT now(),
    resolved_at timestamp with time zone,
    status character varying(20),
    description text,
    resolution_notes text,
    acknowledged_by integer,
    acknowledged_at timestamp with time zone
);


--
-- Name: device_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_events_id_seq OWNED BY public.device_events.id;


--
-- Name: device_maintenance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_maintenance (
    id integer NOT NULL,
    device_id character varying(100) NOT NULL,
    maintenance_type character varying(50) NOT NULL,
    description text,
    scheduled_date timestamp with time zone NOT NULL,
    estimated_duration integer,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    actual_duration integer,
    status character varying(20),
    performed_by integer,
    technician_notes text,
    parts_used json,
    cost integer,
    test_results json,
    next_maintenance_date timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: device_maintenance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_maintenance_id_seq OWNED BY public.device_maintenance.id;


--
-- Name: device_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_schedules (
    id integer NOT NULL,
    device_id character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    monday_enabled boolean,
    tuesday_enabled boolean,
    wednesday_enabled boolean,
    thursday_enabled boolean,
    friday_enabled boolean,
    saturday_enabled boolean,
    sunday_enabled boolean,
    time_ranges json,
    access_mode character varying(50),
    authorized_personnel json,
    is_active boolean,
    priority integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: device_schedules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_schedules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_schedules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_schedules_id_seq OWNED BY public.device_schedules.id;


--
-- Name: device_suppressed; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_suppressed (
    sn text NOT NULL,
    suppressed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: devicemap; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.devicemap (
    id integer NOT NULL,
    device_sn character varying(20) NOT NULL,
    ip_address character varying(15),
    port integer DEFAULT 4370,
    comm_key character varying(20) DEFAULT '0'::character varying,
    device_type smallint DEFAULT 0,
    area_id integer,
    last_sync timestamp with time zone,
    sync_status smallint DEFAULT 0,
    status smallint DEFAULT 0,
    firmware_version character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: devicemap_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.devicemap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: devicemap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.devicemap_id_seq OWNED BY public.devicemap.id;


--
-- Name: devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.devices (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    serial_number character varying(50) NOT NULL,
    device_type character varying(50) DEFAULT 'FINGERPRINT'::character varying,
    model character varying(100),
    firmware_version character varying(50),
    ip_address character varying(45),
    port integer DEFAULT 4370,
    location character varying(255),
    zone_id integer,
    status character varying(20) DEFAULT 'OFFLINE'::character varying,
    is_active boolean DEFAULT true NOT NULL,
    last_heartbeat timestamp with time zone,
    last_sync timestamp with time zone,
    connection_mode character varying(20) DEFAULT 'ADMS'::character varying,
    adms_url character varying(500),
    user_count integer DEFAULT 0,
    fp_count integer DEFAULT 0,
    face_count integer DEFAULT 0,
    log_count integer DEFAULT 0,
    manufacturer character varying(100) DEFAULT 'ZKTeco'::character varying,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    device_id character varying(100),
    location_description character varying(255),
    building character varying(100),
    floor character varying(50),
    last_seen timestamp with time zone,
    battery_level integer,
    signal_strength integer,
    supported_biometrics jsonb,
    max_templates integer DEFAULT 1000,
    current_templates integer DEFAULT 0,
    access_mode character varying(50) DEFAULT 'normal'::character varying,
    authorized_personnel jsonb,
    access_schedule jsonb,
    zkteco_device_id character varying(50),
    zkteco_config jsonb,
    encryption_enabled boolean DEFAULT true,
    authentication_key character varying(255),
    last_maintenance timestamp with time zone,
    next_maintenance timestamp with time zone,
    maintenance_interval_days integer DEFAULT 90,
    settings jsonb,
    mac_address character varying(17),
    hardware_version character varying(50),
    auto_poll boolean DEFAULT false NOT NULL,
    poll_interval_sec integer DEFAULT 300 NOT NULL,
    last_attendance_pull timestamp with time zone,
    custom_fields jsonb
);


--
-- Name: devices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.devices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: devices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.devices_id_seq OWNED BY public.devices.id;


--
-- Name: disciplinary_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disciplinary_cases (
    id integer NOT NULL,
    personnel_id integer,
    case_number character varying(50) NOT NULL,
    incident_date date NOT NULL,
    incident_type character varying(50) NOT NULL,
    description text,
    severity_level character varying(20),
    action_type character varying(20),
    status character varying(20) DEFAULT 'open'::character varying,
    reported_by integer,
    assigned_to integer,
    resolution_date date,
    resolution_notes text,
    appeal_status character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: disciplinary_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disciplinary_cases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disciplinary_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disciplinary_cases_id_seq OWNED BY public.disciplinary_cases.id;


--
-- Name: emergency_device; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_device (
    id integer NOT NULL,
    terminal_sn character varying(20),
    device_type smallint DEFAULT 0,
    zone_id integer,
    status smallint DEFAULT 0,
    last_heartbeat timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_device_command; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_device_command (
    id bigint NOT NULL,
    emergency_event_id bigint,
    device_id integer,
    command_type character varying(50),
    command_data jsonb,
    command_priority smallint,
    status character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    sent_at timestamp with time zone,
    executed_at timestamp with time zone,
    completed_at timestamp with time zone,
    queue_time double precision,
    execution_time double precision,
    total_time double precision,
    device_response jsonb,
    acknowledgment jsonb,
    confirmation_data jsonb,
    error_code character varying(50),
    error_message text,
    retry_count integer,
    max_retries integer,
    batch_id character varying(50),
    parent_command bigint,
    operator_id integer,
    audit_log jsonb,
    compliance_data jsonb
);


--
-- Name: emergency_device_command_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_device_command_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_device_command_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_device_command_id_seq OWNED BY public.emergency_device_command.id;


--
-- Name: emergency_device_enhanced; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_device_enhanced (
    id integer NOT NULL,
    terminal_sn character varying(20) NOT NULL,
    device_type smallint NOT NULL,
    zone_id integer,
    building_id integer,
    status smallint,
    health_score double precision,
    last_maintenance timestamp with time zone,
    next_maintenance timestamp with time zone,
    response_time_avg double precision,
    uptime_percentage double precision,
    failure_count integer,
    test_results jsonb,
    ai_monitored boolean,
    predictive_maintenance jsonb,
    performance_anomalies jsonb,
    usage_patterns jsonb,
    location_description character varying(200),
    installation_date date,
    manufacturer character varying(100),
    model character varying(100),
    firmware_version character varying(50),
    serial_number character varying(100),
    capabilities jsonb,
    supported_commands jsonb,
    integration_points jsonb,
    test_schedule character varying(50),
    last_test timestamp with time zone,
    test_results_history jsonb,
    calibration_data jsonb,
    operating_temperature_min double precision,
    operating_temperature_max double precision,
    humidity_tolerance_min double precision,
    humidity_tolerance_max double precision,
    power_requirements jsonb,
    network_config jsonb,
    communication_protocols jsonb,
    encryption_keys jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_device_enhanced_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_device_enhanced_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_device_enhanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_device_enhanced_id_seq OWNED BY public.emergency_device_enhanced.id;


--
-- Name: emergency_device_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_device_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_device_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_device_id_seq OWNED BY public.emergency_device.id;


--
-- Name: emergency_device_maintenance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_device_maintenance (
    id integer NOT NULL,
    device_id integer NOT NULL,
    maintenance_type smallint NOT NULL,
    description text NOT NULL,
    priority smallint,
    scheduled_date timestamp with time zone NOT NULL,
    estimated_duration integer,
    actual_duration integer,
    status character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    technician character varying(100),
    technician_id integer,
    supervisor character varying(100),
    supervisor_id integer,
    work_performed text,
    parts_used jsonb,
    tools_used jsonb,
    measurements jsonb,
    labor_cost double precision,
    parts_cost double precision,
    total_cost double precision,
    cost_center character varying(50),
    quality_check boolean,
    quality_score double precision,
    inspection_notes text,
    approved_by integer,
    approved_time timestamp with time zone,
    next_maintenance timestamp with time zone,
    warranty_expiry date,
    maintenance_interval integer,
    predictive_maintenance boolean,
    ai_recommended boolean,
    performance_impact jsonb,
    risk_assessment jsonb,
    work_order_id character varying(100),
    photos_before jsonb,
    photos_after jsonb,
    documentation jsonb,
    compliance_required boolean,
    audit_findings jsonb,
    regulatory_compliance jsonb
);


--
-- Name: emergency_device_maintenance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_device_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_device_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_device_maintenance_id_seq OWNED BY public.emergency_device_maintenance.id;


--
-- Name: emergency_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_event (
    id bigint NOT NULL,
    event_type smallint NOT NULL,
    status smallint,
    scope smallint,
    zone_ids integer[],
    door_ids integer[],
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone,
    initiated_by integer,
    initiated_type smallint,
    trigger_source character varying(100),
    reason text,
    actions jsonb,
    mustering_event_id bigint,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_event_enhanced; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_event_enhanced (
    id bigint NOT NULL,
    event_type smallint NOT NULL,
    status smallint,
    scope smallint,
    severity smallint,
    zone_ids integer[],
    door_ids integer[],
    building_ids integer[],
    personnel_ids integer[],
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone,
    estimated_resolution timestamp with time zone,
    actual_resolution timestamp with time zone,
    initiated_by integer,
    initiated_type smallint,
    trigger_source character varying(100),
    confidence_score double precision,
    reason text,
    description text,
    impact_assessment jsonb,
    risk_factors jsonb,
    mitigation_actions jsonb,
    ai_detected boolean,
    ai_predictions jsonb,
    ai_recommendations jsonb,
    pattern_anomalies jsonb,
    mustering_event_id bigint,
    incident_report_id bigint,
    external_system_id character varying(100),
    response_time double precision,
    resolution_time double precision,
    cost_impact double precision,
    disruption_level smallint,
    actions jsonb,
    command_queue jsonb,
    notification_log jsonb,
    compliance_required boolean,
    compliance_notes text,
    audit_trail jsonb,
    regulatory_reports jsonb,
    weather_conditions jsonb,
    environmental_factors jsonb,
    affected_personnel jsonb,
    injuries jsonb,
    evacuations jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_event_enhanced_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_event_enhanced_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_event_enhanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_event_enhanced_id_seq OWNED BY public.emergency_event_enhanced.id;


--
-- Name: emergency_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_event_id_seq OWNED BY public.emergency_event.id;


--
-- Name: emergency_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_notification (
    id bigint NOT NULL,
    emergency_event_id bigint NOT NULL,
    channel smallint NOT NULL,
    recipient_type smallint,
    recipient_id integer,
    recipient_addr character varying(255),
    message text,
    status smallint,
    sent_time timestamp with time zone,
    delivered_time timestamp with time zone,
    error_msg text,
    template_vars jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_notification_enhanced; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_notification_enhanced (
    id bigint NOT NULL,
    emergency_event_id bigint NOT NULL,
    channel smallint NOT NULL,
    recipient_type smallint,
    recipient_id integer,
    recipient_addr character varying(255),
    recipient_name character varying(100),
    message text,
    message_template character varying(100),
    template_variables jsonb,
    personalization_data jsonb,
    status smallint,
    priority smallint,
    created_at timestamp with time zone DEFAULT now(),
    queued_at timestamp with time zone,
    sent_time timestamp with time zone,
    delivered_time timestamp with time zone,
    acknowledged_at timestamp with time zone,
    read_time timestamp with time zone,
    delivery_attempts integer,
    last_attempt_status character varying(50),
    delivery_provider character varying(50),
    tracking_id character varying(100),
    delivery_time double precision,
    cost double precision,
    engagement_metrics jsonb,
    retry_policy jsonb,
    escalation_rules jsonb,
    acknowledgment_required boolean,
    response_tracking jsonb,
    compliance_required boolean,
    audit_log jsonb,
    regulatory_compliance jsonb,
    error_codes jsonb,
    error_details text,
    recovery_actions jsonb
);


--
-- Name: emergency_notification_enhanced_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_notification_enhanced_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_notification_enhanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_notification_enhanced_id_seq OWNED BY public.emergency_notification_enhanced.id;


--
-- Name: emergency_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_notification_id_seq OWNED BY public.emergency_notification.id;


--
-- Name: emergency_panic_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_panic_log (
    id bigint NOT NULL,
    terminal_sn character varying(20),
    panic_time timestamp with time zone NOT NULL,
    panic_type smallint,
    emp_code character varying(20),
    location character varying(100),
    emergency_event_id bigint,
    reason text,
    resolved_by integer,
    resolved_time timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_panic_log_enhanced; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_panic_log_enhanced (
    id bigint NOT NULL,
    terminal_sn character varying(20),
    device_type smallint,
    emp_code character varying(20),
    location character varying(100),
    geolocation jsonb,
    emergency_event_id bigint,
    panic_time timestamp with time zone NOT NULL,
    panic_type smallint,
    severity smallint,
    confidence double precision,
    environmental_conditions jsonb,
    nearby_personnel jsonb,
    security_context jsonb,
    ai_detected boolean,
    ai_confidence double precision,
    ai_risk_assessment jsonb,
    false_alarm_probability double precision,
    resolved_by integer,
    resolved_time timestamp with time zone,
    resolution_method character varying(50),
    verification_required boolean,
    verified_by integer,
    verified_time timestamp with time zone,
    impact_assessment jsonb,
    disruption_duration integer,
    cost_impact double precision,
    personnel_impacted jsonb,
    follow_up_required boolean,
    follow_up_actions jsonb,
    investigation_required boolean,
    investigation_results jsonb,
    audio_recording character varying(255),
    video_recording character varying(255),
    sensor_data jsonb,
    regulatory_report boolean,
    audit_findings jsonb,
    compliance_notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_panic_log_enhanced_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_panic_log_enhanced_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_panic_log_enhanced_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_panic_log_enhanced_id_seq OWNED BY public.emergency_panic_log_enhanced.id;


--
-- Name: emergency_panic_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_panic_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_panic_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_panic_log_id_seq OWNED BY public.emergency_panic_log.id;


--
-- Name: emergency_plan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_plan (
    id integer NOT NULL,
    plan_name character varying(100) NOT NULL,
    event_type smallint,
    zone_id integer,
    steps text,
    pdf_path character varying(255),
    contacts jsonb,
    is_active boolean,
    last_reviewed date,
    next_review date,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_plan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_plan_id_seq OWNED BY public.emergency_plan.id;


--
-- Name: emergency_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emergency_template (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    event_type smallint NOT NULL,
    description text,
    actions jsonb NOT NULL,
    notify_channels jsonb,
    auto_mustering boolean,
    auto_mustering_zone_id integer,
    is_active boolean,
    is_default boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: emergency_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.emergency_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: emergency_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.emergency_template_id_seq OWNED BY public.emergency_template.id;


--
-- Name: employee_benefits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_benefits (
    id integer NOT NULL,
    personnel_id integer,
    plan_id integer,
    enrollment_date date,
    effective_date date,
    coverage_amount numeric(10,2),
    dependents json,
    status character varying(20) DEFAULT 'active'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: employee_benefits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_benefits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_benefits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_benefits_id_seq OWNED BY public.employee_benefits.id;


--
-- Name: employment_contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employment_contracts (
    id integer NOT NULL,
    personnel_id integer,
    contract_number character varying(50) NOT NULL,
    contract_type character varying(20) NOT NULL,
    start_date date NOT NULL,
    end_date date,
    probation_end_date date,
    salary numeric(10,2),
    currency character varying(3) DEFAULT 'USD'::character varying,
    payment_frequency character varying(20),
    working_hours integer,
    job_title character varying(100),
    department_id integer,
    position_id integer,
    terms text,
    status character varying(20) DEFAULT 'active'::character varying,
    signed_by integer,
    signed_date date,
    document_url character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: employment_contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employment_contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employment_contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employment_contracts_id_seq OWNED BY public.employment_contracts.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    event_type character varying(50) NOT NULL,
    description text,
    personnel_id integer,
    user_id integer,
    "timestamp" timestamp with time zone NOT NULL,
    event_metadata json
);


--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: face; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.face (
    id integer NOT NULL,
    user_id integer,
    template_data bytea NOT NULL,
    template_version integer DEFAULT 1,
    quality_score integer,
    template_size integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT face_quality_score_check CHECK (((quality_score >= 0) AND (quality_score <= 100)))
);


--
-- Name: face_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.face_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: face_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.face_id_seq OWNED BY public.face.id;


--
-- Name: fingerprint; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fingerprint (
    id integer NOT NULL,
    user_id integer,
    finger_index integer NOT NULL,
    template_data bytea NOT NULL,
    template_version integer DEFAULT 1,
    quality_score integer,
    template_size integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT fingerprint_finger_index_check CHECK (((finger_index >= 0) AND (finger_index <= 9))),
    CONSTRAINT fingerprint_quality_score_check CHECK (((quality_score >= 0) AND (quality_score <= 100)))
);


--
-- Name: fingerprint_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fingerprint_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fingerprint_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fingerprint_id_seq OWNED BY public.fingerprint.id;


--
-- Name: flight_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flight_log (
    id integer NOT NULL,
    transport_id integer NOT NULL,
    flight_date timestamp with time zone NOT NULL,
    departure_time timestamp with time zone NOT NULL,
    arrival_time timestamp with time zone,
    departure_location character varying(100) NOT NULL,
    arrival_location character varying(100) NOT NULL,
    flight_duration double precision NOT NULL,
    distance double precision NOT NULL,
    fuel_consumed double precision,
    weather_conditions character varying(100),
    pilot_name character varying(100),
    co_pilot_name character varying(100),
    flight_route character varying(200),
    passengers_count integer,
    cargo_weight double precision,
    incidents text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: flight_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.flight_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: flight_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.flight_log_id_seq OWNED BY public.flight_log.id;


--
-- Name: holiday; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.holiday (
    id integer NOT NULL,
    holiday_name character varying(100) NOT NULL,
    holiday_date date NOT NULL,
    end_date date,
    is_repeatable boolean DEFAULT false,
    repeat_month integer,
    repeat_day integer,
    holiday_type smallint DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: holiday_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.holiday_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: holiday_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.holiday_id_seq OWNED BY public.holiday.id;


--
-- Name: hr_integration_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_integration_config (
    id integer NOT NULL,
    api_base_url character varying(255),
    api_key character varying(500),
    org_id character varying(100),
    auth_header_name character varying(100) DEFAULT 'Authorization'::character varying,
    attendance_endpoint character varying(255) DEFAULT '/v1/attendance/clock-records'::character varying,
    employee_endpoint character varying(255) DEFAULT '/v1/employees'::character varying,
    is_enabled boolean DEFAULT false,
    sync_time character varying(10) DEFAULT '00:00'::character varying,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: hr_integration_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hr_integration_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hr_integration_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hr_integration_config_id_seq OWNED BY public.hr_integration_config.id;


--
-- Name: hr_sync_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_sync_log (
    id integer NOT NULL,
    sync_date date,
    triggered_by character varying(50),
    status character varying(20),
    records_built integer DEFAULT 0,
    records_sent integer DEFAULT 0,
    records_failed integer DEFAULT 0,
    message character varying(500),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: hr_sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hr_sync_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hr_sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hr_sync_log_id_seq OWNED BY public.hr_sync_log.id;


--
-- Name: iclock_bio_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iclock_bio_template (
    id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    finger_id smallint DEFAULT 0 NOT NULL,
    template_size integer,
    valid boolean DEFAULT true,
    template_data text,
    source_sn character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: iclock_bio_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iclock_bio_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iclock_bio_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iclock_bio_template_id_seq OWNED BY public.iclock_bio_template.id;


--
-- Name: iclock_devcmd; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iclock_devcmd (
    id bigint NOT NULL,
    sn character varying(20) NOT NULL,
    cmd_content text NOT NULL,
    status smallint,
    cmd_commit_time timestamp with time zone DEFAULT now(),
    cmd_trans_time timestamp with time zone,
    cmd_return_time timestamp with time zone,
    cmd_return text,
    created_by integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: iclock_devcmd_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iclock_devcmd_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iclock_devcmd_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iclock_devcmd_id_seq OWNED BY public.iclock_devcmd.id;


--
-- Name: iclock_operlog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iclock_operlog (
    id bigint NOT NULL,
    terminal_sn character varying(20) NOT NULL,
    oper_event smallint NOT NULL,
    event_time timestamp with time zone NOT NULL,
    admin_id character varying(20),
    door_id integer,
    object_name character varying(100),
    param1 character varying(100),
    param2 character varying(100),
    raw_data text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: iclock_operlog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iclock_operlog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iclock_operlog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iclock_operlog_id_seq OWNED BY public.iclock_operlog.id;


--
-- Name: iclock_terminal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iclock_terminal (
    id integer NOT NULL,
    sn character varying(20) NOT NULL,
    alias character varying(50),
    ip_address character varying(45),
    area_id integer,
    last_activity timestamp with time zone,
    state smallint DEFAULT 0,
    comm_key character varying(20),
    fw_ver character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    log_count integer DEFAULT 0,
    zone_id integer,
    pushver character varying(10) DEFAULT '1.0'::character varying,
    user_count integer DEFAULT 0,
    fp_count integer DEFAULT 0,
    face_count integer DEFAULT 0,
    palm_count integer DEFAULT 0,
    att_stamp bigint DEFAULT 0,
    op_stamp bigint DEFAULT 0,
    heartbeat_interval integer DEFAULT 30,
    device_name character varying(50),
    device_model character varying(50),
    device_type smallint DEFAULT 0,
    is_auto_reg boolean DEFAULT false,
    reader_purpose character varying(20) DEFAULT 'ATTENDANCE'::character varying NOT NULL,
    connection_mode character varying(10) DEFAULT 'adms'::character varying NOT NULL,
    user_stamp bigint DEFAULT 0 NOT NULL,
    platform character varying(30),
    mac_address character varying(17),
    oem_vendor character varying(50),
    CONSTRAINT iclock_terminal_reader_purpose_check CHECK (((reader_purpose)::text = ANY ((ARRAY['ATTENDANCE'::character varying, 'ACCESS_ENTRY'::character varying, 'ACCESS_EXIT'::character varying, 'MUSTERING'::character varying, 'POB'::character varying, 'EMERGENCY'::character varying, 'TRANSPORT_CHECKIN'::character varying])::text[])))
);


--
-- Name: iclock_terminal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iclock_terminal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iclock_terminal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iclock_terminal_id_seq OWNED BY public.iclock_terminal.id;


--
-- Name: iclock_transaction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iclock_transaction (
    id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    punch_time timestamp with time zone NOT NULL,
    punch_state smallint,
    verify_type smallint,
    work_code integer,
    terminal_sn character varying(20),
    area_alias character varying(50),
    upload_time timestamp with time zone DEFAULT now()
);


--
-- Name: iclock_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iclock_transaction_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iclock_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iclock_transaction_id_seq OWNED BY public.iclock_transaction.id;


--
-- Name: leave_balance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leave_balance (
    id integer NOT NULL,
    personnel_id integer,
    leave_type character varying(50) NOT NULL,
    total_days numeric(5,2),
    used_days numeric(5,2) DEFAULT 0,
    balance_days numeric(5,2),
    carry_forward_days numeric(5,2) DEFAULT 0,
    year integer,
    accrual_rate numeric(5,2),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: leave_balance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leave_balance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leave_balance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leave_balance_id_seq OWNED BY public.leave_balance.id;


--
-- Name: leave_blackout; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leave_blackout (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    reason text,
    applies_to character varying(20) DEFAULT 'all'::character varying,
    department_id integer,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: leave_blackout_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leave_blackout_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leave_blackout_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leave_blackout_id_seq OWNED BY public.leave_blackout.id;


--
-- Name: leave_management; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leave_management (
    id integer NOT NULL,
    personnel_id integer,
    leave_type character varying(50) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    days_count numeric(5,2),
    reason text,
    status character varying(20) DEFAULT 'pending'::character varying,
    approved_by integer,
    approved_at timestamp with time zone,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: leave_management_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leave_management_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leave_management_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leave_management_id_seq OWNED BY public.leave_management.id;


--
-- Name: manifest_entry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manifest_entry (
    id integer NOT NULL,
    schedule_id integer NOT NULL,
    personnel_id integer,
    passenger_name character varying(200) NOT NULL,
    emp_code character varying(50),
    company character varying(100),
    id_number character varying(50),
    body_weight double precision,
    baggage_weight double precision,
    direction character varying(20) DEFAULT 'INBOUND'::character varying NOT NULL,
    status character varying(20) DEFAULT 'MANIFESTED'::character varying NOT NULL,
    confirmed_at timestamp with time zone,
    confirmed_by_id integer,
    remarks text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: manifest_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manifest_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manifest_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manifest_entry_id_seq OWNED BY public.manifest_entry.id;


--
-- Name: mtd_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_audit_log (
    id bigint NOT NULL,
    access_time timestamp without time zone,
    user_id integer,
    record_type character varying(50),
    record_id bigint,
    action character varying(20),
    ip_address character varying(45),
    user_agent text,
    details text
);


--
-- Name: mtd_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_audit_log_id_seq OWNED BY public.mtd_audit_log.id;


--
-- Name: mtd_cert_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_cert_type (
    id integer NOT NULL,
    cert_name character varying(100) NOT NULL,
    validity_days integer NOT NULL,
    is_critical boolean,
    required_for_dept integer[],
    required_for_position integer[],
    required_for_vendor integer[],
    description text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: mtd_cert_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_cert_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_cert_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_cert_type_id_seq OWNED BY public.mtd_cert_type.id;


--
-- Name: mtd_certification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_certification (
    id bigint NOT NULL,
    person_type smallint NOT NULL,
    emp_id integer,
    visitor_id bigint,
    cert_type_id integer NOT NULL,
    cert_no character varying(100),
    issuer character varying(100),
    issue_date date NOT NULL,
    expiry_date date,
    cert_path character varying(255),
    status smallint,
    verified_by integer,
    verified_time timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: mtd_certification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_certification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_certification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_certification_id_seq OWNED BY public.mtd_certification.id;


--
-- Name: mtd_compliance_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_compliance_log (
    id bigint NOT NULL,
    check_time timestamp without time zone,
    emp_id integer,
    cert_type_id integer,
    record_type character varying(50),
    record_id bigint,
    status smallint,
    action_taken character varying(100),
    details text,
    created_by integer
);


--
-- Name: mtd_compliance_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_compliance_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_compliance_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_compliance_log_id_seq OWNED BY public.mtd_compliance_log.id;


--
-- Name: mtd_induction_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_induction_record (
    id bigint NOT NULL,
    person_type smallint NOT NULL,
    emp_id integer,
    visitor_id bigint,
    template_id integer NOT NULL,
    taken_date date,
    score integer,
    passed boolean,
    valid_until date,
    signed_doc character varying(255),
    trainer_emp_id integer,
    quiz_answers json,
    completion_time timestamp without time zone,
    created_at timestamp without time zone
);


--
-- Name: mtd_induction_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_induction_record_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_induction_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_induction_record_id_seq OWNED BY public.mtd_induction_record.id;


--
-- Name: mtd_induction_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_induction_template (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    video_path character varying(255),
    slides_path character varying(255),
    quiz_questions json,
    passing_score integer,
    validity_days integer,
    required_for_type smallint,
    description text,
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: mtd_induction_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_induction_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_induction_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_induction_template_id_seq OWNED BY public.mtd_induction_template.id;


--
-- Name: mtd_medical_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_medical_record (
    id bigint NOT NULL,
    person_type smallint NOT NULL,
    emp_id integer,
    visitor_id bigint,
    blood_group character varying(3),
    height_cm integer,
    weight_kg numeric(5,2),
    bmi numeric(4,2),
    medical_conditions text,
    allergies text,
    disabilities text,
    fit_status smallint,
    restrictions text,
    doctor_name character varying(100),
    last_checkup date,
    next_due date,
    cert_path character varying(255),
    updated_by integer,
    updated_time timestamp without time zone
);


--
-- Name: mtd_medical_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_medical_record_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_medical_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_medical_record_id_seq OWNED BY public.mtd_medical_record.id;


--
-- Name: mtd_ppe_issue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_ppe_issue (
    id bigint NOT NULL,
    emp_id integer NOT NULL,
    ppe_type_id integer NOT NULL,
    serial_no character varying(100),
    issue_date date,
    due_return_date date,
    return_date date,
    condition_out smallint,
    condition_in smallint,
    last_calib_date date,
    next_calib_date date,
    status smallint,
    notes text,
    issued_by integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: mtd_ppe_issue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_ppe_issue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_ppe_issue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_ppe_issue_id_seq OWNED BY public.mtd_ppe_issue.id;


--
-- Name: mtd_ppe_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtd_ppe_type (
    id integer NOT NULL,
    ppe_name character varying(100) NOT NULL,
    lifespan_days integer,
    requires_calibration boolean,
    calib_interval_days integer,
    description text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: mtd_ppe_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtd_ppe_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtd_ppe_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtd_ppe_type_id_seq OWNED BY public.mtd_ppe_type.id;


--
-- Name: mtg_action_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_action_item (
    id bigint NOT NULL,
    booking_id bigint NOT NULL,
    action_desc character varying(500) NOT NULL,
    assignee_emp_id integer NOT NULL,
    due_date date,
    status smallint,
    completed_time timestamp with time zone,
    created_time timestamp with time zone,
    created_by integer
);


--
-- Name: mtg_action_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_action_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_action_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_action_item_id_seq OWNED BY public.mtg_action_item.id;


--
-- Name: mtg_attendance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_attendance (
    id bigint NOT NULL,
    booking_id bigint NOT NULL,
    attendee_id bigint NOT NULL,
    check_in_time timestamp with time zone,
    check_out_time timestamp with time zone,
    device_sn character varying(20),
    verify_type smallint,
    status smallint,
    notes text
);


--
-- Name: mtg_attendance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_attendance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_attendance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_attendance_id_seq OWNED BY public.mtg_attendance.id;


--
-- Name: mtg_attendee; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_attendee (
    id bigint NOT NULL,
    booking_id bigint NOT NULL,
    attendee_type smallint NOT NULL,
    emp_id integer,
    visitor_id bigint,
    ext_name character varying(100),
    ext_email character varying(100),
    ext_phone character varying(20),
    is_required boolean,
    pre_reg_id bigint,
    invitation_sent boolean,
    invitation_sent_time timestamp with time zone
);


--
-- Name: mtg_attendee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_attendee_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_attendee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_attendee_id_seq OWNED BY public.mtg_attendee.id;


--
-- Name: mtg_booking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_booking (
    id bigint NOT NULL,
    room_id integer NOT NULL,
    title character varying(200) NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    organizer_emp_id integer NOT NULL,
    attendee_count integer,
    agenda text,
    attachments text,
    repeat_type smallint,
    repeat_until date,
    status smallint,
    approval_by integer,
    approval_time timestamp with time zone,
    approval_note character varying(255),
    meeting_code character varying(20) NOT NULL,
    qr_code character varying(100),
    auto_unlock boolean,
    created_time timestamp with time zone,
    updated_time timestamp with time zone
);


--
-- Name: TABLE mtg_booking; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.mtg_booking IS 'Unique constraint on meeting QR code';


--
-- Name: mtg_booking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_booking_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_booking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_booking_id_seq OWNED BY public.mtg_booking.id;


--
-- Name: mtg_equipment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_equipment (
    id integer NOT NULL,
    equip_name character varying(100) NOT NULL,
    equip_type character varying(50),
    room_id integer,
    status smallint,
    serial_no character varying(50),
    purchase_date date,
    warranty_expiry date,
    last_maintenance date,
    notes text
);


--
-- Name: mtg_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_equipment_id_seq OWNED BY public.mtg_equipment.id;


--
-- Name: mtg_minutes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_minutes (
    id bigint NOT NULL,
    booking_id bigint NOT NULL,
    minutes_path character varying(255),
    uploaded_by integer NOT NULL,
    uploaded_time timestamp with time zone,
    file_size bigint,
    file_type character varying(10)
);


--
-- Name: mtg_minutes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_minutes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_minutes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_minutes_id_seq OWNED BY public.mtg_minutes.id;


--
-- Name: mtg_room; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mtg_room (
    id integer NOT NULL,
    room_name character varying(100) NOT NULL,
    capacity integer NOT NULL,
    location character varying(100),
    area_id integer,
    door_id integer,
    equipment text,
    status smallint,
    require_approval boolean,
    mustering_zone_id integer,
    is_emergency_assembly boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: mtg_room_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mtg_room_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mtg_room_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mtg_room_id_seq OWNED BY public.mtg_room.id;


--
-- Name: mustering_drill_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_drill_schedule (
    id integer NOT NULL,
    zone_id integer NOT NULL,
    event_type smallint DEFAULT 1,
    scheduled_time timestamp with time zone NOT NULL,
    participant_type smallint DEFAULT 0,
    participant_id integer,
    template_id integer,
    auto_start boolean DEFAULT true,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    processed boolean DEFAULT false,
    processed_time timestamp with time zone,
    status character varying(20) DEFAULT 'PENDING'::character varying
);


--
-- Name: mustering_drill_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_drill_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_drill_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_drill_schedule_id_seq OWNED BY public.mustering_drill_schedule.id;


--
-- Name: mustering_escalation_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_escalation_record (
    id bigint NOT NULL,
    event_id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    level smallint NOT NULL,
    notification_type character varying(20),
    notified_at timestamp with time zone DEFAULT now()
);


--
-- Name: mustering_escalation_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_escalation_record_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_escalation_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_escalation_record_id_seq OWNED BY public.mustering_escalation_record.id;


--
-- Name: mustering_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_event (
    id bigint NOT NULL,
    zone_id integer,
    event_type smallint NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone,
    status smallint DEFAULT 0,
    initiated_by integer,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text,
    total_expected integer DEFAULT 0,
    total_safe integer DEFAULT 0,
    total_missing integer DEFAULT 0,
    total_injured integer DEFAULT 0,
    zone_ids jsonb DEFAULT '[]'::jsonb,
    max_duration_minutes integer DEFAULT 0 NOT NULL
);


--
-- Name: mustering_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_event_id_seq OWNED BY public.mustering_event.id;


--
-- Name: mustering_expected; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_expected (
    id bigint NOT NULL,
    event_id bigint NOT NULL,
    emp_code character varying(50) NOT NULL,
    emp_name character varying(100) NOT NULL,
    dept_id integer,
    shift_id integer,
    last_punch_time timestamp with time zone,
    last_punch_area character varying(100),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: mustering_expected_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_expected_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_expected_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_expected_id_seq OWNED BY public.mustering_expected.id;


--
-- Name: mustering_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_log (
    id bigint NOT NULL,
    event_id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    check_time timestamp with time zone NOT NULL,
    device_sn character varying(20),
    status smallint DEFAULT 0,
    location character varying(100),
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    emp_name character varying(100),
    dept_name character varying(50),
    device_alias character varying(50),
    last_punch_area character varying(20)
);


--
-- Name: mustering_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_log_id_seq OWNED BY public.mustering_log.id;


--
-- Name: mustering_search_sweep; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_search_sweep (
    id bigint NOT NULL,
    event_id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    area_searched character varying(200) NOT NULL,
    result character varying(20) NOT NULL,
    searcher_id integer,
    searcher_name character varying(100),
    notes text,
    sweep_time timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: mustering_search_sweep_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_search_sweep_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_search_sweep_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_search_sweep_id_seq OWNED BY public.mustering_search_sweep.id;


--
-- Name: mustering_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mustering_template (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    event_type smallint,
    notify_sms boolean DEFAULT false,
    notify_email boolean DEFAULT false,
    notify_users text,
    actions text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: mustering_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mustering_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: mustering_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mustering_template_id_seq OWNED BY public.mustering_template.id;


--
-- Name: onboarding_checklists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_checklists (
    id integer NOT NULL,
    onboarding_id integer NOT NULL,
    checklist_name character varying(100) NOT NULL,
    checklist_type character varying(50) NOT NULL,
    description text,
    is_required boolean,
    checklist_items json,
    sort_order integer,
    is_completed boolean,
    completed_by integer,
    completed_at timestamp with time zone,
    completion_notes text,
    depends_on_tasks json,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: onboarding_checklists_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_checklists_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_checklists_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_checklists_id_seq OWNED BY public.onboarding_checklists.id;


--
-- Name: onboarding_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_documents (
    id integer NOT NULL,
    onboarding_id integer NOT NULL,
    document_type character varying(50) NOT NULL,
    document_name character varying(255) NOT NULL,
    document_path character varying(500) NOT NULL,
    file_size integer,
    mime_type character varying(100),
    description text,
    is_required boolean,
    uploaded_by integer,
    uploaded_at timestamp with time zone DEFAULT now(),
    is_verified boolean,
    verified_by integer,
    verified_at timestamp with time zone,
    verification_notes text
);


--
-- Name: onboarding_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_documents_id_seq OWNED BY public.onboarding_documents.id;


--
-- Name: onboarding_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_notifications (
    id integer NOT NULL,
    onboarding_id integer NOT NULL,
    notification_type character varying(50) NOT NULL,
    recipient_id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    is_read boolean,
    read_at timestamp with time zone,
    sent_via character varying(20),
    sent_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: onboarding_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_notifications_id_seq OWNED BY public.onboarding_notifications.id;


--
-- Name: onboarding_task; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_task (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    task_name character varying(100) NOT NULL,
    doc_path character varying(255),
    status smallint DEFAULT 0,
    due_date date,
    approved_by integer,
    approved_time timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: onboarding_task_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_task_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_task_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_task_id_seq OWNED BY public.onboarding_task.id;


--
-- Name: onboarding_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_tasks (
    id integer NOT NULL,
    onboarding_id integer NOT NULL,
    task_name character varying(100) NOT NULL,
    task_type public.tasktype NOT NULL,
    description text,
    is_required boolean,
    due_date timestamp with time zone,
    priority public.taskpriority,
    status character varying(20),
    completion_date timestamp with time zone,
    completed_by integer,
    completion_notes text,
    checklist_items json,
    completed_items json,
    depends_on_tasks json,
    created_by integer NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: onboarding_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_tasks_id_seq OWNED BY public.onboarding_tasks.id;


--
-- Name: onboarding_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboarding_templates (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    template_code character varying(50) NOT NULL,
    onboarding_type public.onboardingtype NOT NULL,
    description text,
    default_tasks json NOT NULL,
    required_documents json,
    approval_workflow json,
    default_duration_days integer,
    reminder_settings json,
    is_active boolean,
    is_default boolean,
    usage_count integer,
    last_used timestamp with time zone,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: onboarding_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboarding_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboarding_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboarding_templates_id_seq OWNED BY public.onboarding_templates.id;


--
-- Name: onboardings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.onboardings (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    onboarding_type public.onboardingtype NOT NULL,
    status public.onboardingstatus,
    start_date timestamp with time zone NOT NULL,
    planned_end_date timestamp with time zone NOT NULL,
    actual_end_date timestamp with time zone,
    job_title character varying(200) NOT NULL,
    job_description text,
    department_id integer,
    position_id integer,
    reporting_to integer,
    buddy_id integer,
    manager_id integer,
    template_id integer,
    template_data json,
    custom_fields json,
    completion_percentage double precision,
    last_progress_update timestamp with time zone,
    submitted_at timestamp with time zone,
    reviewed_by integer,
    reviewed_at timestamp with time zone,
    approved_by integer,
    approved_at timestamp with time zone,
    rejection_reason text,
    completed_at timestamp with time zone,
    completed_by integer,
    exit_interview_date timestamp with time zone,
    exit_interview_conducted_by integer,
    created_by integer NOT NULL,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: onboardings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.onboardings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: onboardings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.onboardings_id_seq OWNED BY public.onboardings.id;


--
-- Name: overtime_management; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overtime_management (
    id integer NOT NULL,
    personnel_id integer,
    overtime_type character varying(20) NOT NULL,
    date date NOT NULL,
    start_time time without time zone,
    end_time time without time zone,
    hours_worked numeric(5,2),
    overtime_hours numeric(5,2),
    reason text,
    status character varying(20) DEFAULT 'pending'::character varying,
    approved_by integer,
    approved_at timestamp with time zone,
    rejection_reason text,
    compensation_type character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: overtime_management_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.overtime_management_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: overtime_management_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.overtime_management_id_seq OWNED BY public.overtime_management.id;


--
-- Name: overtime_record; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overtime_record (
    id bigint NOT NULL,
    emp_code character varying(20) NOT NULL,
    overtime_date date NOT NULL,
    overtime_rule_id integer,
    start_time time without time zone,
    end_time time without time zone,
    total_minutes integer NOT NULL,
    rate double precision NOT NULL,
    overtime_amount double precision,
    approved_by integer,
    approved_time timestamp with time zone,
    status smallint DEFAULT 0,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: overtime_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.overtime_record_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: overtime_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.overtime_record_id_seq OWNED BY public.overtime_record.id;


--
-- Name: overtime_rule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overtime_rule (
    id integer NOT NULL,
    rule_name character varying(100) NOT NULL,
    rule_type smallint NOT NULL,
    min_minutes integer NOT NULL,
    rate double precision DEFAULT 1.0 NOT NULL,
    max_hours_per_day double precision,
    max_hours_per_week double precision,
    area_id integer,
    department_id integer,
    is_active boolean DEFAULT true,
    effective_date date NOT NULL,
    expiry_date date,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: overtime_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.overtime_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: overtime_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.overtime_rule_id_seq OWNED BY public.overtime_rule.id;


--
-- Name: overtime_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.overtime_rules (
    id integer NOT NULL,
    rule_name character varying(100) NOT NULL,
    rule_type character varying(20) NOT NULL,
    daily_threshold_hours numeric(5,2),
    weekly_threshold_hours numeric(5,2),
    monthly_threshold_hours numeric(5,2),
    rate_multiplier numeric(5,2) DEFAULT 1.5,
    max_daily_hours numeric(5,2),
    max_weekly_hours numeric(5,2),
    max_monthly_hours numeric(5,2),
    requires_approval boolean DEFAULT true,
    applies_to character varying(20) DEFAULT 'all'::character varying,
    is_active boolean DEFAULT true,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: overtime_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.overtime_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: overtime_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.overtime_rules_id_seq OWNED BY public.overtime_rules.id;


--
-- Name: pay_attendance_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_attendance_mapping (
    id integer NOT NULL,
    attendance_field character varying(50) NOT NULL,
    payroll_item_name character varying(50) NOT NULL,
    rate numeric(10,4),
    is_active boolean,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_attendance_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_attendance_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_attendance_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_attendance_mapping_id_seq OWNED BY public.pay_attendance_mapping.id;


--
-- Name: pay_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_audit_log (
    id bigint NOT NULL,
    table_name character varying(50) NOT NULL,
    record_id integer NOT NULL,
    action_type character varying(20) NOT NULL,
    old_values jsonb,
    new_values jsonb,
    changed_fields jsonb,
    user_id integer,
    ip_address inet,
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now()
);


--
-- Name: pay_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_audit_log_id_seq OWNED BY public.pay_audit_log.id;


--
-- Name: pay_bank_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_bank_config (
    id integer NOT NULL,
    bank_name character varying(100) NOT NULL,
    bank_code character varying(20) NOT NULL,
    export_format character varying(10),
    file_template text,
    header_rows integer,
    footer_rows integer,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_bank_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_bank_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_bank_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_bank_config_id_seq OWNED BY public.pay_bank_config.id;


--
-- Name: pay_calculation_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_calculation_log (
    id bigint NOT NULL,
    period_id integer,
    emp_id integer,
    calculation_type character varying(50),
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    status character varying(20),
    input_data jsonb,
    result_data jsonb,
    error_message text,
    created_by integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_calculation_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_calculation_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_calculation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_calculation_log_id_seq OWNED BY public.pay_calculation_log.id;


--
-- Name: pay_contractor_rate; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_contractor_rate (
    id integer NOT NULL,
    vendor_id integer,
    position_id integer,
    position_name character varying(100),
    hourly_rate numeric(10,2),
    daily_rate numeric(10,2),
    weekly_rate numeric(10,2),
    monthly_rate numeric(10,2),
    ot_rate numeric(10,2),
    night_shift_rate numeric(10,2),
    holiday_rate numeric(10,2),
    is_active boolean,
    effective_date date,
    end_date date,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_contractor_rate_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_contractor_rate_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_contractor_rate_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_contractor_rate_id_seq OWNED BY public.pay_contractor_rate.id;


--
-- Name: pay_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_item (
    id integer NOT NULL,
    structure_id integer NOT NULL,
    item_name character varying(50) NOT NULL,
    item_type public.payitemtype NOT NULL,
    calc_type public.paycalctype,
    amount numeric(10,2),
    formula text,
    attendance_field character varying(50),
    rate numeric(10,4),
    sequence integer,
    is_taxable boolean,
    is_print boolean,
    is_mandatory boolean,
    gl_account character varying(50),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_item_id_seq OWNED BY public.pay_item.id;


--
-- Name: pay_loan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_loan (
    id integer NOT NULL,
    emp_id integer NOT NULL,
    loan_type character varying(50),
    loan_amount numeric(10,2) NOT NULL,
    emi_amount numeric(10,2) NOT NULL,
    interest_rate numeric(5,2),
    start_date date NOT NULL,
    end_date date NOT NULL,
    balance numeric(10,2) NOT NULL,
    status public.payloanstatus,
    reason character varying(255),
    approved_by integer,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_loan_deduction; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_loan_deduction (
    id integer NOT NULL,
    loan_id integer NOT NULL,
    salary_id bigint,
    period_id integer,
    emp_id integer NOT NULL,
    emi_amount numeric(10,2) NOT NULL,
    principal_amount numeric(10,2),
    interest_amount numeric(10,2),
    balance_before numeric(10,2),
    balance_after numeric(10,2),
    deduction_date date,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_loan_deduction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_loan_deduction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_loan_deduction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_loan_deduction_id_seq OWNED BY public.pay_loan_deduction.id;


--
-- Name: pay_loan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_loan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_loan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_loan_id_seq OWNED BY public.pay_loan.id;


--
-- Name: pay_payslip_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_payslip_template (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    template_type character varying(20),
    header_html text,
    body_html text,
    footer_html text,
    css_style text,
    is_default boolean,
    is_active boolean,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_payslip_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_payslip_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_payslip_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_payslip_template_id_seq OWNED BY public.pay_payslip_template.id;


--
-- Name: pay_period; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_period (
    id integer NOT NULL,
    period_name character varying(50) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    pay_date date,
    status public.payperiodstatus,
    is_att_locked boolean,
    description text,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    closed_at timestamp with time zone,
    closed_by integer
);


--
-- Name: pay_period_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_period_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_period_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_period_id_seq OWNED BY public.pay_period.id;


--
-- Name: pay_salary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_salary (
    id bigint NOT NULL,
    period_id integer NOT NULL,
    emp_id integer NOT NULL,
    structure_id integer,
    basic_salary numeric(10,2),
    work_days numeric(5,2),
    present_days numeric(5,2),
    ot_hours numeric(5,2),
    late_minutes integer,
    leave_days numeric(5,2),
    absent_days numeric(5,2),
    gross_salary numeric(10,2),
    total_earnings numeric(10,2),
    total_deductions numeric(10,2),
    net_salary numeric(10,2),
    is_final boolean,
    calc_status public.paycalcstatus,
    calc_time timestamp with time zone DEFAULT now(),
    calc_by integer,
    verified_by integer,
    verified_at timestamp with time zone,
    approved_by integer,
    approved_at timestamp with time zone,
    zone_hours numeric(5,2),
    night_hours numeric(5,2),
    hazard_days numeric(5,2),
    contractor_flag boolean
);


--
-- Name: pay_salary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_salary_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_salary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_salary_id_seq OWNED BY public.pay_salary.id;


--
-- Name: pay_salary_item; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_salary_item (
    id bigint NOT NULL,
    salary_id bigint NOT NULL,
    item_id integer,
    item_name character varying(50) NOT NULL,
    item_value numeric(10,2),
    item_type public.payitemtype NOT NULL,
    formula_used text,
    source_value numeric(10,2),
    calculation_order integer,
    is_manual_adjustment boolean,
    adjustment_reason text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_salary_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_salary_item_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_salary_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_salary_item_id_seq OWNED BY public.pay_salary_item.id;


--
-- Name: pay_structure; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_structure (
    id integer NOT NULL,
    structure_name character varying(100) NOT NULL,
    structure_type public.paystructuretype,
    is_active boolean,
    version integer,
    effective_date date,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by integer
);


--
-- Name: pay_structure_assign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_structure_assign (
    id integer NOT NULL,
    structure_id integer NOT NULL,
    assign_type integer NOT NULL,
    assign_id integer NOT NULL,
    priority integer,
    effective_date date,
    end_date date,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_structure_assign_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_structure_assign_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_structure_assign_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_structure_assign_id_seq OWNED BY public.pay_structure_assign.id;


--
-- Name: pay_structure_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_structure_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_structure_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_structure_id_seq OWNED BY public.pay_structure.id;


--
-- Name: pay_zone_allowance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_zone_allowance (
    id integer NOT NULL,
    structure_id integer NOT NULL,
    area_id integer,
    zone_name character varying(100),
    allowance_type integer,
    amount numeric(10,2) NOT NULL,
    is_hazard boolean,
    hazard_rate numeric(5,2),
    effective_date date,
    end_date date,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: pay_zone_allowance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_zone_allowance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_zone_allowance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_zone_allowance_id_seq OWNED BY public.pay_zone_allowance.id;


--
-- Name: performance_appraisals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.performance_appraisals (
    id integer NOT NULL,
    personnel_id integer,
    cycle_id integer,
    appraisal_date date,
    reviewer_id integer,
    overall_rating character varying(20),
    goals_achieved numeric(5,2),
    performance_score numeric(5,2),
    strengths text,
    areas_for_improvement text,
    comments text,
    status character varying(20) DEFAULT 'draft'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: performance_appraisals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.performance_appraisals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: performance_appraisals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.performance_appraisals_id_seq OWNED BY public.performance_appraisals.id;


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissions (
    id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    category character varying(50) DEFAULT 'general'::character varying NOT NULL,
    is_system boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.permissions_id_seq OWNED BY public.permissions.id;


--
-- Name: personnel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    full_name character varying(200),
    email character varying(255),
    phone character varying(20),
    user_id integer,
    department_id integer,
    "position" character varying(100),
    primary_role_id integer,
    current_zone_id integer,
    status character varying(20) DEFAULT 'ONSHORE'::character varying,
    employment_type character varying(30) DEFAULT 'EMPLOYEE'::character varying,
    hire_date date,
    photo_url character varying(500),
    nationality character varying(100),
    id_number character varying(50),
    passport_number character varying(50),
    emergency_contact_name character varying(200),
    emergency_contact_phone character varying(20),
    is_active boolean DEFAULT true NOT NULL,
    hr_source character varying(20),
    hr_synced_at timestamp with time zone,
    on_leave boolean DEFAULT false,
    leave_end_date date,
    is_pob boolean DEFAULT false NOT NULL,
    pob_location character varying(100),
    pob_since timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    badge_id character varying(50),
    company character varying(255),
    department character varying(100),
    role character varying(100),
    current_location character varying(100),
    is_onboard boolean DEFAULT false,
    personnel_type character varying(20) DEFAULT 'STAFF'::character varying,
    safety_critical boolean DEFAULT false,
    biometric_enrolled boolean DEFAULT false,
    compliance_score double precision DEFAULT 0.0,
    biometric_data jsonb,
    fingerprint_templates jsonb,
    face_template character varying(255),
    certifications jsonb,
    training_records jsonb,
    medical_fitness_date timestamp with time zone,
    emergency_contact jsonb,
    blood_group character varying(10),
    medical_conditions text,
    last_seen timestamp with time zone,
    biotime_employee_id character varying(50),
    work_schedule jsonb,
    access_groups jsonb,
    device_groups jsonb,
    biometric_quality_score double precision DEFAULT 0.0,
    last_sync_timestamp timestamp with time zone,
    timezone_preference character varying(50) DEFAULT 'UTC'::character varying,
    language_preference character varying(10) DEFAULT 'en'::character varying,
    card_number bigint
);


--
-- Name: personnel_area; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel_area (
    id integer NOT NULL,
    area_code character varying(20),
    area_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: personnel_area_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_area_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_area_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_area_id_seq OWNED BY public.personnel_area.id;


--
-- Name: personnel_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel_assignments (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    location character varying(255) NOT NULL,
    zone character varying(100),
    vessel character varying(100),
    platform character varying(100),
    assignment_type character varying(50) NOT NULL,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone,
    is_active boolean DEFAULT true,
    transport_method character varying(50),
    transport_details jsonb,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: personnel_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_assignments_id_seq OWNED BY public.personnel_assignments.id;


--
-- Name: personnel_department; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel_department (
    id integer NOT NULL,
    dept_code character varying(20),
    dept_name character varying(50) NOT NULL,
    parent_id integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    default_shift_id integer
);


--
-- Name: personnel_department_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_department_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_department_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_department_id_seq OWNED BY public.personnel_department.id;


--
-- Name: personnel_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel_documents (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    filename text NOT NULL,
    original_name text NOT NULL,
    file_size bigint,
    content_type text,
    category text DEFAULT 'other'::text,
    title text,
    expiry_date date,
    notes text,
    uploaded_by integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: personnel_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_documents_id_seq OWNED BY public.personnel_documents.id;


--
-- Name: personnel_employee; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personnel_employee (
    id integer NOT NULL,
    emp_code character varying(20) NOT NULL,
    first_name character varying(20),
    last_name character varying(25) NOT NULL,
    dept_id integer,
    area_id integer,
    position_id integer,
    hire_date date,
    birthday date,
    sex character(1),
    photo character varying(255),
    card_no character varying(20),
    pwd character varying(20),
    status smallint DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: personnel_employee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_employee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_employee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_employee_id_seq OWNED BY public.personnel_employee.id;


--
-- Name: personnel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personnel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personnel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personnel_id_seq OWNED BY public.personnel.id;


--
-- Name: pob_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pob_status (
    id integer NOT NULL,
    personnel_id integer,
    personnel_count integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'ONSHORE'::character varying NOT NULL,
    location character varying(100),
    last_updated timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: pob_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pob_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pob_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pob_status_id_seq OWNED BY public.pob_status.id;


--
-- Name: position_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.position_assignments (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    position_id integer NOT NULL,
    department_id integer,
    assignment_type character varying(20) DEFAULT 'PRIMARY'::character varying,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone,
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    is_current boolean DEFAULT true,
    assigned_by integer,
    approved_by integer,
    approved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: position_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.position_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: position_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.position_assignments_id_seq OWNED BY public.position_assignments.id;


--
-- Name: position_levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.position_levels (
    id integer NOT NULL,
    level_code character varying(10) NOT NULL,
    level_name character varying(50) NOT NULL,
    level_number integer NOT NULL,
    description text,
    level_type character varying(20),
    authority_level integer DEFAULT 1,
    can_approve boolean DEFAULT false,
    can_manage boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: position_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.position_levels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: position_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.position_levels_id_seq OWNED BY public.position_levels.id;


--
-- Name: position_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.position_templates (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    template_code character varying(20) NOT NULL,
    position_type character varying(20),
    job_category character varying(30),
    template_data json NOT NULL,
    default_requirements json,
    usage_count integer DEFAULT 0,
    last_used timestamp with time zone,
    is_active boolean DEFAULT true,
    is_system_template boolean DEFAULT false,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: position_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.position_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: position_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.position_templates_id_seq OWNED BY public.position_templates.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.positions (
    id integer NOT NULL,
    position_code character varying(20) NOT NULL,
    position_name character varying(100) NOT NULL,
    description text,
    parent_id integer,
    level integer DEFAULT 1,
    sort_order integer DEFAULT 0,
    department_id integer,
    position_type character varying(20),
    job_category character varying(30),
    grade_level character varying(10),
    required_certifications json,
    required_skills json,
    min_experience_years integer DEFAULT 0,
    education_level character varying(50),
    salary_range_min double precision,
    salary_range_max double precision,
    currency character varying(3) DEFAULT 'USD'::character varying,
    is_active boolean DEFAULT true,
    is_safety_critical boolean DEFAULT false,
    requires_background_check boolean DEFAULT false,
    created_by integer,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text,
    headcount integer DEFAULT 1
);


--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: promotion_transfers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.promotion_transfers (
    id integer NOT NULL,
    personnel_id integer,
    transfer_type character varying(20) NOT NULL,
    effective_date date NOT NULL,
    from_department_id integer,
    to_department_id integer,
    from_position_id integer,
    to_position_id integer,
    from_location character varying(100),
    to_location character varying(100),
    salary_change numeric(10,2),
    reason text,
    status character varying(20) DEFAULT 'pending'::character varying,
    requested_by integer,
    approved_by integer,
    approved_at timestamp with time zone,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: promotion_transfers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.promotion_transfers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: promotion_transfers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.promotion_transfers_id_seq OWNED BY public.promotion_transfers.id;


--
-- Name: resignation_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resignation_documents (
    id integer NOT NULL,
    resignation_id integer NOT NULL,
    document_type character varying(50) NOT NULL,
    document_name character varying(255) NOT NULL,
    document_path character varying(500) NOT NULL,
    file_size integer,
    mime_type character varying(100),
    description text,
    is_required boolean,
    uploaded_by integer,
    uploaded_at timestamp with time zone DEFAULT now(),
    is_verified boolean,
    verified_by integer,
    verified_at timestamp with time zone,
    verification_notes text
);


--
-- Name: resignation_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resignation_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resignation_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resignation_documents_id_seq OWNED BY public.resignation_documents.id;


--
-- Name: resignation_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resignation_notifications (
    id integer NOT NULL,
    resignation_id integer NOT NULL,
    notification_type character varying(50) NOT NULL,
    recipient_id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    is_read boolean,
    read_at timestamp with time zone,
    sent_via character varying(20),
    sent_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: resignation_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resignation_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resignation_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resignation_notifications_id_seq OWNED BY public.resignation_notifications.id;


--
-- Name: resignation_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resignation_tasks (
    id integer NOT NULL,
    resignation_id integer NOT NULL,
    task_name character varying(100) NOT NULL,
    task_type character varying(50) NOT NULL,
    description text,
    is_required boolean,
    is_completed boolean,
    completion_date timestamp with time zone,
    completed_by integer,
    completion_notes text,
    checklist_items json,
    due_date timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: resignation_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resignation_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resignation_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resignation_tasks_id_seq OWNED BY public.resignation_tasks.id;


--
-- Name: resignation_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resignation_templates (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    template_code character varying(20) NOT NULL,
    resignation_type public.resignationtype NOT NULL,
    default_tasks json NOT NULL,
    required_documents json,
    approval_workflow json,
    notification_settings json,
    description text,
    is_active boolean,
    is_default boolean,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: resignation_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resignation_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resignation_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resignation_templates_id_seq OWNED BY public.resignation_templates.id;


--
-- Name: resignations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resignations (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    resignation_type public.resignationtype NOT NULL,
    status public.resignationstatus,
    resignation_date timestamp with time zone NOT NULL,
    last_working_day timestamp with time zone NOT NULL,
    reason text NOT NULL,
    detailed_reason text,
    exit_interview_date timestamp with time zone,
    exit_interview_conducted_by integer,
    exit_interview_notes text,
    handover_completed boolean,
    handover_date timestamp with time zone,
    handover_conducted_by integer,
    handover_notes text,
    handover_checklist json,
    financial_clearance_completed boolean,
    financial_clearance_date timestamp with time zone,
    financial_clearance_conducted_by integer,
    financial_clearance_notes text,
    assets_returned boolean,
    assets_return_date timestamp with time zone,
    assets_return_conducted_by integer,
    assets_return_notes text,
    assets_return_checklist json,
    system_access_revoked boolean,
    system_access_revoked_date timestamp with time zone,
    system_access_revoked_by integer,
    device_access_removed boolean,
    approved_by integer,
    approved_at timestamp with time zone,
    rejection_reason text,
    completed_at timestamp with time zone,
    completed_by integer,
    created_by integer NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: resignations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resignations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resignations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resignations_id_seq OWNED BY public.resignations.id;


--
-- Name: role_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_assignments (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    role_id integer NOT NULL,
    assigned_at timestamp with time zone DEFAULT now(),
    assigned_by character varying(100),
    expires_at timestamp with time zone,
    is_active boolean DEFAULT true,
    is_primary boolean DEFAULT false
);


--
-- Name: role_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.role_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: role_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.role_assignments_id_seq OWNED BY public.role_assignments.id;


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    id integer NOT NULL,
    role_id integer NOT NULL,
    permission_code character varying(100) NOT NULL,
    granted_at timestamp with time zone DEFAULT now(),
    granted_by character varying(100)
);


--
-- Name: role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.role_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: role_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.role_permissions_id_seq OWNED BY public.role_permissions.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    code character varying(50) NOT NULL,
    description text,
    level integer DEFAULT 1,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: rpt_export_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rpt_export_log (
    id integer NOT NULL,
    template_id integer,
    user_id integer,
    export_time timestamp without time zone,
    format character varying(10),
    filters jsonb,
    row_count integer,
    file_path character varying(255),
    file_size integer,
    ip_address character varying(45),
    status character varying(20),
    error_message text,
    task_id character varying(100)
);


--
-- Name: rpt_export_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rpt_export_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rpt_export_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rpt_export_log_id_seq OWNED BY public.rpt_export_log.id;


--
-- Name: rpt_favorite; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rpt_favorite (
    id integer NOT NULL,
    user_id integer NOT NULL,
    template_id integer NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: rpt_favorite_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rpt_favorite_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rpt_favorite_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rpt_favorite_id_seq OWNED BY public.rpt_favorite.id;


--
-- Name: rpt_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rpt_schedule (
    id integer NOT NULL,
    template_id integer NOT NULL,
    schedule_name character varying(100) NOT NULL,
    cron character varying(50) NOT NULL,
    format character varying(10),
    recipients jsonb,
    last_run timestamp without time zone,
    next_run timestamp without time zone,
    is_active boolean,
    created_by integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: rpt_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rpt_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rpt_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rpt_schedule_id_seq OWNED BY public.rpt_schedule.id;


--
-- Name: rpt_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rpt_template (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    module character varying(50) NOT NULL,
    report_code character varying(100) NOT NULL,
    filters jsonb,
    columns jsonb,
    group_by character varying(50),
    chart_type character varying(20),
    is_system boolean,
    created_by integer,
    is_public boolean,
    description text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: rpt_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rpt_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rpt_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rpt_template_id_seq OWNED BY public.rpt_template.id;


--
-- Name: rpt_user_preset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rpt_user_preset (
    id integer NOT NULL,
    user_id integer NOT NULL,
    template_id integer,
    preset_name character varying(100) NOT NULL,
    preset_type character varying(20) NOT NULL,
    filters jsonb,
    columns jsonb,
    is_default boolean,
    created_at timestamp without time zone
);


--
-- Name: rpt_user_preset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rpt_user_preset_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rpt_user_preset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rpt_user_preset_id_seq OWNED BY public.rpt_user_preset.id;


--
-- Name: schedule_management; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schedule_management (
    id integer NOT NULL,
    personnel_id integer,
    shift_id integer,
    schedule_date date NOT NULL,
    status character varying(20) DEFAULT 'scheduled'::character varying,
    assigned_by integer,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: schedule_management_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schedule_management_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schedule_management_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schedule_management_id_seq OWNED BY public.schedule_management.id;


--
-- Name: shift_management; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shift_management (
    id integer NOT NULL,
    shift_code character varying(20) NOT NULL,
    shift_name character varying(100) NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    break_duration integer DEFAULT 0,
    shift_type character varying(20) NOT NULL,
    working_hours integer NOT NULL,
    is_night_shift boolean DEFAULT false,
    is_weekend_shift boolean DEFAULT false,
    is_flexible boolean DEFAULT false,
    rotation_pattern json,
    rotation_cycle_days integer,
    grace_period_minutes integer DEFAULT 15,
    max_late_minutes integer DEFAULT 60,
    max_early_departure_minutes integer DEFAULT 30,
    overtime_threshold_minutes integer DEFAULT 30,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: shift_management_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.shift_management_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: shift_management_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.shift_management_id_seq OWNED BY public.shift_management.id;


--
-- Name: sn; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sn (
    id integer NOT NULL,
    sn character varying(20) NOT NULL,
    device_type character varying(50),
    model character varying(50),
    firmware character varying(20),
    purchase_date date,
    warranty_expiry date,
    status smallint DEFAULT 0,
    location character varying(100),
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: sn_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sn_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sn_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sn_id_seq OWNED BY public.sn.id;


--
-- Name: ssr; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ssr (
    id bigint NOT NULL,
    user_id integer,
    ssr_type smallint NOT NULL,
    request_date date NOT NULL,
    start_time time without time zone,
    end_time time without time zone,
    reason text,
    status smallint DEFAULT 0,
    approved_by integer,
    approved_time timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: ssr_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ssr_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ssr_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ssr_id_seq OWNED BY public.ssr.id;


--
-- Name: sys_api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_api_keys (
    id integer NOT NULL,
    api_key character varying(255) NOT NULL,
    name character varying(100) NOT NULL,
    created_by integer,
    is_active boolean DEFAULT true,
    expiry_date date,
    last_used timestamp with time zone,
    usage_count integer DEFAULT 0,
    ip_whitelist text[],
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_api_keys_id_seq OWNED BY public.sys_api_keys.id;


--
-- Name: sys_branding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_branding (
    id integer NOT NULL,
    company_name character varying(100),
    logo_url character varying(500),
    primary_color character varying(7),
    secondary_color character varying(7),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_branding_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_branding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_branding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_branding_id_seq OWNED BY public.sys_branding.id;


--
-- Name: sys_consent_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_consent_records (
    id integer NOT NULL,
    user_id integer NOT NULL,
    consent_type character varying(50),
    consented boolean DEFAULT true,
    ip_address character varying(45),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_consent_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_consent_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_consent_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_consent_records_id_seq OWNED BY public.sys_consent_records.id;


--
-- Name: sys_data_access_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_data_access_logs (
    id bigint NOT NULL,
    user_id integer,
    table_name character varying(100),
    record_id integer,
    action character varying(50),
    accessed_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_data_access_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_data_access_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_data_access_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_data_access_logs_id_seq OWNED BY public.sys_data_access_logs.id;


--
-- Name: sys_db_backups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_db_backups (
    id bigint NOT NULL,
    backup_time timestamp with time zone DEFAULT now(),
    backup_type smallint DEFAULT 0,
    file_path character varying(255),
    file_size bigint,
    status smallint DEFAULT 0,
    created_by character varying(100)
);


--
-- Name: sys_db_backups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_db_backups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_db_backups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_db_backups_id_seq OWNED BY public.sys_db_backups.id;


--
-- Name: sys_email_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_email_templates (
    id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(100) NOT NULL,
    subject character varying(255),
    body_html text,
    body_text text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_email_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_email_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_email_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_email_templates_id_seq OWNED BY public.sys_email_templates.id;


--
-- Name: sys_languages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_languages (
    id integer NOT NULL,
    code character varying(10) NOT NULL,
    name character varying(50) NOT NULL,
    is_default boolean DEFAULT false,
    is_active boolean DEFAULT true
);


--
-- Name: sys_languages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_languages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_languages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_languages_id_seq OWNED BY public.sys_languages.id;


--
-- Name: sys_licenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_licenses (
    id integer NOT NULL,
    license_key character varying(255) NOT NULL,
    license_type smallint DEFAULT 1,
    max_users integer DEFAULT 100,
    max_devices integer DEFAULT 50,
    issued_to character varying(255),
    valid_from timestamp with time zone DEFAULT now(),
    valid_until timestamp with time zone,
    is_active boolean DEFAULT true,
    features jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_licenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_licenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_licenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_licenses_id_seq OWNED BY public.sys_licenses.id;


--
-- Name: sys_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_notifications (
    id integer NOT NULL,
    user_id integer,
    notification_type character varying(50) DEFAULT 'info'::character varying,
    title character varying(200) NOT NULL,
    message text,
    priority character varying(20) DEFAULT 'medium'::character varying,
    is_read boolean DEFAULT false,
    read_at timestamp with time zone,
    link character varying(500),
    dedup_key character varying(200),
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone
);


--
-- Name: sys_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_notifications_id_seq OWNED BY public.sys_notifications.id;


--
-- Name: sys_parameters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_parameters (
    id integer NOT NULL,
    param_key character varying(100) NOT NULL,
    param_value text,
    param_type character varying(20) DEFAULT 'string'::character varying,
    module character varying(50) DEFAULT 'system'::character varying NOT NULL,
    description text,
    is_public boolean DEFAULT false,
    is_encrypted boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    updated_by character varying(100)
);


--
-- Name: sys_parameters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_parameters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_parameters_id_seq OWNED BY public.sys_parameters.id;


--
-- Name: sys_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_permissions (
    id integer NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    module character varying(50) DEFAULT 'general'::character varying NOT NULL,
    action character varying(50) DEFAULT 'view'::character varying NOT NULL,
    category character varying(50) DEFAULT 'general'::character varying NOT NULL,
    is_system boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_permissions_id_seq OWNED BY public.sys_permissions.id;


--
-- Name: sys_renewal_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_renewal_log (
    id integer NOT NULL,
    subscription_id integer,
    previous_expiry timestamp with time zone NOT NULL,
    new_expiry timestamp with time zone NOT NULL,
    key_prefix character varying(12),
    activated_by character varying(150),
    ip_address character varying(45),
    activated_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_renewal_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_renewal_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_renewal_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_renewal_log_id_seq OWNED BY public.sys_renewal_log.id;


--
-- Name: sys_role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_role_permissions (
    id integer NOT NULL,
    role_id integer NOT NULL,
    permission_code character varying(100) NOT NULL,
    granted_at timestamp with time zone DEFAULT now(),
    granted_by character varying(100)
);


--
-- Name: sys_role_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_role_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_role_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_role_permissions_id_seq OWNED BY public.sys_role_permissions.id;


--
-- Name: sys_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_roles (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    level integer DEFAULT 50 NOT NULL,
    is_system boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by character varying(100)
);


--
-- Name: sys_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_roles_id_seq OWNED BY public.sys_roles.id;


--
-- Name: sys_sso_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_sso_configs (
    id integer NOT NULL,
    sso_type smallint DEFAULT 0,
    server_url character varying(500),
    bind_dn character varying(255),
    bind_password character varying(255),
    base_dn character varying(255),
    is_active boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_sso_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_sso_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_sso_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_sso_configs_id_seq OWNED BY public.sys_sso_configs.id;


--
-- Name: sys_subscription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_subscription (
    id integer NOT NULL,
    installation_id character varying(64) NOT NULL,
    org_name character varying(200) NOT NULL,
    tier character varying(50) DEFAULT 'standard'::character varying,
    max_users integer DEFAULT 50,
    max_employees integer DEFAULT 500,
    max_devices integer DEFAULT 20,
    issue_date date DEFAULT CURRENT_DATE NOT NULL,
    expiry_date timestamp with time zone NOT NULL,
    is_active boolean DEFAULT true,
    notes text,
    created_by character varying(150),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_subscription_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_subscription_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_subscription_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_subscription_id_seq OWNED BY public.sys_subscription.id;


--
-- Name: sys_translations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_translations (
    id integer NOT NULL,
    lang_code character varying(10) NOT NULL,
    key character varying(255) NOT NULL,
    value text
);


--
-- Name: sys_translations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_translations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_translations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_translations_id_seq OWNED BY public.sys_translations.id;


--
-- Name: sys_user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_user_roles (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role_id integer NOT NULL,
    assigned_at timestamp with time zone DEFAULT now(),
    assigned_by character varying(100),
    expires_at timestamp with time zone,
    is_active boolean DEFAULT true,
    is_primary boolean DEFAULT false
);


--
-- Name: sys_user_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_user_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_user_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_user_roles_id_seq OWNED BY public.sys_user_roles.id;


--
-- Name: sys_webhooks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sys_webhooks (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    url character varying(500) NOT NULL,
    events text[],
    secret_key character varying(255),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: sys_webhooks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sys_webhooks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sys_webhooks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sys_webhooks_id_seq OWNED BY public.sys_webhooks.id;


--
-- Name: system_company; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_company (
    id integer NOT NULL,
    name character varying(200) DEFAULT 'Marconi.ng EPC Limited'::character varying NOT NULL,
    short_name character varying(50),
    industry character varying(100) DEFAULT 'Oil & Gas'::character varying,
    address text,
    city character varying(100),
    state character varying(100),
    country character varying(100) DEFAULT 'Nigeria'::character varying,
    phone character varying(50),
    email character varying(100),
    website character varying(200),
    logo_url character varying(500),
    timezone character varying(50) DEFAULT 'Africa/Lagos'::character varying,
    date_format character varying(20) DEFAULT 'DD/MM/YYYY'::character varying,
    time_format character varying(10) DEFAULT '24h'::character varying,
    fiscal_year_start character varying(5) DEFAULT '01-01'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: system_company_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_company_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_company_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_company_id_seq OWNED BY public.system_company.id;


--
-- Name: training_courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.training_courses (
    id integer NOT NULL,
    course_code character varying(20) NOT NULL,
    course_name character varying(200) NOT NULL,
    description text,
    duration_hours integer,
    category character varying(50),
    is_mandatory boolean DEFAULT false,
    valid_period_months integer,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: training_courses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.training_courses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: training_courses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.training_courses_id_seq OWNED BY public.training_courses.id;


--
-- Name: training_enrollment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.training_enrollment (
    id integer NOT NULL,
    personnel_id integer,
    course_id integer,
    enrollment_date date,
    completion_date date,
    status character varying(20) DEFAULT 'enrolled'::character varying,
    score numeric(5,2),
    certificate_url character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    expiry_date date,
    personnel_type character varying(20)
);


--
-- Name: training_enrollment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.training_enrollment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: training_enrollment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.training_enrollment_id_seq OWNED BY public.training_enrollment.id;


--
-- Name: transport; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport (
    id integer NOT NULL,
    type smallint NOT NULL,
    identifier character varying(50) NOT NULL,
    registration_number character varying(50),
    operator character varying(100),
    capacity integer,
    max_payload_kg double precision,
    current_pob integer,
    status smallint,
    base_location character varying(100),
    current_location character varying(100),
    fuel_capacity double precision,
    current_fuel double precision,
    flight_hours double precision,
    max_altitude integer,
    max_speed double precision,
    cost_per_hour double precision,
    utilization_rate double precision,
    performance_rating double precision,
    is_available boolean,
    is_maintenance_mode boolean,
    is_inspection_due boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transport_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport_assignments (
    id integer NOT NULL,
    personnel_id integer NOT NULL,
    transport_type character varying(50) NOT NULL,
    transport_name character varying(100) NOT NULL,
    transport_code character varying(20),
    departure_location character varying(100) NOT NULL,
    destination_location character varying(100) NOT NULL,
    departure_time timestamp with time zone NOT NULL,
    arrival_time timestamp with time zone,
    return_time timestamp with time zone,
    seat_number character varying(10),
    cabin_number character varying(20),
    purpose character varying(100),
    status character varying(20),
    booked_at timestamp with time zone DEFAULT now() NOT NULL,
    booked_by integer,
    notes text
);


--
-- Name: transport_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_assignments_id_seq OWNED BY public.transport_assignments.id;


--
-- Name: transport_crew; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport_crew (
    id integer NOT NULL,
    transport_id integer NOT NULL,
    personnel_id integer NOT NULL,
    role character varying(50) NOT NULL,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone,
    status character varying(20),
    certification_number character varying(50),
    certification_expiry date,
    medical_expiry date,
    experience_hours double precision,
    flight_hours double precision,
    last_flight_date timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transport_crew_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_crew_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_crew_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_crew_id_seq OWNED BY public.transport_crew.id;


--
-- Name: transport_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_id_seq OWNED BY public.transport.id;


--
-- Name: transport_inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport_inventory (
    id integer NOT NULL,
    transport_id integer NOT NULL,
    item_name character varying(100) NOT NULL,
    item_type character varying(50) NOT NULL,
    item_description text,
    quantity integer,
    unit_of_measure character varying(20),
    location_on_transport character varying(50),
    expiry_date date,
    last_inspected timestamp with time zone,
    condition_status character varying(20),
    replacement_cost double precision,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transport_inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_inventory_id_seq OWNED BY public.transport_inventory.id;


--
-- Name: transport_maintenance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport_maintenance (
    id integer NOT NULL,
    transport_id integer NOT NULL,
    maintenance_type smallint NOT NULL,
    description text NOT NULL,
    scheduled_date timestamp with time zone NOT NULL,
    completed_date timestamp with time zone,
    status character varying(20),
    technician character varying(100),
    cost double precision,
    parts_used jsonb,
    next_maintenance timestamp with time zone,
    maintenance_hours double precision,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transport_maintenance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_maintenance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_maintenance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_maintenance_id_seq OWNED BY public.transport_maintenance.id;


--
-- Name: transport_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transport_schedule (
    id integer NOT NULL,
    transport_id integer NOT NULL,
    schedule_type character varying(20) NOT NULL,
    departure_location character varying(100) NOT NULL,
    arrival_location character varying(100) NOT NULL,
    departure_time timestamp with time zone NOT NULL,
    arrival_time timestamp with time zone,
    actual_departure_time timestamp with time zone,
    actual_arrival_time timestamp with time zone,
    frequency character varying(20),
    end_date timestamp with time zone,
    status character varying(20),
    priority character varying(20),
    passenger_manifest jsonb,
    cargo_manifest jsonb,
    crew jsonb,
    estimated_cost double precision,
    actual_cost double precision,
    weather_requirements character varying(100),
    special_requirements text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transport_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transport_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transport_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transport_schedule_id_seq OWNED BY public.transport_schedule.id;


--
-- Name: user_extensions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_extensions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    default_role_id integer,
    avatar_url character varying(500),
    phone character varying(20),
    last_login_ip character varying(45),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_extensions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_extensions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_extensions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_extensions_id_seq OWNED BY public.user_extensions.id;


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role_id integer NOT NULL,
    assigned_by integer,
    assigned_at timestamp with time zone DEFAULT now(),
    is_active boolean
);


--
-- Name: user_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_roles_id_seq OWNED BY public.user_roles.id;


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    session_token character varying(255) NOT NULL,
    refresh_token character varying(255),
    device_info text,
    ip_address character varying(45),
    is_active boolean DEFAULT true,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_sessions_id_seq OWNED BY public.user_sessions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(200),
    hashed_password character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_superuser boolean DEFAULT false NOT NULL,
    is_verified boolean DEFAULT false NOT NULL,
    phone character varying(20),
    avatar character varying(500),
    last_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    is_global_admin boolean DEFAULT false
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vendor_compliance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_compliance (
    id integer NOT NULL,
    vendor_id integer NOT NULL,
    compliance_type character varying(50) NOT NULL,
    compliance_status character varying(20) NOT NULL,
    compliance_date timestamp with time zone NOT NULL,
    expiry_date timestamp with time zone,
    certifying_authority character varying(100),
    certificate_number character varying(100),
    assessment_score double precision,
    assessment_notes text,
    corrective_actions json,
    follow_up_date timestamp with time zone,
    certificate_path character varying(500),
    supporting_documents json,
    assessed_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: vendor_compliance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_compliance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_compliance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_compliance_id_seq OWNED BY public.vendor_compliance.id;


--
-- Name: vendor_contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_contracts (
    id integer NOT NULL,
    vendor_id integer NOT NULL,
    contract_number character varying(50) NOT NULL,
    contract_name character varying(200) NOT NULL,
    contract_type character varying(50) NOT NULL,
    status character varying(20) DEFAULT 'DRAFT'::character varying,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone NOT NULL,
    renewal_date timestamp with time zone,
    notice_period_days integer DEFAULT 30,
    total_value double precision,
    currency character varying(3) DEFAULT 'USD'::character varying,
    payment_terms character varying(100),
    billing_frequency character varying(20),
    sla_requirements json,
    penalty_clauses json,
    scope_of_work text,
    deliverables json,
    key_performance_indicators json,
    contract_manager integer,
    legal_reviewer integer,
    approved_by integer,
    approved_at timestamp with time zone,
    performance_score double precision DEFAULT 0.0,
    compliance_score double precision DEFAULT 0.0,
    last_performance_review timestamp with time zone,
    created_by integer NOT NULL,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: vendor_contracts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_contracts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_contracts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_contracts_id_seq OWNED BY public.vendor_contracts.id;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id integer NOT NULL,
    vendor_code character varying(50) NOT NULL,
    vendor_name character varying(200) NOT NULL,
    vendor_type character varying(50) NOT NULL,
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    contact_person character varying(100),
    email character varying(100),
    phone character varying(20),
    mobile character varying(20),
    fax character varying(20),
    address_line1 character varying(200),
    address_line2 character varying(200),
    city character varying(100),
    state character varying(100),
    country character varying(100),
    postal_code character varying(20),
    business_registration character varying(100),
    tax_id character varying(50),
    website character varying(200),
    description text,
    services_offered json,
    service_areas json,
    certifications json,
    payment_terms character varying(100),
    credit_limit double precision,
    currency character varying(3) DEFAULT 'USD'::character varying,
    compliance_status character varying(20) DEFAULT 'PENDING_REVIEW'::character varying,
    last_compliance_check timestamp with time zone,
    next_compliance_due timestamp with time zone,
    risk_rating character varying(10),
    performance_score double precision DEFAULT 0.0,
    total_contracts integer DEFAULT 0,
    active_contracts integer DEFAULT 0,
    created_by integer NOT NULL,
    updated_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    notes text
);


--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: vis_blacklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vis_blacklist (
    id integer NOT NULL,
    full_name character varying(100),
    id_no character varying(50) NOT NULL,
    phone character varying(20),
    email character varying(100),
    reason character varying(255) NOT NULL,
    added_by integer,
    added_time timestamp with time zone DEFAULT now(),
    is_active boolean
);


--
-- Name: vis_blacklist_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vis_blacklist_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vis_blacklist_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vis_blacklist_id_seq OWNED BY public.vis_blacklist.id;


--
-- Name: vis_pre_registration; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vis_pre_registration (
    id bigint NOT NULL,
    visitor_id bigint,
    host_emp_id integer NOT NULL,
    visit_date date NOT NULL,
    visit_time_start time without time zone,
    visit_time_end time without time zone,
    purpose character varying(255),
    area_id integer,
    vehicle_no character varying(20),
    qr_code character varying(100) NOT NULL,
    status smallint,
    approval_time timestamp with time zone,
    approval_by integer,
    approval_note character varying(255),
    safety_induction_done boolean,
    induction_doc character varying(255),
    contractor_visitor boolean,
    created_by integer,
    created_time timestamp with time zone DEFAULT now(),
    updated_time timestamp with time zone DEFAULT now()
);


--
-- Name: vis_pre_registration_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vis_pre_registration_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vis_pre_registration_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vis_pre_registration_id_seq OWNED BY public.vis_pre_registration.id;


--
-- Name: vis_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vis_type (
    id integer NOT NULL,
    type_name character varying(50) NOT NULL,
    access_level_id integer,
    badge_template character varying(100),
    induction_required boolean,
    default_visit_hours integer,
    auto_checkout boolean,
    mustering_zone_id integer,
    contractor_visitor boolean,
    safety_induction_required boolean,
    created_time timestamp with time zone DEFAULT now(),
    is_active boolean
);


--
-- Name: vis_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vis_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vis_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vis_type_id_seq OWNED BY public.vis_type.id;


--
-- Name: vis_visit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vis_visit_log (
    id bigint NOT NULL,
    visitor_id bigint NOT NULL,
    pre_reg_id bigint,
    host_emp_id integer,
    check_in_time timestamp with time zone NOT NULL,
    check_out_time timestamp with time zone,
    card_no character varying(20),
    device_sn character varying(20),
    badge_printed boolean,
    status smallint,
    area_id integer,
    mustering_zone_id integer,
    mustering_status smallint,
    overstay_alert_sent boolean,
    created_by integer,
    created_time timestamp with time zone DEFAULT now()
);


--
-- Name: vis_visit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vis_visit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vis_visit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vis_visit_log_id_seq OWNED BY public.vis_visit_log.id;


--
-- Name: vis_visitor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vis_visitor (
    id bigint NOT NULL,
    visitor_code character varying(20) NOT NULL,
    full_name character varying(100) NOT NULL,
    phone character varying(20),
    email character varying(100),
    company character varying(100),
    id_type smallint,
    id_no character varying(50),
    photo character varying(255),
    signature character varying(255),
    visitor_type_id integer,
    is_blacklist boolean,
    blacklist_reason character varying(255),
    vendor_id integer,
    safety_induction_done boolean,
    induction_doc character varying(255),
    created_time timestamp with time zone DEFAULT now(),
    updated_time timestamp with time zone DEFAULT now()
);


--
-- Name: vis_visitor_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vis_visitor_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vis_visitor_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vis_visitor_id_seq OWNED BY public.vis_visitor.id;


--
-- Name: zone_personnel_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zone_personnel_assignments (
    id integer NOT NULL,
    zone_id integer NOT NULL,
    personnel_id integer NOT NULL,
    role character varying(100),
    access_level character varying(20) DEFAULT 'STANDARD'::character varying,
    is_primary_zone boolean DEFAULT false,
    assigned_at timestamp with time zone DEFAULT now(),
    unassigned_at timestamp with time zone,
    is_permanent boolean DEFAULT false,
    access_times jsonb,
    device_access jsonb,
    safety_briefing_completed boolean DEFAULT false,
    safety_briefing_date timestamp with time zone,
    certifications_verified boolean DEFAULT false,
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    approved_by integer,
    approved_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: zone_personnel_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zone_personnel_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zone_personnel_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zone_personnel_assignments_id_seq OWNED BY public.zone_personnel_assignments.id;


--
-- Name: zone_personnel_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zone_personnel_tracking (
    id integer NOT NULL,
    zone_id integer NOT NULL,
    personnel_id integer,
    emp_code character varying(20) NOT NULL,
    device_sn character varying(50) NOT NULL,
    event_type character varying(20) DEFAULT 'CLOCK_IN'::character varying,
    punch_time timestamp with time zone NOT NULL,
    previous_zone_id integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: zone_personnel_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zone_personnel_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zone_personnel_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zone_personnel_tracking_id_seq OWNED BY public.zone_personnel_tracking.id;


--
-- Name: zone_reader_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zone_reader_assignments (
    id integer NOT NULL,
    zone_id integer NOT NULL,
    reader_id integer NOT NULL,
    assignment_type character varying(50) DEFAULT 'PERMANENT'::character varying,
    status character varying(20) DEFAULT 'active'::character varying,
    is_primary boolean DEFAULT false,
    assigned_at timestamp with time zone DEFAULT now(),
    unassigned_at timestamp with time zone,
    expires_at timestamp with time zone,
    access_level character varying(20) DEFAULT 'STANDARD'::character varying,
    access_schedule jsonb,
    reader_config jsonb,
    last_heartbeat timestamp with time zone,
    last_activity timestamp with time zone,
    error_count integer DEFAULT 0,
    notes text,
    assigned_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: zone_reader_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zone_reader_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zone_reader_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zone_reader_assignments_id_seq OWNED BY public.zone_reader_assignments.id;


--
-- Name: zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zones (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    code character varying(20) NOT NULL,
    zone_type character varying(30) DEFAULT 'WORK_AREA'::character varying NOT NULL,
    description text,
    status character varying(20) DEFAULT 'active'::character varying,
    state character varying(100),
    address text,
    latitude character varying(20),
    longitude character varying(20),
    max_capacity integer,
    current_occupancy integer DEFAULT 0,
    current_personnel_count integer DEFAULT 0,
    hazard_level character varying(20) DEFAULT 'LOW'::character varying,
    safety_level character varying(20) DEFAULT 'NORMAL'::character varying,
    access_level character varying(20) DEFAULT 'RESTRICTED'::character varying,
    device_count integer DEFAULT 0,
    zone_manager_id integer,
    contact_person character varying(255),
    contact_phone character varying(20),
    zkteco_sync_enabled boolean DEFAULT true,
    last_sync_at timestamp with time zone,
    floor_plan_url character varying(500),
    floor_plan_file_path character varying(500),
    floor_plan_filename character varying(255),
    floor_plan_uploaded_at timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    parent_zone_id integer,
    display_color character varying(20),
    tile_position character varying(20) DEFAULT 'auto'::character varying,
    evac_point character varying(100),
    evac_gps character varying(50),
    reader_sn character varying(50),
    map_x double precision,
    map_y double precision,
    map_connections text
);


--
-- Name: zones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zones_id_seq OWNED BY public.zones.id;


--
-- Name: acc_antipassback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_antipassback ALTER COLUMN id SET DEFAULT nextval('public.acc_antipassback_id_seq'::regclass);


--
-- Name: acc_door id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_door ALTER COLUMN id SET DEFAULT nextval('public.acc_door_id_seq'::regclass);


--
-- Name: acc_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_event ALTER COLUMN id SET DEFAULT nextval('public.acc_event_id_seq'::regclass);


--
-- Name: acc_first_card id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_first_card ALTER COLUMN id SET DEFAULT nextval('public.acc_first_card_id_seq'::regclass);


--
-- Name: acc_guard_tour id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour ALTER COLUMN id SET DEFAULT nextval('public.acc_guard_tour_id_seq'::regclass);


--
-- Name: acc_guard_tour_checkpoint id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_checkpoint ALTER COLUMN id SET DEFAULT nextval('public.acc_guard_tour_checkpoint_id_seq'::regclass);


--
-- Name: acc_guard_tour_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_log ALTER COLUMN id SET DEFAULT nextval('public.acc_guard_tour_log_id_seq'::regclass);


--
-- Name: acc_guard_tour_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_schedule ALTER COLUMN id SET DEFAULT nextval('public.acc_guard_tour_schedule_id_seq'::regclass);


--
-- Name: acc_interlock_door id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_door ALTER COLUMN id SET DEFAULT nextval('public.acc_interlock_door_id_seq'::regclass);


--
-- Name: acc_interlock_group id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_group ALTER COLUMN id SET DEFAULT nextval('public.acc_interlock_group_id_seq'::regclass);


--
-- Name: acc_level id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level ALTER COLUMN id SET DEFAULT nextval('public.acc_level_id_seq'::regclass);


--
-- Name: acc_level_door id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level_door ALTER COLUMN id SET DEFAULT nextval('public.acc_level_door_id_seq'::regclass);


--
-- Name: acc_linkage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_linkage ALTER COLUMN id SET DEFAULT nextval('public.acc_linkage_id_seq'::regclass);


--
-- Name: acc_multi_card id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card ALTER COLUMN id SET DEFAULT nextval('public.acc_multi_card_id_seq'::regclass);


--
-- Name: acc_multi_card_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card_user ALTER COLUMN id SET DEFAULT nextval('public.acc_multi_card_user_id_seq'::regclass);


--
-- Name: acc_passback_rule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_passback_rule ALTER COLUMN id SET DEFAULT nextval('public.acc_passback_rule_id_seq'::regclass);


--
-- Name: acc_timezone id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_timezone ALTER COLUMN id SET DEFAULT nextval('public.acc_timezone_id_seq'::regclass);


--
-- Name: acc_userauthorize id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_userauthorize ALTER COLUMN id SET DEFAULT nextval('public.acc_userauthorize_id_seq'::regclass);


--
-- Name: acc_visitor_access id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_visitor_access ALTER COLUMN id SET DEFAULT nextval('public.acc_visitor_access_id_seq'::regclass);


--
-- Name: acc_zone id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone ALTER COLUMN id SET DEFAULT nextval('public.acc_zone_id_seq'::regclass);


--
-- Name: acc_zone_door id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone_door ALTER COLUMN id SET DEFAULT nextval('public.acc_zone_door_id_seq'::regclass);


--
-- Name: access_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_logs ALTER COLUMN id SET DEFAULT nextval('public.access_logs_id_seq'::regclass);


--
-- Name: acgroup id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acgroup ALTER COLUMN id SET DEFAULT nextval('public.acgroup_id_seq'::regclass);


--
-- Name: appraisal_cycles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appraisal_cycles ALTER COLUMN id SET DEFAULT nextval('public.appraisal_cycles_id_seq'::regclass);


--
-- Name: att_exception id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_exception ALTER COLUMN id SET DEFAULT nextval('public.att_exception_id_seq'::regclass);


--
-- Name: att_holiday id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_holiday ALTER COLUMN id SET DEFAULT nextval('public.att_holiday_id_seq'::regclass);


--
-- Name: att_leave id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave ALTER COLUMN id SET DEFAULT nextval('public.att_leave_id_seq1'::regclass);


--
-- Name: att_leave_old id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave_old ALTER COLUMN id SET DEFAULT nextval('public.att_leave_id_seq'::regclass);


--
-- Name: att_leave_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave_type ALTER COLUMN id SET DEFAULT nextval('public.att_leave_type_id_seq'::regclass);


--
-- Name: att_manual_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_manual_log ALTER COLUMN id SET DEFAULT nextval('public.att_manual_log_id_seq'::regclass);


--
-- Name: att_overtime id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_overtime ALTER COLUMN id SET DEFAULT nextval('public.att_overtime_id_seq'::regclass);


--
-- Name: att_overtime_rule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_overtime_rule ALTER COLUMN id SET DEFAULT nextval('public.att_overtime_rule_id_seq'::regclass);


--
-- Name: att_report id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report ALTER COLUMN id SET DEFAULT nextval('public.att_report_id_seq'::regclass);


--
-- Name: att_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_schedule ALTER COLUMN id SET DEFAULT nextval('public.att_schedule_id_seq'::regclass);


--
-- Name: att_shift id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift ALTER COLUMN id SET DEFAULT nextval('public.att_shift_id_seq'::regclass);


--
-- Name: att_shift_timetable id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift_timetable ALTER COLUMN id SET DEFAULT nextval('public.att_shift_timetable_id_seq'::regclass);


--
-- Name: att_timetable id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_timetable ALTER COLUMN id SET DEFAULT nextval('public.att_timetable_id_seq'::regclass);


--
-- Name: attendance_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs ALTER COLUMN id SET DEFAULT nextval('public.attendance_logs_id_seq'::regclass);


--
-- Name: attribute_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_templates ALTER COLUMN id SET DEFAULT nextval('public.attribute_templates_id_seq'::regclass);


--
-- Name: attribute_validations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_validations ALTER COLUMN id SET DEFAULT nextval('public.attribute_validations_id_seq'::regclass);


--
-- Name: auth_permission id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_permission_id_seq'::regclass);


--
-- Name: auth_role id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role ALTER COLUMN id SET DEFAULT nextval('public.auth_role_id_seq'::regclass);


--
-- Name: auth_role_permission id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_role_permission_id_seq'::regclass);


--
-- Name: auth_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq'::regclass);


--
-- Name: auth_user_role id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_role ALTER COLUMN id SET DEFAULT nextval('public.auth_user_role_id_seq'::regclass);


--
-- Name: base_company id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_company ALTER COLUMN id SET DEFAULT nextval('public.base_company_id_seq'::regclass);


--
-- Name: base_operationlog id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_operationlog ALTER COLUMN id SET DEFAULT nextval('public.base_operationlog_id_seq'::regclass);


--
-- Name: bc_integration_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bc_integration_config ALTER COLUMN id SET DEFAULT nextval('public.bc_integration_config_id_seq'::regclass);


--
-- Name: bc_sync_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bc_sync_log ALTER COLUMN id SET DEFAULT nextval('public.bc_sync_log_id_seq'::regclass);


--
-- Name: benefit_plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benefit_plans ALTER COLUMN id SET DEFAULT nextval('public.benefit_plans_id_seq'::regclass);


--
-- Name: biometric_devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_devices ALTER COLUMN id SET DEFAULT nextval('public.biometric_devices_id_seq'::regclass);


--
-- Name: biometric_enrollment_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_enrollment_sessions ALTER COLUMN id SET DEFAULT nextval('public.biometric_enrollment_sessions_id_seq'::regclass);


--
-- Name: biometric_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_templates ALTER COLUMN id SET DEFAULT nextval('public.biometric_templates_id_seq'::regclass);


--
-- Name: biometric_verification_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_verification_logs ALTER COLUMN id SET DEFAULT nextval('public.biometric_verification_logs_id_seq'::regclass);


--
-- Name: biotime_access_levels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_levels ALTER COLUMN id SET DEFAULT nextval('public.biotime_access_levels_id_seq'::regclass);


--
-- Name: biotime_access_schedules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_schedules ALTER COLUMN id SET DEFAULT nextval('public.biotime_access_schedules_id_seq'::regclass);


--
-- Name: biotime_biometric_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_biometric_templates ALTER COLUMN id SET DEFAULT nextval('public.biotime_biometric_templates_id_seq'::regclass);


--
-- Name: biotime_conflict_resolutions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_conflict_resolutions ALTER COLUMN id SET DEFAULT nextval('public.biotime_conflict_resolutions_id_seq'::regclass);


--
-- Name: biotime_device_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_device_groups ALTER COLUMN id SET DEFAULT nextval('public.biotime_device_groups_id_seq'::regclass);


--
-- Name: biotime_devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_devices ALTER COLUMN id SET DEFAULT nextval('public.biotime_devices_id_seq'::regclass);


--
-- Name: biotime_sync_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_sync_logs ALTER COLUMN id SET DEFAULT nextval('public.biotime_sync_logs_id_seq'::regclass);


--
-- Name: certification_audits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_audits ALTER COLUMN id SET DEFAULT nextval('public.certification_audits_id_seq'::regclass);


--
-- Name: certification_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_templates ALTER COLUMN id SET DEFAULT nextval('public.certification_templates_id_seq'::regclass);


--
-- Name: certifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certifications ALTER COLUMN id SET DEFAULT nextval('public.certifications_id_seq'::regclass);


--
-- Name: checkinout id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkinout ALTER COLUMN id SET DEFAULT nextval('public.checkinout_id_seq'::regclass);


--
-- Name: contract_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assignments ALTER COLUMN id SET DEFAULT nextval('public.contract_assignments_id_seq'::regclass);


--
-- Name: contractor_compliance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractor_compliance ALTER COLUMN id SET DEFAULT nextval('public.contractor_compliance_id_seq'::regclass);


--
-- Name: contractors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors ALTER COLUMN id SET DEFAULT nextval('public.contractors_id_seq'::regclass);


--
-- Name: custom_attribute_values id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values ALTER COLUMN id SET DEFAULT nextval('public.custom_attribute_values_id_seq'::regclass);


--
-- Name: custom_attributes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attributes ALTER COLUMN id SET DEFAULT nextval('public.custom_attributes_id_seq'::regclass);


--
-- Name: department_personnel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.department_personnel ALTER COLUMN id SET DEFAULT nextval('public.department_personnel_id_seq'::regclass);


--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: device_blacklist id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_blacklist ALTER COLUMN id SET DEFAULT nextval('public.device_blacklist_id_seq'::regclass);


--
-- Name: device_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_events ALTER COLUMN id SET DEFAULT nextval('public.device_events_id_seq'::regclass);


--
-- Name: device_maintenance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_maintenance ALTER COLUMN id SET DEFAULT nextval('public.device_maintenance_id_seq'::regclass);


--
-- Name: device_schedules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_schedules ALTER COLUMN id SET DEFAULT nextval('public.device_schedules_id_seq'::regclass);


--
-- Name: devicemap id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devicemap ALTER COLUMN id SET DEFAULT nextval('public.devicemap_id_seq'::regclass);


--
-- Name: devices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices ALTER COLUMN id SET DEFAULT nextval('public.devices_id_seq'::regclass);


--
-- Name: disciplinary_cases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disciplinary_cases ALTER COLUMN id SET DEFAULT nextval('public.disciplinary_cases_id_seq'::regclass);


--
-- Name: emergency_device id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device ALTER COLUMN id SET DEFAULT nextval('public.emergency_device_id_seq'::regclass);


--
-- Name: emergency_device_command id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command ALTER COLUMN id SET DEFAULT nextval('public.emergency_device_command_id_seq'::regclass);


--
-- Name: emergency_device_enhanced id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_enhanced ALTER COLUMN id SET DEFAULT nextval('public.emergency_device_enhanced_id_seq'::regclass);


--
-- Name: emergency_device_maintenance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance ALTER COLUMN id SET DEFAULT nextval('public.emergency_device_maintenance_id_seq'::regclass);


--
-- Name: emergency_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event ALTER COLUMN id SET DEFAULT nextval('public.emergency_event_id_seq'::regclass);


--
-- Name: emergency_event_enhanced id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event_enhanced ALTER COLUMN id SET DEFAULT nextval('public.emergency_event_enhanced_id_seq'::regclass);


--
-- Name: emergency_notification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification ALTER COLUMN id SET DEFAULT nextval('public.emergency_notification_id_seq'::regclass);


--
-- Name: emergency_notification_enhanced id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification_enhanced ALTER COLUMN id SET DEFAULT nextval('public.emergency_notification_enhanced_id_seq'::regclass);


--
-- Name: emergency_panic_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log ALTER COLUMN id SET DEFAULT nextval('public.emergency_panic_log_id_seq'::regclass);


--
-- Name: emergency_panic_log_enhanced id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log_enhanced ALTER COLUMN id SET DEFAULT nextval('public.emergency_panic_log_enhanced_id_seq'::regclass);


--
-- Name: emergency_plan id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_plan ALTER COLUMN id SET DEFAULT nextval('public.emergency_plan_id_seq'::regclass);


--
-- Name: emergency_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_template ALTER COLUMN id SET DEFAULT nextval('public.emergency_template_id_seq'::regclass);


--
-- Name: employee_benefits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_benefits ALTER COLUMN id SET DEFAULT nextval('public.employee_benefits_id_seq'::regclass);


--
-- Name: employment_contracts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employment_contracts ALTER COLUMN id SET DEFAULT nextval('public.employment_contracts_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: face id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.face ALTER COLUMN id SET DEFAULT nextval('public.face_id_seq'::regclass);


--
-- Name: fingerprint id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fingerprint ALTER COLUMN id SET DEFAULT nextval('public.fingerprint_id_seq'::regclass);


--
-- Name: flight_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flight_log ALTER COLUMN id SET DEFAULT nextval('public.flight_log_id_seq'::regclass);


--
-- Name: holiday id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holiday ALTER COLUMN id SET DEFAULT nextval('public.holiday_id_seq'::regclass);


--
-- Name: hr_integration_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_integration_config ALTER COLUMN id SET DEFAULT nextval('public.hr_integration_config_id_seq'::regclass);


--
-- Name: hr_sync_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_sync_log ALTER COLUMN id SET DEFAULT nextval('public.hr_sync_log_id_seq'::regclass);


--
-- Name: iclock_bio_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_bio_template ALTER COLUMN id SET DEFAULT nextval('public.iclock_bio_template_id_seq'::regclass);


--
-- Name: iclock_devcmd id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_devcmd ALTER COLUMN id SET DEFAULT nextval('public.iclock_devcmd_id_seq'::regclass);


--
-- Name: iclock_operlog id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_operlog ALTER COLUMN id SET DEFAULT nextval('public.iclock_operlog_id_seq'::regclass);


--
-- Name: iclock_terminal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_terminal ALTER COLUMN id SET DEFAULT nextval('public.iclock_terminal_id_seq'::regclass);


--
-- Name: iclock_transaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_transaction ALTER COLUMN id SET DEFAULT nextval('public.iclock_transaction_id_seq'::regclass);


--
-- Name: leave_balance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_balance ALTER COLUMN id SET DEFAULT nextval('public.leave_balance_id_seq'::regclass);


--
-- Name: leave_blackout id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_blackout ALTER COLUMN id SET DEFAULT nextval('public.leave_blackout_id_seq'::regclass);


--
-- Name: leave_management id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_management ALTER COLUMN id SET DEFAULT nextval('public.leave_management_id_seq'::regclass);


--
-- Name: manifest_entry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manifest_entry ALTER COLUMN id SET DEFAULT nextval('public.manifest_entry_id_seq'::regclass);


--
-- Name: mtd_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_audit_log ALTER COLUMN id SET DEFAULT nextval('public.mtd_audit_log_id_seq'::regclass);


--
-- Name: mtd_cert_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_cert_type ALTER COLUMN id SET DEFAULT nextval('public.mtd_cert_type_id_seq'::regclass);


--
-- Name: mtd_certification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification ALTER COLUMN id SET DEFAULT nextval('public.mtd_certification_id_seq'::regclass);


--
-- Name: mtd_compliance_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_compliance_log ALTER COLUMN id SET DEFAULT nextval('public.mtd_compliance_log_id_seq'::regclass);


--
-- Name: mtd_induction_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record ALTER COLUMN id SET DEFAULT nextval('public.mtd_induction_record_id_seq'::regclass);


--
-- Name: mtd_induction_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_template ALTER COLUMN id SET DEFAULT nextval('public.mtd_induction_template_id_seq'::regclass);


--
-- Name: mtd_medical_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_medical_record ALTER COLUMN id SET DEFAULT nextval('public.mtd_medical_record_id_seq'::regclass);


--
-- Name: mtd_ppe_issue id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_issue ALTER COLUMN id SET DEFAULT nextval('public.mtd_ppe_issue_id_seq'::regclass);


--
-- Name: mtd_ppe_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_type ALTER COLUMN id SET DEFAULT nextval('public.mtd_ppe_type_id_seq'::regclass);


--
-- Name: mtg_action_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_action_item ALTER COLUMN id SET DEFAULT nextval('public.mtg_action_item_id_seq'::regclass);


--
-- Name: mtg_attendance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendance ALTER COLUMN id SET DEFAULT nextval('public.mtg_attendance_id_seq'::regclass);


--
-- Name: mtg_attendee id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee ALTER COLUMN id SET DEFAULT nextval('public.mtg_attendee_id_seq'::regclass);


--
-- Name: mtg_booking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking ALTER COLUMN id SET DEFAULT nextval('public.mtg_booking_id_seq'::regclass);


--
-- Name: mtg_equipment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_equipment ALTER COLUMN id SET DEFAULT nextval('public.mtg_equipment_id_seq'::regclass);


--
-- Name: mtg_minutes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_minutes ALTER COLUMN id SET DEFAULT nextval('public.mtg_minutes_id_seq'::regclass);


--
-- Name: mtg_room id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_room ALTER COLUMN id SET DEFAULT nextval('public.mtg_room_id_seq'::regclass);


--
-- Name: mustering_drill_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_drill_schedule ALTER COLUMN id SET DEFAULT nextval('public.mustering_drill_schedule_id_seq'::regclass);


--
-- Name: mustering_escalation_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_escalation_record ALTER COLUMN id SET DEFAULT nextval('public.mustering_escalation_record_id_seq'::regclass);


--
-- Name: mustering_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_event ALTER COLUMN id SET DEFAULT nextval('public.mustering_event_id_seq'::regclass);


--
-- Name: mustering_expected id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_expected ALTER COLUMN id SET DEFAULT nextval('public.mustering_expected_id_seq'::regclass);


--
-- Name: mustering_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_log ALTER COLUMN id SET DEFAULT nextval('public.mustering_log_id_seq'::regclass);


--
-- Name: mustering_search_sweep id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_search_sweep ALTER COLUMN id SET DEFAULT nextval('public.mustering_search_sweep_id_seq'::regclass);


--
-- Name: mustering_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_template ALTER COLUMN id SET DEFAULT nextval('public.mustering_template_id_seq'::regclass);


--
-- Name: onboarding_checklists id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_checklists ALTER COLUMN id SET DEFAULT nextval('public.onboarding_checklists_id_seq'::regclass);


--
-- Name: onboarding_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_documents ALTER COLUMN id SET DEFAULT nextval('public.onboarding_documents_id_seq'::regclass);


--
-- Name: onboarding_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_notifications ALTER COLUMN id SET DEFAULT nextval('public.onboarding_notifications_id_seq'::regclass);


--
-- Name: onboarding_task id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task ALTER COLUMN id SET DEFAULT nextval('public.onboarding_task_id_seq'::regclass);


--
-- Name: onboarding_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_tasks ALTER COLUMN id SET DEFAULT nextval('public.onboarding_tasks_id_seq'::regclass);


--
-- Name: onboarding_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_templates ALTER COLUMN id SET DEFAULT nextval('public.onboarding_templates_id_seq'::regclass);


--
-- Name: onboardings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings ALTER COLUMN id SET DEFAULT nextval('public.onboardings_id_seq'::regclass);


--
-- Name: overtime_management id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_management ALTER COLUMN id SET DEFAULT nextval('public.overtime_management_id_seq'::regclass);


--
-- Name: overtime_record id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_record ALTER COLUMN id SET DEFAULT nextval('public.overtime_record_id_seq'::regclass);


--
-- Name: overtime_rule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rule ALTER COLUMN id SET DEFAULT nextval('public.overtime_rule_id_seq'::regclass);


--
-- Name: overtime_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rules ALTER COLUMN id SET DEFAULT nextval('public.overtime_rules_id_seq'::regclass);


--
-- Name: pay_attendance_mapping id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_attendance_mapping ALTER COLUMN id SET DEFAULT nextval('public.pay_attendance_mapping_id_seq'::regclass);


--
-- Name: pay_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_audit_log ALTER COLUMN id SET DEFAULT nextval('public.pay_audit_log_id_seq'::regclass);


--
-- Name: pay_bank_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_bank_config ALTER COLUMN id SET DEFAULT nextval('public.pay_bank_config_id_seq'::regclass);


--
-- Name: pay_calculation_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_calculation_log ALTER COLUMN id SET DEFAULT nextval('public.pay_calculation_log_id_seq'::regclass);


--
-- Name: pay_contractor_rate id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_contractor_rate ALTER COLUMN id SET DEFAULT nextval('public.pay_contractor_rate_id_seq'::regclass);


--
-- Name: pay_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_item ALTER COLUMN id SET DEFAULT nextval('public.pay_item_id_seq'::regclass);


--
-- Name: pay_loan id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan ALTER COLUMN id SET DEFAULT nextval('public.pay_loan_id_seq'::regclass);


--
-- Name: pay_loan_deduction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction ALTER COLUMN id SET DEFAULT nextval('public.pay_loan_deduction_id_seq'::regclass);


--
-- Name: pay_payslip_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_payslip_template ALTER COLUMN id SET DEFAULT nextval('public.pay_payslip_template_id_seq'::regclass);


--
-- Name: pay_period id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_period ALTER COLUMN id SET DEFAULT nextval('public.pay_period_id_seq'::regclass);


--
-- Name: pay_salary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary ALTER COLUMN id SET DEFAULT nextval('public.pay_salary_id_seq'::regclass);


--
-- Name: pay_salary_item id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary_item ALTER COLUMN id SET DEFAULT nextval('public.pay_salary_item_id_seq'::regclass);


--
-- Name: pay_structure id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure ALTER COLUMN id SET DEFAULT nextval('public.pay_structure_id_seq'::regclass);


--
-- Name: pay_structure_assign id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure_assign ALTER COLUMN id SET DEFAULT nextval('public.pay_structure_assign_id_seq'::regclass);


--
-- Name: pay_zone_allowance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_zone_allowance ALTER COLUMN id SET DEFAULT nextval('public.pay_zone_allowance_id_seq'::regclass);


--
-- Name: performance_appraisals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_appraisals ALTER COLUMN id SET DEFAULT nextval('public.performance_appraisals_id_seq'::regclass);


--
-- Name: permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions ALTER COLUMN id SET DEFAULT nextval('public.permissions_id_seq'::regclass);


--
-- Name: personnel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel ALTER COLUMN id SET DEFAULT nextval('public.personnel_id_seq'::regclass);


--
-- Name: personnel_area id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_area ALTER COLUMN id SET DEFAULT nextval('public.personnel_area_id_seq'::regclass);


--
-- Name: personnel_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_assignments ALTER COLUMN id SET DEFAULT nextval('public.personnel_assignments_id_seq'::regclass);


--
-- Name: personnel_department id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_department ALTER COLUMN id SET DEFAULT nextval('public.personnel_department_id_seq'::regclass);


--
-- Name: personnel_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_documents ALTER COLUMN id SET DEFAULT nextval('public.personnel_documents_id_seq'::regclass);


--
-- Name: personnel_employee id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_employee ALTER COLUMN id SET DEFAULT nextval('public.personnel_employee_id_seq'::regclass);


--
-- Name: pob_status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pob_status ALTER COLUMN id SET DEFAULT nextval('public.pob_status_id_seq'::regclass);


--
-- Name: position_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_assignments ALTER COLUMN id SET DEFAULT nextval('public.position_assignments_id_seq'::regclass);


--
-- Name: position_levels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_levels ALTER COLUMN id SET DEFAULT nextval('public.position_levels_id_seq'::regclass);


--
-- Name: position_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_templates ALTER COLUMN id SET DEFAULT nextval('public.position_templates_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: promotion_transfers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promotion_transfers ALTER COLUMN id SET DEFAULT nextval('public.promotion_transfers_id_seq'::regclass);


--
-- Name: resignation_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_documents ALTER COLUMN id SET DEFAULT nextval('public.resignation_documents_id_seq'::regclass);


--
-- Name: resignation_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_notifications ALTER COLUMN id SET DEFAULT nextval('public.resignation_notifications_id_seq'::regclass);


--
-- Name: resignation_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_tasks ALTER COLUMN id SET DEFAULT nextval('public.resignation_tasks_id_seq'::regclass);


--
-- Name: resignation_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_templates ALTER COLUMN id SET DEFAULT nextval('public.resignation_templates_id_seq'::regclass);


--
-- Name: resignations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations ALTER COLUMN id SET DEFAULT nextval('public.resignations_id_seq'::regclass);


--
-- Name: role_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_assignments ALTER COLUMN id SET DEFAULT nextval('public.role_assignments_id_seq'::regclass);


--
-- Name: role_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions ALTER COLUMN id SET DEFAULT nextval('public.role_permissions_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: rpt_export_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_export_log ALTER COLUMN id SET DEFAULT nextval('public.rpt_export_log_id_seq'::regclass);


--
-- Name: rpt_favorite id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_favorite ALTER COLUMN id SET DEFAULT nextval('public.rpt_favorite_id_seq'::regclass);


--
-- Name: rpt_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_schedule ALTER COLUMN id SET DEFAULT nextval('public.rpt_schedule_id_seq'::regclass);


--
-- Name: rpt_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_template ALTER COLUMN id SET DEFAULT nextval('public.rpt_template_id_seq'::regclass);


--
-- Name: rpt_user_preset id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_user_preset ALTER COLUMN id SET DEFAULT nextval('public.rpt_user_preset_id_seq'::regclass);


--
-- Name: schedule_management id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedule_management ALTER COLUMN id SET DEFAULT nextval('public.schedule_management_id_seq'::regclass);


--
-- Name: shift_management id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shift_management ALTER COLUMN id SET DEFAULT nextval('public.shift_management_id_seq'::regclass);


--
-- Name: sn id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sn ALTER COLUMN id SET DEFAULT nextval('public.sn_id_seq'::regclass);


--
-- Name: ssr id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssr ALTER COLUMN id SET DEFAULT nextval('public.ssr_id_seq'::regclass);


--
-- Name: sys_api_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_api_keys ALTER COLUMN id SET DEFAULT nextval('public.sys_api_keys_id_seq'::regclass);


--
-- Name: sys_branding id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_branding ALTER COLUMN id SET DEFAULT nextval('public.sys_branding_id_seq'::regclass);


--
-- Name: sys_consent_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_consent_records ALTER COLUMN id SET DEFAULT nextval('public.sys_consent_records_id_seq'::regclass);


--
-- Name: sys_data_access_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_data_access_logs ALTER COLUMN id SET DEFAULT nextval('public.sys_data_access_logs_id_seq'::regclass);


--
-- Name: sys_db_backups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_db_backups ALTER COLUMN id SET DEFAULT nextval('public.sys_db_backups_id_seq'::regclass);


--
-- Name: sys_email_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_email_templates ALTER COLUMN id SET DEFAULT nextval('public.sys_email_templates_id_seq'::regclass);


--
-- Name: sys_languages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_languages ALTER COLUMN id SET DEFAULT nextval('public.sys_languages_id_seq'::regclass);


--
-- Name: sys_licenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_licenses ALTER COLUMN id SET DEFAULT nextval('public.sys_licenses_id_seq'::regclass);


--
-- Name: sys_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_notifications ALTER COLUMN id SET DEFAULT nextval('public.sys_notifications_id_seq'::regclass);


--
-- Name: sys_parameters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_parameters ALTER COLUMN id SET DEFAULT nextval('public.sys_parameters_id_seq'::regclass);


--
-- Name: sys_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_permissions ALTER COLUMN id SET DEFAULT nextval('public.sys_permissions_id_seq'::regclass);


--
-- Name: sys_renewal_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_renewal_log ALTER COLUMN id SET DEFAULT nextval('public.sys_renewal_log_id_seq'::regclass);


--
-- Name: sys_role_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_role_permissions ALTER COLUMN id SET DEFAULT nextval('public.sys_role_permissions_id_seq'::regclass);


--
-- Name: sys_roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_roles ALTER COLUMN id SET DEFAULT nextval('public.sys_roles_id_seq'::regclass);


--
-- Name: sys_sso_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_sso_configs ALTER COLUMN id SET DEFAULT nextval('public.sys_sso_configs_id_seq'::regclass);


--
-- Name: sys_subscription id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_subscription ALTER COLUMN id SET DEFAULT nextval('public.sys_subscription_id_seq'::regclass);


--
-- Name: sys_translations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_translations ALTER COLUMN id SET DEFAULT nextval('public.sys_translations_id_seq'::regclass);


--
-- Name: sys_user_roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_user_roles ALTER COLUMN id SET DEFAULT nextval('public.sys_user_roles_id_seq'::regclass);


--
-- Name: sys_webhooks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_webhooks ALTER COLUMN id SET DEFAULT nextval('public.sys_webhooks_id_seq'::regclass);


--
-- Name: system_company id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_company ALTER COLUMN id SET DEFAULT nextval('public.system_company_id_seq'::regclass);


--
-- Name: training_courses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_courses ALTER COLUMN id SET DEFAULT nextval('public.training_courses_id_seq'::regclass);


--
-- Name: training_enrollment id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_enrollment ALTER COLUMN id SET DEFAULT nextval('public.training_enrollment_id_seq'::regclass);


--
-- Name: transport id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport ALTER COLUMN id SET DEFAULT nextval('public.transport_id_seq'::regclass);


--
-- Name: transport_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_assignments ALTER COLUMN id SET DEFAULT nextval('public.transport_assignments_id_seq'::regclass);


--
-- Name: transport_crew id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_crew ALTER COLUMN id SET DEFAULT nextval('public.transport_crew_id_seq'::regclass);


--
-- Name: transport_inventory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_inventory ALTER COLUMN id SET DEFAULT nextval('public.transport_inventory_id_seq'::regclass);


--
-- Name: transport_maintenance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_maintenance ALTER COLUMN id SET DEFAULT nextval('public.transport_maintenance_id_seq'::regclass);


--
-- Name: transport_schedule id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_schedule ALTER COLUMN id SET DEFAULT nextval('public.transport_schedule_id_seq'::regclass);


--
-- Name: user_extensions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_extensions ALTER COLUMN id SET DEFAULT nextval('public.user_extensions_id_seq'::regclass);


--
-- Name: user_roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles ALTER COLUMN id SET DEFAULT nextval('public.user_roles_id_seq'::regclass);


--
-- Name: user_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions ALTER COLUMN id SET DEFAULT nextval('public.user_sessions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vendor_compliance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_compliance ALTER COLUMN id SET DEFAULT nextval('public.vendor_compliance_id_seq'::regclass);


--
-- Name: vendor_contracts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_contracts ALTER COLUMN id SET DEFAULT nextval('public.vendor_contracts_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Name: vis_blacklist id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_blacklist ALTER COLUMN id SET DEFAULT nextval('public.vis_blacklist_id_seq'::regclass);


--
-- Name: vis_pre_registration id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration ALTER COLUMN id SET DEFAULT nextval('public.vis_pre_registration_id_seq'::regclass);


--
-- Name: vis_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_type ALTER COLUMN id SET DEFAULT nextval('public.vis_type_id_seq'::regclass);


--
-- Name: vis_visit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log ALTER COLUMN id SET DEFAULT nextval('public.vis_visit_log_id_seq'::regclass);


--
-- Name: vis_visitor id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visitor ALTER COLUMN id SET DEFAULT nextval('public.vis_visitor_id_seq'::regclass);


--
-- Name: zone_personnel_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_assignments ALTER COLUMN id SET DEFAULT nextval('public.zone_personnel_assignments_id_seq'::regclass);


--
-- Name: zone_personnel_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_tracking ALTER COLUMN id SET DEFAULT nextval('public.zone_personnel_tracking_id_seq'::regclass);


--
-- Name: zone_reader_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_reader_assignments ALTER COLUMN id SET DEFAULT nextval('public.zone_reader_assignments_id_seq'::regclass);


--
-- Name: zones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones ALTER COLUMN id SET DEFAULT nextval('public.zones_id_seq'::regclass);


--
-- Name: mtg_booking _meeting_booking_qr_code_uc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking
    ADD CONSTRAINT _meeting_booking_qr_code_uc UNIQUE (qr_code);


--
-- Name: acc_antipassback acc_antipassback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_antipassback
    ADD CONSTRAINT acc_antipassback_pkey PRIMARY KEY (id);


--
-- Name: acc_door acc_door_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_door
    ADD CONSTRAINT acc_door_pkey PRIMARY KEY (id);


--
-- Name: acc_event acc_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_event
    ADD CONSTRAINT acc_event_pkey PRIMARY KEY (id);


--
-- Name: acc_first_card acc_first_card_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_first_card
    ADD CONSTRAINT acc_first_card_pkey PRIMARY KEY (id);


--
-- Name: acc_guard_tour_checkpoint acc_guard_tour_checkpoint_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_checkpoint
    ADD CONSTRAINT acc_guard_tour_checkpoint_pkey PRIMARY KEY (id);


--
-- Name: acc_guard_tour_log acc_guard_tour_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_log
    ADD CONSTRAINT acc_guard_tour_log_pkey PRIMARY KEY (id);


--
-- Name: acc_guard_tour acc_guard_tour_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour
    ADD CONSTRAINT acc_guard_tour_pkey PRIMARY KEY (id);


--
-- Name: acc_guard_tour_schedule acc_guard_tour_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_schedule
    ADD CONSTRAINT acc_guard_tour_schedule_pkey PRIMARY KEY (id);


--
-- Name: acc_guard_tour acc_guard_tour_tour_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour
    ADD CONSTRAINT acc_guard_tour_tour_name_key UNIQUE (tour_name);


--
-- Name: acc_interlock_door acc_interlock_door_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_door
    ADD CONSTRAINT acc_interlock_door_pkey PRIMARY KEY (id);


--
-- Name: acc_interlock_group acc_interlock_group_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_group
    ADD CONSTRAINT acc_interlock_group_group_name_key UNIQUE (group_name);


--
-- Name: acc_interlock_group acc_interlock_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_group
    ADD CONSTRAINT acc_interlock_group_pkey PRIMARY KEY (id);


--
-- Name: acc_level_door acc_level_door_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level_door
    ADD CONSTRAINT acc_level_door_pkey PRIMARY KEY (id);


--
-- Name: acc_level acc_level_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level
    ADD CONSTRAINT acc_level_pkey PRIMARY KEY (id);


--
-- Name: acc_linkage acc_linkage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_linkage
    ADD CONSTRAINT acc_linkage_pkey PRIMARY KEY (id);


--
-- Name: acc_multi_card acc_multi_card_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card
    ADD CONSTRAINT acc_multi_card_pkey PRIMARY KEY (id);


--
-- Name: acc_multi_card_user acc_multi_card_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card_user
    ADD CONSTRAINT acc_multi_card_user_pkey PRIMARY KEY (id);


--
-- Name: acc_passback_rule acc_passback_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_passback_rule
    ADD CONSTRAINT acc_passback_rule_pkey PRIMARY KEY (id);


--
-- Name: acc_timezone acc_timezone_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_timezone
    ADD CONSTRAINT acc_timezone_pkey PRIMARY KEY (id);


--
-- Name: acc_timezone acc_timezone_timezone_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_timezone
    ADD CONSTRAINT acc_timezone_timezone_name_key UNIQUE (timezone_name);


--
-- Name: acc_userauthorize acc_userauthorize_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_userauthorize
    ADD CONSTRAINT acc_userauthorize_pkey PRIMARY KEY (id);


--
-- Name: acc_visitor_access acc_visitor_access_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_visitor_access
    ADD CONSTRAINT acc_visitor_access_pkey PRIMARY KEY (id);


--
-- Name: acc_zone_door acc_zone_door_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone_door
    ADD CONSTRAINT acc_zone_door_pkey PRIMARY KEY (id);


--
-- Name: acc_zone_door acc_zone_door_zone_id_door_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone_door
    ADD CONSTRAINT acc_zone_door_zone_id_door_id_key UNIQUE (zone_id, door_id);


--
-- Name: acc_zone acc_zone_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone
    ADD CONSTRAINT acc_zone_pkey PRIMARY KEY (id);


--
-- Name: acc_zone acc_zone_zone_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone
    ADD CONSTRAINT acc_zone_zone_name_key UNIQUE (zone_name);


--
-- Name: access_logs access_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_pkey PRIMARY KEY (id);


--
-- Name: acgroup acgroup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acgroup
    ADD CONSTRAINT acgroup_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: appraisal_cycles appraisal_cycles_cycle_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appraisal_cycles
    ADD CONSTRAINT appraisal_cycles_cycle_code_key UNIQUE (cycle_code);


--
-- Name: appraisal_cycles appraisal_cycles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appraisal_cycles
    ADD CONSTRAINT appraisal_cycles_pkey PRIMARY KEY (id);


--
-- Name: att_exception att_exception_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_exception
    ADD CONSTRAINT att_exception_pkey PRIMARY KEY (id);


--
-- Name: att_holiday att_holiday_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_holiday
    ADD CONSTRAINT att_holiday_pkey PRIMARY KEY (id);


--
-- Name: att_leave_old att_leave_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave_old
    ADD CONSTRAINT att_leave_pkey PRIMARY KEY (id);


--
-- Name: att_leave att_leave_pkey1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave
    ADD CONSTRAINT att_leave_pkey1 PRIMARY KEY (id);


--
-- Name: att_leave_type att_leave_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave_type
    ADD CONSTRAINT att_leave_type_pkey PRIMARY KEY (id);


--
-- Name: att_manual_log att_manual_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_manual_log
    ADD CONSTRAINT att_manual_log_pkey PRIMARY KEY (id);


--
-- Name: att_overtime att_overtime_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_overtime
    ADD CONSTRAINT att_overtime_pkey PRIMARY KEY (id);


--
-- Name: att_overtime_rule att_overtime_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_overtime_rule
    ADD CONSTRAINT att_overtime_rule_pkey PRIMARY KEY (id);


--
-- Name: att_report att_report_emp_id_att_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report
    ADD CONSTRAINT att_report_emp_id_att_date_key UNIQUE (emp_id, att_date);


--
-- Name: att_report att_report_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report
    ADD CONSTRAINT att_report_pkey PRIMARY KEY (id);


--
-- Name: att_rules att_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_rules
    ADD CONSTRAINT att_rules_pkey PRIMARY KEY (rule_key);


--
-- Name: att_schedule att_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_schedule
    ADD CONSTRAINT att_schedule_pkey PRIMARY KEY (id);


--
-- Name: att_shift att_shift_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift
    ADD CONSTRAINT att_shift_pkey PRIMARY KEY (id);


--
-- Name: att_shift_timetable att_shift_timetable_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift_timetable
    ADD CONSTRAINT att_shift_timetable_pkey PRIMARY KEY (id);


--
-- Name: att_shift_timetable att_shift_timetable_shift_id_day_of_week_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift_timetable
    ADD CONSTRAINT att_shift_timetable_shift_id_day_of_week_key UNIQUE (shift_id, day_of_week);


--
-- Name: att_timetable att_timetable_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_timetable
    ADD CONSTRAINT att_timetable_pkey PRIMARY KEY (id);


--
-- Name: attendance_logs attendance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_pkey PRIMARY KEY (id);


--
-- Name: attribute_templates attribute_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_templates
    ADD CONSTRAINT attribute_templates_pkey PRIMARY KEY (id);


--
-- Name: attribute_validations attribute_validations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_validations
    ADD CONSTRAINT attribute_validations_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_codename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_codename_key UNIQUE (codename);


--
-- Name: auth_permission auth_permission_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_name_key UNIQUE (name);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_role auth_role_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role
    ADD CONSTRAINT auth_role_name_key UNIQUE (name);


--
-- Name: auth_role_permission auth_role_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role_permission
    ADD CONSTRAINT auth_role_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_role_permission auth_role_permission_role_id_permission_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role_permission
    ADD CONSTRAINT auth_role_permission_role_id_permission_id_key UNIQUE (role_id, permission_id);


--
-- Name: auth_role auth_role_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role
    ADD CONSTRAINT auth_role_pkey PRIMARY KEY (id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_role auth_user_role_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_role
    ADD CONSTRAINT auth_user_role_pkey PRIMARY KEY (id);


--
-- Name: auth_user_role auth_user_role_user_id_role_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_role
    ADD CONSTRAINT auth_user_role_user_id_role_id_key UNIQUE (user_id, role_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: base_company base_company_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_company
    ADD CONSTRAINT base_company_pkey PRIMARY KEY (id);


--
-- Name: base_operationlog base_operationlog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_operationlog
    ADD CONSTRAINT base_operationlog_pkey PRIMARY KEY (id);


--
-- Name: bc_integration_config bc_integration_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bc_integration_config
    ADD CONSTRAINT bc_integration_config_pkey PRIMARY KEY (id);


--
-- Name: bc_sync_log bc_sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bc_sync_log
    ADD CONSTRAINT bc_sync_log_pkey PRIMARY KEY (id);


--
-- Name: benefit_plans benefit_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benefit_plans
    ADD CONSTRAINT benefit_plans_pkey PRIMARY KEY (id);


--
-- Name: benefit_plans benefit_plans_plan_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.benefit_plans
    ADD CONSTRAINT benefit_plans_plan_code_key UNIQUE (plan_code);


--
-- Name: biometric_devices biometric_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_devices
    ADD CONSTRAINT biometric_devices_pkey PRIMARY KEY (id);


--
-- Name: biometric_enrollment_sessions biometric_enrollment_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_enrollment_sessions
    ADD CONSTRAINT biometric_enrollment_sessions_pkey PRIMARY KEY (id);


--
-- Name: biometric_templates biometric_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_templates
    ADD CONSTRAINT biometric_templates_pkey PRIMARY KEY (id);


--
-- Name: biometric_verification_logs biometric_verification_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_verification_logs
    ADD CONSTRAINT biometric_verification_logs_pkey PRIMARY KEY (id);


--
-- Name: biotime_access_levels biotime_access_levels_level_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_levels
    ADD CONSTRAINT biotime_access_levels_level_code_key UNIQUE (level_code);


--
-- Name: biotime_access_levels biotime_access_levels_level_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_levels
    ADD CONSTRAINT biotime_access_levels_level_name_key UNIQUE (level_name);


--
-- Name: biotime_access_levels biotime_access_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_levels
    ADD CONSTRAINT biotime_access_levels_pkey PRIMARY KEY (id);


--
-- Name: biotime_access_schedules biotime_access_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_access_schedules
    ADD CONSTRAINT biotime_access_schedules_pkey PRIMARY KEY (id);


--
-- Name: biotime_biometric_templates biotime_biometric_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_biometric_templates
    ADD CONSTRAINT biotime_biometric_templates_pkey PRIMARY KEY (id);


--
-- Name: biotime_conflict_resolutions biotime_conflict_resolutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_conflict_resolutions
    ADD CONSTRAINT biotime_conflict_resolutions_pkey PRIMARY KEY (id);


--
-- Name: biotime_device_groups biotime_device_groups_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_device_groups
    ADD CONSTRAINT biotime_device_groups_group_name_key UNIQUE (group_name);


--
-- Name: biotime_device_groups biotime_device_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_device_groups
    ADD CONSTRAINT biotime_device_groups_pkey PRIMARY KEY (id);


--
-- Name: biotime_devices biotime_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_devices
    ADD CONSTRAINT biotime_devices_pkey PRIMARY KEY (id);


--
-- Name: biotime_sync_logs biotime_sync_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_sync_logs
    ADD CONSTRAINT biotime_sync_logs_pkey PRIMARY KEY (id);


--
-- Name: certification_audits certification_audits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_audits
    ADD CONSTRAINT certification_audits_pkey PRIMARY KEY (id);


--
-- Name: certification_templates certification_templates_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_templates
    ADD CONSTRAINT certification_templates_name_key UNIQUE (name);


--
-- Name: certification_templates certification_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_templates
    ADD CONSTRAINT certification_templates_pkey PRIMARY KEY (id);


--
-- Name: certifications certifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certifications
    ADD CONSTRAINT certifications_pkey PRIMARY KEY (id);


--
-- Name: checkinout checkinout_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkinout
    ADD CONSTRAINT checkinout_pkey PRIMARY KEY (id);


--
-- Name: contract_assignments contract_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assignments
    ADD CONSTRAINT contract_assignments_pkey PRIMARY KEY (id);


--
-- Name: contractor_compliance contractor_compliance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractor_compliance
    ADD CONSTRAINT contractor_compliance_pkey PRIMARY KEY (id);


--
-- Name: contractors contractors_contractor_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT contractors_contractor_code_key UNIQUE (contractor_code);


--
-- Name: contractors contractors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT contractors_pkey PRIMARY KEY (id);


--
-- Name: custom_attribute_values custom_attribute_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values
    ADD CONSTRAINT custom_attribute_values_pkey PRIMARY KEY (id);


--
-- Name: custom_attributes custom_attributes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attributes
    ADD CONSTRAINT custom_attributes_pkey PRIMARY KEY (id);


--
-- Name: department_personnel department_personnel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.department_personnel
    ADD CONSTRAINT department_personnel_pkey PRIMARY KEY (id);


--
-- Name: departments departments_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_code_key UNIQUE (code);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: device_blacklist device_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_blacklist
    ADD CONSTRAINT device_blacklist_pkey PRIMARY KEY (id);


--
-- Name: device_events device_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_events
    ADD CONSTRAINT device_events_pkey PRIMARY KEY (id);


--
-- Name: device_maintenance device_maintenance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_maintenance
    ADD CONSTRAINT device_maintenance_pkey PRIMARY KEY (id);


--
-- Name: device_schedules device_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_schedules
    ADD CONSTRAINT device_schedules_pkey PRIMARY KEY (id);


--
-- Name: device_suppressed device_suppressed_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_suppressed
    ADD CONSTRAINT device_suppressed_pkey PRIMARY KEY (sn);


--
-- Name: devicemap devicemap_device_sn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devicemap
    ADD CONSTRAINT devicemap_device_sn_key UNIQUE (device_sn);


--
-- Name: devicemap devicemap_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devicemap
    ADD CONSTRAINT devicemap_pkey PRIMARY KEY (id);


--
-- Name: devices devices_device_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_device_id_key UNIQUE (device_id);


--
-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (id);


--
-- Name: devices devices_serial_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_serial_number_key UNIQUE (serial_number);


--
-- Name: disciplinary_cases disciplinary_cases_case_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disciplinary_cases
    ADD CONSTRAINT disciplinary_cases_case_number_key UNIQUE (case_number);


--
-- Name: disciplinary_cases disciplinary_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disciplinary_cases
    ADD CONSTRAINT disciplinary_cases_pkey PRIMARY KEY (id);


--
-- Name: emergency_device_command emergency_device_command_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command
    ADD CONSTRAINT emergency_device_command_pkey PRIMARY KEY (id);


--
-- Name: emergency_device_enhanced emergency_device_enhanced_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_enhanced
    ADD CONSTRAINT emergency_device_enhanced_pkey PRIMARY KEY (id);


--
-- Name: emergency_device_enhanced emergency_device_enhanced_terminal_sn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_enhanced
    ADD CONSTRAINT emergency_device_enhanced_terminal_sn_key UNIQUE (terminal_sn);


--
-- Name: emergency_device_maintenance emergency_device_maintenance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance
    ADD CONSTRAINT emergency_device_maintenance_pkey PRIMARY KEY (id);


--
-- Name: emergency_device emergency_device_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device
    ADD CONSTRAINT emergency_device_pkey PRIMARY KEY (id);


--
-- Name: emergency_event_enhanced emergency_event_enhanced_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event_enhanced
    ADD CONSTRAINT emergency_event_enhanced_pkey PRIMARY KEY (id);


--
-- Name: emergency_event emergency_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event
    ADD CONSTRAINT emergency_event_pkey PRIMARY KEY (id);


--
-- Name: emergency_notification_enhanced emergency_notification_enhanced_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification_enhanced
    ADD CONSTRAINT emergency_notification_enhanced_pkey PRIMARY KEY (id);


--
-- Name: emergency_notification emergency_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification
    ADD CONSTRAINT emergency_notification_pkey PRIMARY KEY (id);


--
-- Name: emergency_panic_log_enhanced emergency_panic_log_enhanced_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log_enhanced
    ADD CONSTRAINT emergency_panic_log_enhanced_pkey PRIMARY KEY (id);


--
-- Name: emergency_panic_log emergency_panic_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log
    ADD CONSTRAINT emergency_panic_log_pkey PRIMARY KEY (id);


--
-- Name: emergency_plan emergency_plan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_plan
    ADD CONSTRAINT emergency_plan_pkey PRIMARY KEY (id);


--
-- Name: emergency_template emergency_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_template
    ADD CONSTRAINT emergency_template_pkey PRIMARY KEY (id);


--
-- Name: employee_benefits employee_benefits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_benefits
    ADD CONSTRAINT employee_benefits_pkey PRIMARY KEY (id);


--
-- Name: employment_contracts employment_contracts_contract_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employment_contracts
    ADD CONSTRAINT employment_contracts_contract_number_key UNIQUE (contract_number);


--
-- Name: employment_contracts employment_contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employment_contracts
    ADD CONSTRAINT employment_contracts_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: face face_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.face
    ADD CONSTRAINT face_pkey PRIMARY KEY (id);


--
-- Name: face face_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.face
    ADD CONSTRAINT face_user_id_key UNIQUE (user_id);


--
-- Name: fingerprint fingerprint_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fingerprint
    ADD CONSTRAINT fingerprint_pkey PRIMARY KEY (id);


--
-- Name: fingerprint fingerprint_user_id_finger_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fingerprint
    ADD CONSTRAINT fingerprint_user_id_finger_index_key UNIQUE (user_id, finger_index);


--
-- Name: flight_log flight_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flight_log
    ADD CONSTRAINT flight_log_pkey PRIMARY KEY (id);


--
-- Name: holiday holiday_holiday_date_holiday_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holiday
    ADD CONSTRAINT holiday_holiday_date_holiday_name_key UNIQUE (holiday_date, holiday_name);


--
-- Name: holiday holiday_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holiday
    ADD CONSTRAINT holiday_pkey PRIMARY KEY (id);


--
-- Name: hr_integration_config hr_integration_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_integration_config
    ADD CONSTRAINT hr_integration_config_pkey PRIMARY KEY (id);


--
-- Name: hr_sync_log hr_sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_sync_log
    ADD CONSTRAINT hr_sync_log_pkey PRIMARY KEY (id);


--
-- Name: iclock_bio_template iclock_bio_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_bio_template
    ADD CONSTRAINT iclock_bio_template_pkey PRIMARY KEY (id);


--
-- Name: iclock_devcmd iclock_devcmd_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_devcmd
    ADD CONSTRAINT iclock_devcmd_pkey PRIMARY KEY (id);


--
-- Name: iclock_operlog iclock_operlog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_operlog
    ADD CONSTRAINT iclock_operlog_pkey PRIMARY KEY (id);


--
-- Name: iclock_terminal iclock_terminal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_terminal
    ADD CONSTRAINT iclock_terminal_pkey PRIMARY KEY (id);


--
-- Name: iclock_terminal iclock_terminal_sn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_terminal
    ADD CONSTRAINT iclock_terminal_sn_key UNIQUE (sn);


--
-- Name: iclock_transaction iclock_transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_transaction
    ADD CONSTRAINT iclock_transaction_pkey PRIMARY KEY (id);


--
-- Name: leave_balance leave_balance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_balance
    ADD CONSTRAINT leave_balance_pkey PRIMARY KEY (id);


--
-- Name: leave_blackout leave_blackout_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_blackout
    ADD CONSTRAINT leave_blackout_pkey PRIMARY KEY (id);


--
-- Name: leave_management leave_management_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leave_management
    ADD CONSTRAINT leave_management_pkey PRIMARY KEY (id);


--
-- Name: manifest_entry manifest_entry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manifest_entry
    ADD CONSTRAINT manifest_entry_pkey PRIMARY KEY (id);


--
-- Name: mtd_audit_log mtd_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_audit_log
    ADD CONSTRAINT mtd_audit_log_pkey PRIMARY KEY (id);


--
-- Name: mtd_cert_type mtd_cert_type_cert_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_cert_type
    ADD CONSTRAINT mtd_cert_type_cert_name_key UNIQUE (cert_name);


--
-- Name: mtd_cert_type mtd_cert_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_cert_type
    ADD CONSTRAINT mtd_cert_type_pkey PRIMARY KEY (id);


--
-- Name: mtd_certification mtd_certification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification
    ADD CONSTRAINT mtd_certification_pkey PRIMARY KEY (id);


--
-- Name: mtd_compliance_log mtd_compliance_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_compliance_log
    ADD CONSTRAINT mtd_compliance_log_pkey PRIMARY KEY (id);


--
-- Name: mtd_induction_record mtd_induction_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record
    ADD CONSTRAINT mtd_induction_record_pkey PRIMARY KEY (id);


--
-- Name: mtd_induction_template mtd_induction_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_template
    ADD CONSTRAINT mtd_induction_template_pkey PRIMARY KEY (id);


--
-- Name: mtd_medical_record mtd_medical_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_medical_record
    ADD CONSTRAINT mtd_medical_record_pkey PRIMARY KEY (id);


--
-- Name: mtd_ppe_issue mtd_ppe_issue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_issue
    ADD CONSTRAINT mtd_ppe_issue_pkey PRIMARY KEY (id);


--
-- Name: mtd_ppe_type mtd_ppe_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_type
    ADD CONSTRAINT mtd_ppe_type_pkey PRIMARY KEY (id);


--
-- Name: mtg_action_item mtg_action_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_action_item
    ADD CONSTRAINT mtg_action_item_pkey PRIMARY KEY (id);


--
-- Name: mtg_attendance mtg_attendance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendance
    ADD CONSTRAINT mtg_attendance_pkey PRIMARY KEY (id);


--
-- Name: mtg_attendee mtg_attendee_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee
    ADD CONSTRAINT mtg_attendee_pkey PRIMARY KEY (id);


--
-- Name: mtg_booking mtg_booking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking
    ADD CONSTRAINT mtg_booking_pkey PRIMARY KEY (id);


--
-- Name: mtg_equipment mtg_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_equipment
    ADD CONSTRAINT mtg_equipment_pkey PRIMARY KEY (id);


--
-- Name: mtg_minutes mtg_minutes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_minutes
    ADD CONSTRAINT mtg_minutes_pkey PRIMARY KEY (id);


--
-- Name: mtg_room mtg_room_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_room
    ADD CONSTRAINT mtg_room_pkey PRIMARY KEY (id);


--
-- Name: mustering_drill_schedule mustering_drill_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_drill_schedule
    ADD CONSTRAINT mustering_drill_schedule_pkey PRIMARY KEY (id);


--
-- Name: mustering_escalation_record mustering_escalation_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_escalation_record
    ADD CONSTRAINT mustering_escalation_record_pkey PRIMARY KEY (id);


--
-- Name: mustering_event mustering_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_event
    ADD CONSTRAINT mustering_event_pkey PRIMARY KEY (id);


--
-- Name: mustering_expected mustering_expected_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_expected
    ADD CONSTRAINT mustering_expected_pkey PRIMARY KEY (id);


--
-- Name: mustering_log mustering_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_log
    ADD CONSTRAINT mustering_log_pkey PRIMARY KEY (id);


--
-- Name: mustering_search_sweep mustering_search_sweep_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_search_sweep
    ADD CONSTRAINT mustering_search_sweep_pkey PRIMARY KEY (id);


--
-- Name: mustering_template mustering_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_template
    ADD CONSTRAINT mustering_template_pkey PRIMARY KEY (id);


--
-- Name: onboarding_checklists onboarding_checklists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_checklists
    ADD CONSTRAINT onboarding_checklists_pkey PRIMARY KEY (id);


--
-- Name: onboarding_documents onboarding_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_documents
    ADD CONSTRAINT onboarding_documents_pkey PRIMARY KEY (id);


--
-- Name: onboarding_notifications onboarding_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_notifications
    ADD CONSTRAINT onboarding_notifications_pkey PRIMARY KEY (id);


--
-- Name: onboarding_task onboarding_task_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_pkey PRIMARY KEY (id);


--
-- Name: onboarding_tasks onboarding_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_tasks
    ADD CONSTRAINT onboarding_tasks_pkey PRIMARY KEY (id);


--
-- Name: onboarding_templates onboarding_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_templates
    ADD CONSTRAINT onboarding_templates_pkey PRIMARY KEY (id);


--
-- Name: onboardings onboardings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_pkey PRIMARY KEY (id);


--
-- Name: overtime_management overtime_management_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_management
    ADD CONSTRAINT overtime_management_pkey PRIMARY KEY (id);


--
-- Name: overtime_record overtime_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_record
    ADD CONSTRAINT overtime_record_pkey PRIMARY KEY (id);


--
-- Name: overtime_rule overtime_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rule
    ADD CONSTRAINT overtime_rule_pkey PRIMARY KEY (id);


--
-- Name: overtime_rules overtime_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rules
    ADD CONSTRAINT overtime_rules_pkey PRIMARY KEY (id);


--
-- Name: pay_attendance_mapping pay_attendance_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_attendance_mapping
    ADD CONSTRAINT pay_attendance_mapping_pkey PRIMARY KEY (id);


--
-- Name: pay_audit_log pay_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_audit_log
    ADD CONSTRAINT pay_audit_log_pkey PRIMARY KEY (id);


--
-- Name: pay_bank_config pay_bank_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_bank_config
    ADD CONSTRAINT pay_bank_config_pkey PRIMARY KEY (id);


--
-- Name: pay_calculation_log pay_calculation_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_calculation_log
    ADD CONSTRAINT pay_calculation_log_pkey PRIMARY KEY (id);


--
-- Name: pay_contractor_rate pay_contractor_rate_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_contractor_rate
    ADD CONSTRAINT pay_contractor_rate_pkey PRIMARY KEY (id);


--
-- Name: pay_item pay_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_item
    ADD CONSTRAINT pay_item_pkey PRIMARY KEY (id);


--
-- Name: pay_loan_deduction pay_loan_deduction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction
    ADD CONSTRAINT pay_loan_deduction_pkey PRIMARY KEY (id);


--
-- Name: pay_loan pay_loan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan
    ADD CONSTRAINT pay_loan_pkey PRIMARY KEY (id);


--
-- Name: pay_payslip_template pay_payslip_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_payslip_template
    ADD CONSTRAINT pay_payslip_template_pkey PRIMARY KEY (id);


--
-- Name: pay_period pay_period_period_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_period
    ADD CONSTRAINT pay_period_period_name_key UNIQUE (period_name);


--
-- Name: pay_period pay_period_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_period
    ADD CONSTRAINT pay_period_pkey PRIMARY KEY (id);


--
-- Name: pay_salary_item pay_salary_item_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary_item
    ADD CONSTRAINT pay_salary_item_pkey PRIMARY KEY (id);


--
-- Name: pay_salary pay_salary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_pkey PRIMARY KEY (id);


--
-- Name: pay_structure_assign pay_structure_assign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure_assign
    ADD CONSTRAINT pay_structure_assign_pkey PRIMARY KEY (id);


--
-- Name: pay_structure pay_structure_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure
    ADD CONSTRAINT pay_structure_pkey PRIMARY KEY (id);


--
-- Name: pay_zone_allowance pay_zone_allowance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_zone_allowance
    ADD CONSTRAINT pay_zone_allowance_pkey PRIMARY KEY (id);


--
-- Name: performance_appraisals performance_appraisals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_appraisals
    ADD CONSTRAINT performance_appraisals_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_code_key UNIQUE (code);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: personnel_area personnel_area_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_area
    ADD CONSTRAINT personnel_area_pkey PRIMARY KEY (id);


--
-- Name: personnel_assignments personnel_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_assignments
    ADD CONSTRAINT personnel_assignments_pkey PRIMARY KEY (id);


--
-- Name: personnel personnel_badge_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_badge_id_key UNIQUE (badge_id);


--
-- Name: personnel_department personnel_department_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_department
    ADD CONSTRAINT personnel_department_pkey PRIMARY KEY (id);


--
-- Name: personnel_documents personnel_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_documents
    ADD CONSTRAINT personnel_documents_pkey PRIMARY KEY (id);


--
-- Name: personnel personnel_emp_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_emp_code_key UNIQUE (emp_code);


--
-- Name: personnel_employee personnel_employee_emp_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_employee
    ADD CONSTRAINT personnel_employee_emp_code_key UNIQUE (emp_code);


--
-- Name: personnel_employee personnel_employee_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_employee
    ADD CONSTRAINT personnel_employee_pkey PRIMARY KEY (id);


--
-- Name: personnel personnel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_pkey PRIMARY KEY (id);


--
-- Name: pob_status pob_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pob_status
    ADD CONSTRAINT pob_status_pkey PRIMARY KEY (id);


--
-- Name: position_assignments position_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_assignments
    ADD CONSTRAINT position_assignments_pkey PRIMARY KEY (id);


--
-- Name: position_levels position_levels_level_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_levels
    ADD CONSTRAINT position_levels_level_code_key UNIQUE (level_code);


--
-- Name: position_levels position_levels_level_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_levels
    ADD CONSTRAINT position_levels_level_number_key UNIQUE (level_number);


--
-- Name: position_levels position_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_levels
    ADD CONSTRAINT position_levels_pkey PRIMARY KEY (id);


--
-- Name: position_templates position_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_templates
    ADD CONSTRAINT position_templates_pkey PRIMARY KEY (id);


--
-- Name: position_templates position_templates_template_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_templates
    ADD CONSTRAINT position_templates_template_code_key UNIQUE (template_code);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: positions positions_position_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_position_code_key UNIQUE (position_code);


--
-- Name: promotion_transfers promotion_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.promotion_transfers
    ADD CONSTRAINT promotion_transfers_pkey PRIMARY KEY (id);


--
-- Name: resignation_documents resignation_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_documents
    ADD CONSTRAINT resignation_documents_pkey PRIMARY KEY (id);


--
-- Name: resignation_notifications resignation_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_notifications
    ADD CONSTRAINT resignation_notifications_pkey PRIMARY KEY (id);


--
-- Name: resignation_tasks resignation_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_tasks
    ADD CONSTRAINT resignation_tasks_pkey PRIMARY KEY (id);


--
-- Name: resignation_templates resignation_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_templates
    ADD CONSTRAINT resignation_templates_pkey PRIMARY KEY (id);


--
-- Name: resignations resignations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_pkey PRIMARY KEY (id);


--
-- Name: role_assignments role_assignments_personnel_id_role_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_assignments
    ADD CONSTRAINT role_assignments_personnel_id_role_id_key UNIQUE (personnel_id, role_id);


--
-- Name: role_assignments role_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_assignments
    ADD CONSTRAINT role_assignments_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_role_id_permission_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_permission_code_key UNIQUE (role_id, permission_code);


--
-- Name: roles roles_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_code_key UNIQUE (code);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: rpt_export_log rpt_export_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_export_log
    ADD CONSTRAINT rpt_export_log_pkey PRIMARY KEY (id);


--
-- Name: rpt_favorite rpt_favorite_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_favorite
    ADD CONSTRAINT rpt_favorite_pkey PRIMARY KEY (id);


--
-- Name: rpt_schedule rpt_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_schedule
    ADD CONSTRAINT rpt_schedule_pkey PRIMARY KEY (id);


--
-- Name: rpt_template rpt_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_template
    ADD CONSTRAINT rpt_template_pkey PRIMARY KEY (id);


--
-- Name: rpt_user_preset rpt_user_preset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_user_preset
    ADD CONSTRAINT rpt_user_preset_pkey PRIMARY KEY (id);


--
-- Name: schedule_management schedule_management_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schedule_management
    ADD CONSTRAINT schedule_management_pkey PRIMARY KEY (id);


--
-- Name: shift_management shift_management_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shift_management
    ADD CONSTRAINT shift_management_pkey PRIMARY KEY (id);


--
-- Name: shift_management shift_management_shift_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shift_management
    ADD CONSTRAINT shift_management_shift_code_key UNIQUE (shift_code);


--
-- Name: sn sn_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sn
    ADD CONSTRAINT sn_pkey PRIMARY KEY (id);


--
-- Name: sn sn_sn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sn
    ADD CONSTRAINT sn_sn_key UNIQUE (sn);


--
-- Name: ssr ssr_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssr
    ADD CONSTRAINT ssr_pkey PRIMARY KEY (id);


--
-- Name: sys_api_keys sys_api_keys_api_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_api_keys
    ADD CONSTRAINT sys_api_keys_api_key_key UNIQUE (api_key);


--
-- Name: sys_api_keys sys_api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_api_keys
    ADD CONSTRAINT sys_api_keys_pkey PRIMARY KEY (id);


--
-- Name: sys_branding sys_branding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_branding
    ADD CONSTRAINT sys_branding_pkey PRIMARY KEY (id);


--
-- Name: sys_consent_records sys_consent_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_consent_records
    ADD CONSTRAINT sys_consent_records_pkey PRIMARY KEY (id);


--
-- Name: sys_data_access_logs sys_data_access_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_data_access_logs
    ADD CONSTRAINT sys_data_access_logs_pkey PRIMARY KEY (id);


--
-- Name: sys_db_backups sys_db_backups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_db_backups
    ADD CONSTRAINT sys_db_backups_pkey PRIMARY KEY (id);


--
-- Name: sys_email_templates sys_email_templates_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_email_templates
    ADD CONSTRAINT sys_email_templates_code_key UNIQUE (code);


--
-- Name: sys_email_templates sys_email_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_email_templates
    ADD CONSTRAINT sys_email_templates_pkey PRIMARY KEY (id);


--
-- Name: sys_languages sys_languages_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_languages
    ADD CONSTRAINT sys_languages_code_key UNIQUE (code);


--
-- Name: sys_languages sys_languages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_languages
    ADD CONSTRAINT sys_languages_pkey PRIMARY KEY (id);


--
-- Name: sys_licenses sys_licenses_license_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_licenses
    ADD CONSTRAINT sys_licenses_license_key_key UNIQUE (license_key);


--
-- Name: sys_licenses sys_licenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_licenses
    ADD CONSTRAINT sys_licenses_pkey PRIMARY KEY (id);


--
-- Name: sys_notifications sys_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_notifications
    ADD CONSTRAINT sys_notifications_pkey PRIMARY KEY (id);


--
-- Name: sys_parameters sys_parameters_param_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_parameters
    ADD CONSTRAINT sys_parameters_param_key_key UNIQUE (param_key);


--
-- Name: sys_parameters sys_parameters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_parameters
    ADD CONSTRAINT sys_parameters_pkey PRIMARY KEY (id);


--
-- Name: sys_permissions sys_permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_permissions
    ADD CONSTRAINT sys_permissions_code_key UNIQUE (code);


--
-- Name: sys_permissions sys_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_permissions
    ADD CONSTRAINT sys_permissions_pkey PRIMARY KEY (id);


--
-- Name: sys_renewal_log sys_renewal_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_renewal_log
    ADD CONSTRAINT sys_renewal_log_pkey PRIMARY KEY (id);


--
-- Name: sys_role_permissions sys_role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_role_permissions
    ADD CONSTRAINT sys_role_permissions_pkey PRIMARY KEY (id);


--
-- Name: sys_role_permissions sys_role_permissions_role_id_permission_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_role_permissions
    ADD CONSTRAINT sys_role_permissions_role_id_permission_code_key UNIQUE (role_id, permission_code);


--
-- Name: sys_roles sys_roles_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_roles
    ADD CONSTRAINT sys_roles_name_key UNIQUE (name);


--
-- Name: sys_roles sys_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_roles
    ADD CONSTRAINT sys_roles_pkey PRIMARY KEY (id);


--
-- Name: sys_sso_configs sys_sso_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_sso_configs
    ADD CONSTRAINT sys_sso_configs_pkey PRIMARY KEY (id);


--
-- Name: sys_subscription sys_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_subscription
    ADD CONSTRAINT sys_subscription_pkey PRIMARY KEY (id);


--
-- Name: sys_translations sys_translations_lang_code_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_translations
    ADD CONSTRAINT sys_translations_lang_code_key_key UNIQUE (lang_code, key);


--
-- Name: sys_translations sys_translations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_translations
    ADD CONSTRAINT sys_translations_pkey PRIMARY KEY (id);


--
-- Name: sys_user_roles sys_user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_user_roles
    ADD CONSTRAINT sys_user_roles_pkey PRIMARY KEY (id);


--
-- Name: sys_user_roles sys_user_roles_user_id_role_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_user_roles
    ADD CONSTRAINT sys_user_roles_user_id_role_id_key UNIQUE (user_id, role_id);


--
-- Name: sys_webhooks sys_webhooks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_webhooks
    ADD CONSTRAINT sys_webhooks_pkey PRIMARY KEY (id);


--
-- Name: system_company system_company_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_company
    ADD CONSTRAINT system_company_pkey PRIMARY KEY (id);


--
-- Name: training_courses training_courses_course_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_courses
    ADD CONSTRAINT training_courses_course_code_key UNIQUE (course_code);


--
-- Name: training_courses training_courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_courses
    ADD CONSTRAINT training_courses_pkey PRIMARY KEY (id);


--
-- Name: training_enrollment training_enrollment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_enrollment
    ADD CONSTRAINT training_enrollment_pkey PRIMARY KEY (id);


--
-- Name: transport_assignments transport_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_assignments
    ADD CONSTRAINT transport_assignments_pkey PRIMARY KEY (id);


--
-- Name: transport_crew transport_crew_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_crew
    ADD CONSTRAINT transport_crew_pkey PRIMARY KEY (id);


--
-- Name: transport transport_identifier_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport
    ADD CONSTRAINT transport_identifier_key UNIQUE (identifier);


--
-- Name: transport_inventory transport_inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_inventory
    ADD CONSTRAINT transport_inventory_pkey PRIMARY KEY (id);


--
-- Name: transport_maintenance transport_maintenance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_maintenance
    ADD CONSTRAINT transport_maintenance_pkey PRIMARY KEY (id);


--
-- Name: transport transport_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport
    ADD CONSTRAINT transport_pkey PRIMARY KEY (id);


--
-- Name: transport_schedule transport_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_schedule
    ADD CONSTRAINT transport_schedule_pkey PRIMARY KEY (id);


--
-- Name: user_extensions user_extensions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_extensions
    ADD CONSTRAINT user_extensions_pkey PRIMARY KEY (id);


--
-- Name: user_extensions user_extensions_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_extensions
    ADD CONSTRAINT user_extensions_user_id_key UNIQUE (user_id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_refresh_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_refresh_token_key UNIQUE (refresh_token);


--
-- Name: user_sessions user_sessions_session_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_session_token_key UNIQUE (session_token);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: vendor_compliance vendor_compliance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_compliance
    ADD CONSTRAINT vendor_compliance_pkey PRIMARY KEY (id);


--
-- Name: vendor_contracts vendor_contracts_contract_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_contracts
    ADD CONSTRAINT vendor_contracts_contract_number_key UNIQUE (contract_number);


--
-- Name: vendor_contracts vendor_contracts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_contracts
    ADD CONSTRAINT vendor_contracts_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_vendor_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_vendor_code_key UNIQUE (vendor_code);


--
-- Name: vis_blacklist vis_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_blacklist
    ADD CONSTRAINT vis_blacklist_pkey PRIMARY KEY (id);


--
-- Name: vis_pre_registration vis_pre_registration_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_pkey PRIMARY KEY (id);


--
-- Name: vis_type vis_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_type
    ADD CONSTRAINT vis_type_pkey PRIMARY KEY (id);


--
-- Name: vis_visit_log vis_visit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_pkey PRIMARY KEY (id);


--
-- Name: vis_visitor vis_visitor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visitor
    ADD CONSTRAINT vis_visitor_pkey PRIMARY KEY (id);


--
-- Name: zone_personnel_assignments zone_personnel_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_assignments
    ADD CONSTRAINT zone_personnel_assignments_pkey PRIMARY KEY (id);


--
-- Name: zone_personnel_tracking zone_personnel_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_tracking
    ADD CONSTRAINT zone_personnel_tracking_pkey PRIMARY KEY (id);


--
-- Name: zone_reader_assignments zone_reader_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_reader_assignments
    ADD CONSTRAINT zone_reader_assignments_pkey PRIMARY KEY (id);


--
-- Name: zones zones_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_code_key UNIQUE (code);


--
-- Name: zones zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pkey PRIMARY KEY (id);


--
-- Name: att_shift_shift_code_uq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX att_shift_shift_code_uq ON public.att_shift USING btree (shift_code) WHERE (shift_code IS NOT NULL);


--
-- Name: idx_arp_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_arp_role ON public.auth_role_permission USING btree (role_id);


--
-- Name: idx_atr_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atr_date ON public.att_report USING btree (att_date);


--
-- Name: idx_atr_dept; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atr_dept ON public.att_report USING btree (department_id);


--
-- Name: idx_atr_emp_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atr_emp_date ON public.att_report USING btree (emp_id, att_date);


--
-- Name: idx_atr_emp_date_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atr_emp_date_desc ON public.att_report USING btree (emp_id, att_date DESC);


--
-- Name: idx_atr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_atr_status ON public.att_report USING btree (att_status);


--
-- Name: idx_aur_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_aur_user ON public.auth_user_role USING btree (user_id);


--
-- Name: idx_auth_role_perm_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_role_perm_role ON public.auth_role_permission USING btree (role_id);


--
-- Name: idx_auth_user_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_user_active ON public.auth_user USING btree (is_active);


--
-- Name: idx_auth_user_role_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_user_role_role ON public.auth_user_role USING btree (role_id);


--
-- Name: idx_auth_user_role_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_user_role_user ON public.auth_user_role USING btree (user_id);


--
-- Name: idx_auth_user_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_user_username ON public.auth_user USING btree (username);


--
-- Name: idx_bol_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bol_user ON public.base_operationlog USING btree (user_id);


--
-- Name: idx_checkinout_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_checkinout_emp_code ON public.checkinout USING btree (emp_code);


--
-- Name: idx_checkinout_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_checkinout_time ON public.checkinout USING btree (check_time);


--
-- Name: idx_con_permit_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_con_permit_expiry ON public.contractors USING btree (work_permit_expiry);


--
-- Name: idx_con_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_con_status ON public.contractors USING btree (status);


--
-- Name: idx_dep_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dep_active ON public.departments USING btree (is_active);


--
-- Name: idx_devicemap_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_devicemap_sn ON public.devicemap USING btree (device_sn);


--
-- Name: idx_eev_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eev_start ON public.emergency_event USING btree (start_time DESC);


--
-- Name: idx_eev_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eev_status ON public.emergency_event USING btree (status);


--
-- Name: idx_face_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_face_user_id ON public.face USING btree (user_id);


--
-- Name: idx_fingerprint_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fingerprint_user_id ON public.fingerprint USING btree (user_id);


--
-- Name: idx_holiday_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_holiday_date ON public.holiday USING btree (holiday_date);


--
-- Name: idx_iclock_txn_emp_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_iclock_txn_emp_time ON public.iclock_transaction USING btree (emp_code, punch_time DESC);


--
-- Name: idx_iclock_txn_sn_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_iclock_txn_sn_time ON public.iclock_transaction USING btree (terminal_sn, punch_time DESC);


--
-- Name: idx_ict_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ict_emp_code ON public.iclock_transaction USING btree (emp_code);


--
-- Name: idx_ict_emp_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ict_emp_time ON public.iclock_transaction USING btree (emp_code, punch_time DESC);


--
-- Name: idx_ict_punch_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ict_punch_time ON public.iclock_transaction USING btree (punch_time DESC);


--
-- Name: idx_ict_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ict_state ON public.iclock_transaction USING btree (punch_state);


--
-- Name: idx_ict_terminal; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ict_terminal ON public.iclock_transaction USING btree (terminal_sn);


--
-- Name: idx_itt_last_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_itt_last_activity ON public.iclock_terminal USING btree (last_activity DESC);


--
-- Name: idx_itt_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_itt_sn ON public.iclock_terminal USING btree (sn);


--
-- Name: idx_lvm_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lvm_dates ON public.leave_management USING btree (start_date, end_date);


--
-- Name: idx_lvm_personnel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lvm_personnel ON public.leave_management USING btree (personnel_id);


--
-- Name: idx_lvm_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lvm_status ON public.leave_management USING btree (status);


--
-- Name: idx_manifest_schedule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manifest_schedule_id ON public.manifest_entry USING btree (schedule_id);


--
-- Name: idx_manifest_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_manifest_status ON public.manifest_entry USING btree (status);


--
-- Name: idx_mds_auto_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mds_auto_pending ON public.mustering_drill_schedule USING btree (auto_start, processed, scheduled_time);


--
-- Name: idx_mev_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mev_start ON public.mustering_event USING btree (start_time DESC);


--
-- Name: idx_mev_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mev_status ON public.mustering_event USING btree (status);


--
-- Name: idx_mustering_event_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mustering_event_status ON public.mustering_event USING btree (status);


--
-- Name: idx_mustering_event_zone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mustering_event_zone ON public.mustering_event USING btree (zone_id);


--
-- Name: idx_mustering_log_emp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mustering_log_emp ON public.mustering_log USING btree (emp_code);


--
-- Name: idx_mustering_log_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mustering_log_event ON public.mustering_log USING btree (event_id);


--
-- Name: idx_operation_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_operation_log_action ON public.base_operationlog USING btree (action);


--
-- Name: idx_operation_log_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_operation_log_created ON public.base_operationlog USING btree (created_at);


--
-- Name: idx_operation_log_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_operation_log_user ON public.base_operationlog USING btree (user_id);


--
-- Name: idx_overtime_record_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overtime_record_date ON public.overtime_record USING btree (overtime_date);


--
-- Name: idx_overtime_record_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overtime_record_emp_code ON public.overtime_record USING btree (emp_code);


--
-- Name: idx_overtime_rule_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_overtime_rule_type ON public.overtime_rule USING btree (rule_type);


--
-- Name: idx_pdoc_personnel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pdoc_personnel ON public.personnel_documents USING btree (personnel_id);


--
-- Name: idx_pdoc_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pdoc_personnel_id ON public.personnel_documents USING btree (personnel_id);


--
-- Name: idx_per_badge; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_per_badge ON public.personnel USING btree (badge_id);


--
-- Name: idx_per_code_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_per_code_active ON public.personnel USING btree (emp_code, is_active);


--
-- Name: idx_per_dept; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_per_dept ON public.personnel USING btree (department_id);


--
-- Name: idx_per_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_per_emp_code ON public.personnel USING btree (emp_code);


--
-- Name: idx_per_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_per_status ON public.personnel USING btree (status);


--
-- Name: idx_personnel_card_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personnel_card_number ON public.personnel USING btree (card_number);


--
-- Name: idx_personnel_dept_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personnel_dept_id ON public.personnel_employee USING btree (dept_id);


--
-- Name: idx_personnel_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personnel_emp_code ON public.personnel_employee USING btree (emp_code);


--
-- Name: idx_personnel_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personnel_status ON public.personnel_employee USING btree (status);


--
-- Name: idx_rpt_export_log_export_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_export_log_export_time ON public.rpt_export_log USING btree (export_time);


--
-- Name: idx_rpt_export_log_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_export_log_template_id ON public.rpt_export_log USING btree (template_id);


--
-- Name: idx_rpt_export_log_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_export_log_user_id ON public.rpt_export_log USING btree (user_id);


--
-- Name: idx_rpt_favorite_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_favorite_template_id ON public.rpt_favorite USING btree (template_id);


--
-- Name: idx_rpt_favorite_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_favorite_user_id ON public.rpt_favorite USING btree (user_id);


--
-- Name: idx_rpt_favorite_user_template; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_rpt_favorite_user_template ON public.rpt_favorite USING btree (user_id, template_id);


--
-- Name: idx_rpt_schedule_next_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_schedule_next_run ON public.rpt_schedule USING btree (next_run, is_active);


--
-- Name: idx_rpt_schedule_next_run_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_schedule_next_run_active ON public.rpt_schedule USING btree (next_run, is_active);


--
-- Name: idx_rpt_schedule_template; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_schedule_template ON public.rpt_schedule USING btree (template_id);


--
-- Name: idx_rpt_schedule_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_schedule_template_id ON public.rpt_schedule USING btree (template_id);


--
-- Name: idx_rpt_template_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_template_created_by ON public.rpt_template USING btree (created_by);


--
-- Name: idx_rpt_template_is_public; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_template_is_public ON public.rpt_template USING btree (is_public);


--
-- Name: idx_rpt_template_module_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_template_module_code ON public.rpt_template USING btree (module, report_code);


--
-- Name: idx_rpt_user_preset_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_user_preset_template_id ON public.rpt_user_preset USING btree (template_id);


--
-- Name: idx_rpt_user_preset_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rpt_user_preset_user_id ON public.rpt_user_preset USING btree (user_id);


--
-- Name: idx_snf_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snf_read ON public.sys_notifications USING btree (is_read, created_at DESC);


--
-- Name: idx_snf_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_snf_user ON public.sys_notifications USING btree (user_id);


--
-- Name: idx_ssr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ssr_status ON public.ssr USING btree (status);


--
-- Name: idx_ssr_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ssr_user_id ON public.ssr USING btree (user_id);


--
-- Name: idx_ten_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ten_expiry ON public.training_enrollment USING btree (expiry_date);


--
-- Name: idx_ten_personnel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ten_personnel ON public.training_enrollment USING btree (personnel_id);


--
-- Name: idx_ten_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ten_status ON public.training_enrollment USING btree (status);


--
-- Name: idx_terminal_ip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_terminal_ip ON public.iclock_terminal USING btree (ip_address);


--
-- Name: idx_terminal_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_terminal_sn ON public.iclock_terminal USING btree (sn);


--
-- Name: idx_terminal_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_terminal_state ON public.iclock_terminal USING btree (state);


--
-- Name: idx_transaction_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_emp_code ON public.iclock_transaction USING btree (emp_code);


--
-- Name: idx_transaction_punch_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_punch_time ON public.iclock_transaction USING btree (punch_time);


--
-- Name: idx_transaction_terminal_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_terminal_sn ON public.iclock_transaction USING btree (terminal_sn);


--
-- Name: idx_transaction_upload_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_upload_time ON public.iclock_transaction USING btree (upload_time);


--
-- Name: idx_vpr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vpr_status ON public.vis_pre_registration USING btree (status);


--
-- Name: idx_vvl_checkin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vvl_checkin ON public.vis_visit_log USING btree (check_in_time);


--
-- Name: idx_vvl_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vvl_status ON public.vis_visit_log USING btree (status);


--
-- Name: idx_vvl_visitor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vvl_visitor ON public.vis_visit_log USING btree (visitor_id);


--
-- Name: idx_zon_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zon_status ON public.zones USING btree (status);


--
-- Name: idx_zon_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zon_type ON public.zones USING btree (zone_type);


--
-- Name: idx_zpt_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zpt_emp_code ON public.zone_personnel_tracking USING btree (emp_code);


--
-- Name: idx_zpt_punch_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zpt_punch_time ON public.zone_personnel_tracking USING btree (punch_time);


--
-- Name: idx_zpt_zone_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zpt_zone_id ON public.zone_personnel_tracking USING btree (zone_id);


--
-- Name: idx_zpt_zone_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zpt_zone_time ON public.zone_personnel_tracking USING btree (zone_id, punch_time DESC);


--
-- Name: ix_acc_antipassback_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_antipassback_emp_code ON public.acc_antipassback USING btree (emp_code);


--
-- Name: ix_acc_antipassback_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_antipassback_id ON public.acc_antipassback USING btree (id);


--
-- Name: ix_acc_event_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_event_created_at ON public.acc_event USING btree (created_at);


--
-- Name: ix_acc_event_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_event_emp_code ON public.acc_event USING btree (emp_code);


--
-- Name: ix_acc_event_event_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_event_event_time ON public.acc_event USING btree (event_time);


--
-- Name: ix_acc_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_event_id ON public.acc_event USING btree (id);


--
-- Name: ix_acc_event_terminal_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_event_terminal_sn ON public.acc_event USING btree (terminal_sn);


--
-- Name: ix_acc_first_card_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_first_card_id ON public.acc_first_card USING btree (id);


--
-- Name: ix_acc_interlock_door_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_interlock_door_id ON public.acc_interlock_door USING btree (id);


--
-- Name: ix_acc_interlock_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_interlock_group_id ON public.acc_interlock_group USING btree (id);


--
-- Name: ix_acc_level_door_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_level_door_id ON public.acc_level_door USING btree (id);


--
-- Name: ix_acc_linkage_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_linkage_id ON public.acc_linkage USING btree (id);


--
-- Name: ix_acc_passback_rule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_passback_rule_id ON public.acc_passback_rule USING btree (id);


--
-- Name: ix_acc_timezone_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_acc_timezone_id ON public.acc_timezone USING btree (id);


--
-- Name: ix_access_logs_access_granted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_access_granted ON public.access_logs USING btree (access_granted);


--
-- Name: ix_access_logs_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_device_id ON public.access_logs USING btree (device_id);


--
-- Name: ix_access_logs_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_event_type ON public.access_logs USING btree (event_type);


--
-- Name: ix_access_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_id ON public.access_logs USING btree (id);


--
-- Name: ix_access_logs_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_personnel_id ON public.access_logs USING btree (personnel_id);


--
-- Name: ix_access_logs_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_access_logs_timestamp ON public.access_logs USING btree ("timestamp");


--
-- Name: ix_attendance_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_logs_id ON public.attendance_logs USING btree (id);


--
-- Name: ix_attendance_logs_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_logs_timestamp ON public.attendance_logs USING btree ("timestamp");


--
-- Name: ix_attribute_templates_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_templates_category ON public.attribute_templates USING btree (category);


--
-- Name: ix_attribute_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_templates_id ON public.attribute_templates USING btree (id);


--
-- Name: ix_attribute_templates_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_templates_is_active ON public.attribute_templates USING btree (is_active);


--
-- Name: ix_attribute_templates_template_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_attribute_templates_template_code ON public.attribute_templates USING btree (template_code);


--
-- Name: ix_attribute_templates_template_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_templates_template_name ON public.attribute_templates USING btree (template_name);


--
-- Name: ix_attribute_validations_attribute_value_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_validations_attribute_value_id ON public.attribute_validations USING btree (attribute_value_id);


--
-- Name: ix_attribute_validations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attribute_validations_id ON public.attribute_validations USING btree (id);


--
-- Name: ix_base_company_company_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_base_company_company_name ON public.base_company USING btree (company_name);


--
-- Name: ix_base_company_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_base_company_id ON public.base_company USING btree (id);


--
-- Name: ix_biometric_devices_device_serial; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_biometric_devices_device_serial ON public.biometric_devices USING btree (device_serial);


--
-- Name: ix_biometric_devices_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_devices_id ON public.biometric_devices USING btree (id);


--
-- Name: ix_biometric_devices_ip_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_devices_ip_address ON public.biometric_devices USING btree (ip_address);


--
-- Name: ix_biometric_enrollment_sessions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_enrollment_sessions_id ON public.biometric_enrollment_sessions USING btree (id);


--
-- Name: ix_biometric_enrollment_sessions_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_biometric_enrollment_sessions_session_id ON public.biometric_enrollment_sessions USING btree (session_id);


--
-- Name: ix_biometric_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_templates_id ON public.biometric_templates USING btree (id);


--
-- Name: ix_biometric_templates_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_templates_is_active ON public.biometric_templates USING btree (is_active);


--
-- Name: ix_biometric_templates_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_templates_personnel_id ON public.biometric_templates USING btree (personnel_id);


--
-- Name: ix_biometric_templates_template_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_templates_template_type ON public.biometric_templates USING btree (template_type);


--
-- Name: ix_biometric_verification_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_verification_logs_id ON public.biometric_verification_logs USING btree (id);


--
-- Name: ix_biometric_verification_logs_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biometric_verification_logs_personnel_id ON public.biometric_verification_logs USING btree (personnel_id);


--
-- Name: ix_biotime_access_levels_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_access_levels_id ON public.biotime_access_levels USING btree (id);


--
-- Name: ix_biotime_access_schedules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_access_schedules_id ON public.biotime_access_schedules USING btree (id);


--
-- Name: ix_biotime_biometric_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_biometric_templates_id ON public.biotime_biometric_templates USING btree (id);


--
-- Name: ix_biotime_biometric_templates_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_biometric_templates_personnel_id ON public.biotime_biometric_templates USING btree (personnel_id);


--
-- Name: ix_biotime_biometric_templates_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_biometric_templates_template_id ON public.biotime_biometric_templates USING btree (template_id);


--
-- Name: ix_biotime_conflict_resolutions_conflict_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_biotime_conflict_resolutions_conflict_id ON public.biotime_conflict_resolutions USING btree (conflict_id);


--
-- Name: ix_biotime_conflict_resolutions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_conflict_resolutions_id ON public.biotime_conflict_resolutions USING btree (id);


--
-- Name: ix_biotime_device_groups_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_device_groups_id ON public.biotime_device_groups USING btree (id);


--
-- Name: ix_biotime_devices_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_biotime_devices_device_id ON public.biotime_devices USING btree (device_id);


--
-- Name: ix_biotime_devices_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_devices_id ON public.biotime_devices USING btree (id);


--
-- Name: ix_biotime_sync_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_biotime_sync_logs_id ON public.biotime_sync_logs USING btree (id);


--
-- Name: ix_certification_audits_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certification_audits_id ON public.certification_audits USING btree (id);


--
-- Name: ix_certification_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certification_templates_id ON public.certification_templates USING btree (id);


--
-- Name: ix_certifications_certificate_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_certifications_certificate_number ON public.certifications USING btree (certificate_number);


--
-- Name: ix_certifications_expire_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certifications_expire_date ON public.certifications USING btree (expire_date);


--
-- Name: ix_certifications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certifications_id ON public.certifications USING btree (id);


--
-- Name: ix_certifications_issuer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certifications_issuer ON public.certifications USING btree (issuer);


--
-- Name: ix_certifications_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certifications_name ON public.certifications USING btree (name);


--
-- Name: ix_certifications_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_certifications_personnel_id ON public.certifications USING btree (personnel_id);


--
-- Name: ix_custom_attribute_values_attribute_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attribute_values_attribute_id ON public.custom_attribute_values USING btree (attribute_id);


--
-- Name: ix_custom_attribute_values_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attribute_values_id ON public.custom_attribute_values USING btree (id);


--
-- Name: ix_custom_attribute_values_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attribute_values_personnel_id ON public.custom_attribute_values USING btree (personnel_id);


--
-- Name: ix_custom_attributes_attribute_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_custom_attributes_attribute_code ON public.custom_attributes USING btree (attribute_code);


--
-- Name: ix_custom_attributes_attribute_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_attribute_name ON public.custom_attributes USING btree (attribute_name);


--
-- Name: ix_custom_attributes_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_category ON public.custom_attributes USING btree (category);


--
-- Name: ix_custom_attributes_group_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_group_name ON public.custom_attributes USING btree (group_name);


--
-- Name: ix_custom_attributes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_id ON public.custom_attributes USING btree (id);


--
-- Name: ix_custom_attributes_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_is_active ON public.custom_attributes USING btree (is_active);


--
-- Name: ix_custom_attributes_is_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_is_required ON public.custom_attributes USING btree (is_required);


--
-- Name: ix_custom_attributes_is_searchable; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_is_searchable ON public.custom_attributes USING btree (is_searchable);


--
-- Name: ix_custom_attributes_is_visible_in_list; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_attributes_is_visible_in_list ON public.custom_attributes USING btree (is_visible_in_list);


--
-- Name: ix_department_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_department_personnel_id ON public.department_personnel USING btree (id);


--
-- Name: ix_device_blacklist_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_blacklist_emp_code ON public.device_blacklist USING btree (emp_code);


--
-- Name: ix_device_blacklist_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_blacklist_id ON public.device_blacklist USING btree (id);


--
-- Name: ix_device_events_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_events_device_id ON public.device_events USING btree (device_id);


--
-- Name: ix_device_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_events_event_type ON public.device_events USING btree (event_type);


--
-- Name: ix_device_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_events_id ON public.device_events USING btree (id);


--
-- Name: ix_device_events_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_events_timestamp ON public.device_events USING btree ("timestamp");


--
-- Name: ix_device_maintenance_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_maintenance_device_id ON public.device_maintenance USING btree (device_id);


--
-- Name: ix_device_maintenance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_maintenance_id ON public.device_maintenance USING btree (id);


--
-- Name: ix_device_schedules_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_schedules_device_id ON public.device_schedules USING btree (device_id);


--
-- Name: ix_device_schedules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_schedules_id ON public.device_schedules USING btree (id);


--
-- Name: ix_emergency_device_command_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_device_command_created_at ON public.emergency_device_command USING btree (created_at);


--
-- Name: ix_emergency_device_command_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_device_command_id ON public.emergency_device_command USING btree (id);


--
-- Name: ix_emergency_device_enhanced_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_device_enhanced_id ON public.emergency_device_enhanced USING btree (id);


--
-- Name: ix_emergency_device_enhanced_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_device_enhanced_status ON public.emergency_device_enhanced USING btree (status);


--
-- Name: ix_emergency_device_maintenance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_device_maintenance_id ON public.emergency_device_maintenance USING btree (id);


--
-- Name: ix_emergency_event_enhanced_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_enhanced_event_type ON public.emergency_event_enhanced USING btree (event_type);


--
-- Name: ix_emergency_event_enhanced_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_enhanced_id ON public.emergency_event_enhanced USING btree (id);


--
-- Name: ix_emergency_event_enhanced_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_enhanced_start_time ON public.emergency_event_enhanced USING btree (start_time);


--
-- Name: ix_emergency_event_enhanced_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_enhanced_status ON public.emergency_event_enhanced USING btree (status);


--
-- Name: ix_emergency_event_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_event_type ON public.emergency_event USING btree (event_type);


--
-- Name: ix_emergency_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_id ON public.emergency_event USING btree (id);


--
-- Name: ix_emergency_event_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_event_status ON public.emergency_event USING btree (status);


--
-- Name: ix_emergency_notification_emergency_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_emergency_event_id ON public.emergency_notification USING btree (emergency_event_id);


--
-- Name: ix_emergency_notification_enhanced_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_enhanced_channel ON public.emergency_notification_enhanced USING btree (channel);


--
-- Name: ix_emergency_notification_enhanced_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_enhanced_created_at ON public.emergency_notification_enhanced USING btree (created_at);


--
-- Name: ix_emergency_notification_enhanced_emergency_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_enhanced_emergency_event_id ON public.emergency_notification_enhanced USING btree (emergency_event_id);


--
-- Name: ix_emergency_notification_enhanced_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_enhanced_id ON public.emergency_notification_enhanced USING btree (id);


--
-- Name: ix_emergency_notification_enhanced_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_enhanced_status ON public.emergency_notification_enhanced USING btree (status);


--
-- Name: ix_emergency_notification_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_id ON public.emergency_notification USING btree (id);


--
-- Name: ix_emergency_notification_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_notification_status ON public.emergency_notification USING btree (status);


--
-- Name: ix_emergency_panic_log_enhanced_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_panic_log_enhanced_id ON public.emergency_panic_log_enhanced USING btree (id);


--
-- Name: ix_emergency_panic_log_enhanced_panic_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_panic_log_enhanced_panic_time ON public.emergency_panic_log_enhanced USING btree (panic_time);


--
-- Name: ix_emergency_panic_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_panic_log_id ON public.emergency_panic_log USING btree (id);


--
-- Name: ix_emergency_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_plan_id ON public.emergency_plan USING btree (id);


--
-- Name: ix_emergency_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_emergency_template_id ON public.emergency_template USING btree (id);


--
-- Name: ix_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_id ON public.events USING btree (id);


--
-- Name: ix_flight_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_flight_log_id ON public.flight_log USING btree (id);


--
-- Name: ix_iclock_bio_template_emp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_bio_template_emp ON public.iclock_bio_template USING btree (emp_code);


--
-- Name: ix_iclock_devcmd_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_devcmd_id ON public.iclock_devcmd USING btree (id);


--
-- Name: ix_iclock_devcmd_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_devcmd_sn ON public.iclock_devcmd USING btree (sn);


--
-- Name: ix_iclock_devcmd_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_devcmd_status ON public.iclock_devcmd USING btree (status);


--
-- Name: ix_iclock_operlog_event_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_operlog_event_time ON public.iclock_operlog USING btree (event_time);


--
-- Name: ix_iclock_operlog_oper_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_operlog_oper_event ON public.iclock_operlog USING btree (oper_event);


--
-- Name: ix_iclock_operlog_terminal_sn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_iclock_operlog_terminal_sn ON public.iclock_operlog USING btree (terminal_sn);


--
-- Name: ix_mtg_action_item_assignee_emp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_action_item_assignee_emp_id ON public.mtg_action_item USING btree (assignee_emp_id);


--
-- Name: ix_mtg_action_item_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_action_item_booking_id ON public.mtg_action_item USING btree (booking_id);


--
-- Name: ix_mtg_action_item_created_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_action_item_created_time ON public.mtg_action_item USING btree (created_time);


--
-- Name: ix_mtg_action_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_action_item_id ON public.mtg_action_item USING btree (id);


--
-- Name: ix_mtg_action_item_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_action_item_status ON public.mtg_action_item USING btree (status);


--
-- Name: ix_mtg_attendance_attendee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendance_attendee_id ON public.mtg_attendance USING btree (attendee_id);


--
-- Name: ix_mtg_attendance_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendance_booking_id ON public.mtg_attendance USING btree (booking_id);


--
-- Name: ix_mtg_attendance_check_in_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendance_check_in_time ON public.mtg_attendance USING btree (check_in_time);


--
-- Name: ix_mtg_attendance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendance_id ON public.mtg_attendance USING btree (id);


--
-- Name: ix_mtg_attendee_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendee_booking_id ON public.mtg_attendee USING btree (booking_id);


--
-- Name: ix_mtg_attendee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_attendee_id ON public.mtg_attendee USING btree (id);


--
-- Name: ix_mtg_booking_created_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_created_time ON public.mtg_booking USING btree (created_time);


--
-- Name: ix_mtg_booking_end_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_end_time ON public.mtg_booking USING btree (end_time);


--
-- Name: ix_mtg_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_id ON public.mtg_booking USING btree (id);


--
-- Name: ix_mtg_booking_meeting_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_meeting_code ON public.mtg_booking USING btree (meeting_code);


--
-- Name: ix_mtg_booking_organizer_emp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_organizer_emp_id ON public.mtg_booking USING btree (organizer_emp_id);


--
-- Name: ix_mtg_booking_room_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_room_id ON public.mtg_booking USING btree (room_id);


--
-- Name: ix_mtg_booking_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_start_time ON public.mtg_booking USING btree (start_time);


--
-- Name: ix_mtg_booking_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_booking_status ON public.mtg_booking USING btree (status);


--
-- Name: ix_mtg_equipment_equip_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_equipment_equip_name ON public.mtg_equipment USING btree (equip_name);


--
-- Name: ix_mtg_equipment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_equipment_id ON public.mtg_equipment USING btree (id);


--
-- Name: ix_mtg_equipment_room_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_equipment_room_id ON public.mtg_equipment USING btree (room_id);


--
-- Name: ix_mtg_minutes_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_minutes_booking_id ON public.mtg_minutes USING btree (booking_id);


--
-- Name: ix_mtg_minutes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_minutes_id ON public.mtg_minutes USING btree (id);


--
-- Name: ix_mtg_minutes_uploaded_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_minutes_uploaded_time ON public.mtg_minutes USING btree (uploaded_time);


--
-- Name: ix_mtg_room_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mtg_room_id ON public.mtg_room USING btree (id);


--
-- Name: ix_mtg_room_room_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_mtg_room_room_name ON public.mtg_room USING btree (room_name);


--
-- Name: ix_mustering_escalation_record_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_escalation_record_emp_code ON public.mustering_escalation_record USING btree (emp_code);


--
-- Name: ix_mustering_escalation_record_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_escalation_record_event_id ON public.mustering_escalation_record USING btree (event_id);


--
-- Name: ix_mustering_escalation_record_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_escalation_record_id ON public.mustering_escalation_record USING btree (id);


--
-- Name: ix_mustering_expected_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_expected_emp_code ON public.mustering_expected USING btree (emp_code);


--
-- Name: ix_mustering_expected_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_expected_event_id ON public.mustering_expected USING btree (event_id);


--
-- Name: ix_mustering_expected_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_expected_id ON public.mustering_expected USING btree (id);


--
-- Name: ix_mustering_search_sweep_emp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_search_sweep_emp_code ON public.mustering_search_sweep USING btree (emp_code);


--
-- Name: ix_mustering_search_sweep_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_search_sweep_event_id ON public.mustering_search_sweep USING btree (event_id);


--
-- Name: ix_mustering_search_sweep_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mustering_search_sweep_id ON public.mustering_search_sweep USING btree (id);


--
-- Name: ix_onboarding_checklists_checklist_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_checklist_name ON public.onboarding_checklists USING btree (checklist_name);


--
-- Name: ix_onboarding_checklists_checklist_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_checklist_type ON public.onboarding_checklists USING btree (checklist_type);


--
-- Name: ix_onboarding_checklists_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_id ON public.onboarding_checklists USING btree (id);


--
-- Name: ix_onboarding_checklists_is_completed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_is_completed ON public.onboarding_checklists USING btree (is_completed);


--
-- Name: ix_onboarding_checklists_is_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_is_required ON public.onboarding_checklists USING btree (is_required);


--
-- Name: ix_onboarding_checklists_onboarding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_checklists_onboarding_id ON public.onboarding_checklists USING btree (onboarding_id);


--
-- Name: ix_onboarding_documents_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_documents_document_type ON public.onboarding_documents USING btree (document_type);


--
-- Name: ix_onboarding_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_documents_id ON public.onboarding_documents USING btree (id);


--
-- Name: ix_onboarding_documents_is_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_documents_is_required ON public.onboarding_documents USING btree (is_required);


--
-- Name: ix_onboarding_documents_onboarding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_documents_onboarding_id ON public.onboarding_documents USING btree (onboarding_id);


--
-- Name: ix_onboarding_notifications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_notifications_id ON public.onboarding_notifications USING btree (id);


--
-- Name: ix_onboarding_notifications_is_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_notifications_is_read ON public.onboarding_notifications USING btree (is_read);


--
-- Name: ix_onboarding_notifications_notification_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_notifications_notification_type ON public.onboarding_notifications USING btree (notification_type);


--
-- Name: ix_onboarding_notifications_onboarding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_notifications_onboarding_id ON public.onboarding_notifications USING btree (onboarding_id);


--
-- Name: ix_onboarding_notifications_recipient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_notifications_recipient_id ON public.onboarding_notifications USING btree (recipient_id);


--
-- Name: ix_onboarding_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_tasks_id ON public.onboarding_tasks USING btree (id);


--
-- Name: ix_onboarding_tasks_is_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_tasks_is_required ON public.onboarding_tasks USING btree (is_required);


--
-- Name: ix_onboarding_tasks_onboarding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_tasks_onboarding_id ON public.onboarding_tasks USING btree (onboarding_id);


--
-- Name: ix_onboarding_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_tasks_status ON public.onboarding_tasks USING btree (status);


--
-- Name: ix_onboarding_tasks_task_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_tasks_task_name ON public.onboarding_tasks USING btree (task_name);


--
-- Name: ix_onboarding_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_templates_id ON public.onboarding_templates USING btree (id);


--
-- Name: ix_onboarding_templates_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_templates_is_active ON public.onboarding_templates USING btree (is_active);


--
-- Name: ix_onboarding_templates_template_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_onboarding_templates_template_code ON public.onboarding_templates USING btree (template_code);


--
-- Name: ix_onboarding_templates_template_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboarding_templates_template_name ON public.onboarding_templates USING btree (template_name);


--
-- Name: ix_onboardings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboardings_id ON public.onboardings USING btree (id);


--
-- Name: ix_onboardings_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboardings_personnel_id ON public.onboardings USING btree (personnel_id);


--
-- Name: ix_onboardings_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_onboardings_status ON public.onboardings USING btree (status);


--
-- Name: ix_pay_attendance_mapping_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_attendance_mapping_id ON public.pay_attendance_mapping USING btree (id);


--
-- Name: ix_pay_audit_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_audit_log_id ON public.pay_audit_log USING btree (id);


--
-- Name: ix_pay_bank_config_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_bank_config_id ON public.pay_bank_config USING btree (id);


--
-- Name: ix_pay_calculation_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_calculation_log_id ON public.pay_calculation_log USING btree (id);


--
-- Name: ix_pay_contractor_rate_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_contractor_rate_id ON public.pay_contractor_rate USING btree (id);


--
-- Name: ix_pay_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_item_id ON public.pay_item USING btree (id);


--
-- Name: ix_pay_loan_deduction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_loan_deduction_id ON public.pay_loan_deduction USING btree (id);


--
-- Name: ix_pay_loan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_loan_id ON public.pay_loan USING btree (id);


--
-- Name: ix_pay_loan_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_loan_status ON public.pay_loan USING btree (status);


--
-- Name: ix_pay_payslip_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_payslip_template_id ON public.pay_payslip_template USING btree (id);


--
-- Name: ix_pay_period_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_period_id ON public.pay_period USING btree (id);


--
-- Name: ix_pay_period_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_period_status ON public.pay_period USING btree (status);


--
-- Name: ix_pay_salary_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_salary_id ON public.pay_salary USING btree (id);


--
-- Name: ix_pay_salary_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_salary_item_id ON public.pay_salary_item USING btree (id);


--
-- Name: ix_pay_structure_assign_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_structure_assign_id ON public.pay_structure_assign USING btree (id);


--
-- Name: ix_pay_structure_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_structure_id ON public.pay_structure USING btree (id);


--
-- Name: ix_pay_structure_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_structure_is_active ON public.pay_structure USING btree (is_active);


--
-- Name: ix_pay_structure_structure_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_structure_structure_name ON public.pay_structure USING btree (structure_name);


--
-- Name: ix_pay_zone_allowance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pay_zone_allowance_id ON public.pay_zone_allowance USING btree (id);


--
-- Name: ix_personnel_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_personnel_assignments_id ON public.personnel_assignments USING btree (id);


--
-- Name: ix_resignation_documents_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_documents_document_type ON public.resignation_documents USING btree (document_type);


--
-- Name: ix_resignation_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_documents_id ON public.resignation_documents USING btree (id);


--
-- Name: ix_resignation_documents_resignation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_documents_resignation_id ON public.resignation_documents USING btree (resignation_id);


--
-- Name: ix_resignation_notifications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_notifications_id ON public.resignation_notifications USING btree (id);


--
-- Name: ix_resignation_notifications_is_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_notifications_is_read ON public.resignation_notifications USING btree (is_read);


--
-- Name: ix_resignation_notifications_recipient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_notifications_recipient_id ON public.resignation_notifications USING btree (recipient_id);


--
-- Name: ix_resignation_notifications_resignation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_notifications_resignation_id ON public.resignation_notifications USING btree (resignation_id);


--
-- Name: ix_resignation_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_tasks_id ON public.resignation_tasks USING btree (id);


--
-- Name: ix_resignation_tasks_is_completed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_tasks_is_completed ON public.resignation_tasks USING btree (is_completed);


--
-- Name: ix_resignation_tasks_is_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_tasks_is_required ON public.resignation_tasks USING btree (is_required);


--
-- Name: ix_resignation_tasks_resignation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_tasks_resignation_id ON public.resignation_tasks USING btree (resignation_id);


--
-- Name: ix_resignation_tasks_task_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_tasks_task_name ON public.resignation_tasks USING btree (task_name);


--
-- Name: ix_resignation_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_templates_id ON public.resignation_templates USING btree (id);


--
-- Name: ix_resignation_templates_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_templates_is_active ON public.resignation_templates USING btree (is_active);


--
-- Name: ix_resignation_templates_template_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_resignation_templates_template_code ON public.resignation_templates USING btree (template_code);


--
-- Name: ix_resignation_templates_template_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignation_templates_template_name ON public.resignation_templates USING btree (template_name);


--
-- Name: ix_resignations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignations_id ON public.resignations USING btree (id);


--
-- Name: ix_resignations_personnel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignations_personnel_id ON public.resignations USING btree (personnel_id);


--
-- Name: ix_resignations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resignations_status ON public.resignations USING btree (status);


--
-- Name: ix_rpt_export_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rpt_export_log_id ON public.rpt_export_log USING btree (id);


--
-- Name: ix_rpt_favorite_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rpt_favorite_id ON public.rpt_favorite USING btree (id);


--
-- Name: ix_rpt_schedule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rpt_schedule_id ON public.rpt_schedule USING btree (id);


--
-- Name: ix_rpt_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rpt_template_id ON public.rpt_template USING btree (id);


--
-- Name: ix_rpt_user_preset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rpt_user_preset_id ON public.rpt_user_preset USING btree (id);


--
-- Name: ix_transport_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_assignments_id ON public.transport_assignments USING btree (id);


--
-- Name: ix_transport_crew_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_crew_id ON public.transport_crew USING btree (id);


--
-- Name: ix_transport_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_id ON public.transport USING btree (id);


--
-- Name: ix_transport_inventory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_inventory_id ON public.transport_inventory USING btree (id);


--
-- Name: ix_transport_maintenance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_maintenance_id ON public.transport_maintenance USING btree (id);


--
-- Name: ix_transport_schedule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_schedule_id ON public.transport_schedule USING btree (id);


--
-- Name: ix_transport_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transport_status ON public.transport USING btree (status);


--
-- Name: ix_user_roles_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_roles_id ON public.user_roles USING btree (id);


--
-- Name: ix_user_sessions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_sessions_id ON public.user_sessions USING btree (id);


--
-- Name: ix_vis_blacklist_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_blacklist_email ON public.vis_blacklist USING btree (email);


--
-- Name: ix_vis_blacklist_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_blacklist_id ON public.vis_blacklist USING btree (id);


--
-- Name: ix_vis_blacklist_id_no; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_blacklist_id_no ON public.vis_blacklist USING btree (id_no);


--
-- Name: ix_vis_blacklist_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_blacklist_phone ON public.vis_blacklist USING btree (phone);


--
-- Name: ix_vis_pre_registration_host_emp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_pre_registration_host_emp_id ON public.vis_pre_registration USING btree (host_emp_id);


--
-- Name: ix_vis_pre_registration_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_pre_registration_id ON public.vis_pre_registration USING btree (id);


--
-- Name: ix_vis_pre_registration_qr_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_pre_registration_qr_code ON public.vis_pre_registration USING btree (qr_code);


--
-- Name: ix_vis_pre_registration_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_pre_registration_status ON public.vis_pre_registration USING btree (status);


--
-- Name: ix_vis_pre_registration_visit_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_pre_registration_visit_date ON public.vis_pre_registration USING btree (visit_date);


--
-- Name: ix_vis_type_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_type_id ON public.vis_type USING btree (id);


--
-- Name: ix_vis_type_type_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_type_type_name ON public.vis_type USING btree (type_name);


--
-- Name: ix_vis_visit_log_card_no; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_card_no ON public.vis_visit_log USING btree (card_no);


--
-- Name: ix_vis_visit_log_check_in_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_check_in_time ON public.vis_visit_log USING btree (check_in_time);


--
-- Name: ix_vis_visit_log_check_out_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_check_out_time ON public.vis_visit_log USING btree (check_out_time);


--
-- Name: ix_vis_visit_log_host_emp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_host_emp_id ON public.vis_visit_log USING btree (host_emp_id);


--
-- Name: ix_vis_visit_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_id ON public.vis_visit_log USING btree (id);


--
-- Name: ix_vis_visit_log_pre_reg_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_pre_reg_id ON public.vis_visit_log USING btree (pre_reg_id);


--
-- Name: ix_vis_visit_log_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_status ON public.vis_visit_log USING btree (status);


--
-- Name: ix_vis_visit_log_visitor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visit_log_visitor_id ON public.vis_visit_log USING btree (visitor_id);


--
-- Name: ix_vis_visitor_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_email ON public.vis_visitor USING btree (email);


--
-- Name: ix_vis_visitor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_id ON public.vis_visitor USING btree (id);


--
-- Name: ix_vis_visitor_id_no; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_id_no ON public.vis_visitor USING btree (id_no);


--
-- Name: ix_vis_visitor_is_blacklist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_is_blacklist ON public.vis_visitor USING btree (is_blacklist);


--
-- Name: ix_vis_visitor_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_phone ON public.vis_visitor USING btree (phone);


--
-- Name: ix_vis_visitor_visitor_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_vis_visitor_visitor_code ON public.vis_visitor USING btree (visitor_code);


--
-- Name: sys_notifications_dedup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX sys_notifications_dedup_idx ON public.sys_notifications USING btree (dedup_key);


--
-- Name: sys_notifications_user_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sys_notifications_user_idx ON public.sys_notifications USING btree (user_id, is_read, created_at DESC);


--
-- Name: uq_bio_template_emp_finger; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_bio_template_emp_finger ON public.iclock_bio_template USING btree (emp_code, finger_id);


--
-- Name: personnel trg_sync_personnel; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_sync_personnel AFTER INSERT OR DELETE OR UPDATE ON public.personnel FOR EACH ROW EXECUTE FUNCTION public.sync_personnel_to_employee();


--
-- Name: acc_antipassback acc_antipassback_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_antipassback
    ADD CONSTRAINT acc_antipassback_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_door acc_door_acc_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_door
    ADD CONSTRAINT acc_door_acc_level_id_fkey FOREIGN KEY (acc_level_id) REFERENCES public.acc_level(id);


--
-- Name: acc_door acc_door_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_door
    ADD CONSTRAINT acc_door_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: acc_event acc_event_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_event
    ADD CONSTRAINT acc_event_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_first_card acc_first_card_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_first_card
    ADD CONSTRAINT acc_first_card_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_first_card acc_first_card_timezone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_first_card
    ADD CONSTRAINT acc_first_card_timezone_id_fkey FOREIGN KEY (timezone_id) REFERENCES public.acc_timezone(id);


--
-- Name: acc_guard_tour_checkpoint acc_guard_tour_checkpoint_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_checkpoint
    ADD CONSTRAINT acc_guard_tour_checkpoint_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_guard_tour_checkpoint acc_guard_tour_checkpoint_tour_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_checkpoint
    ADD CONSTRAINT acc_guard_tour_checkpoint_tour_id_fkey FOREIGN KEY (tour_id) REFERENCES public.acc_guard_tour(id) ON DELETE CASCADE;


--
-- Name: acc_guard_tour_log acc_guard_tour_log_checkpoint_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_log
    ADD CONSTRAINT acc_guard_tour_log_checkpoint_id_fkey FOREIGN KEY (checkpoint_id) REFERENCES public.acc_guard_tour_checkpoint(id);


--
-- Name: acc_guard_tour_log acc_guard_tour_log_schedule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_log
    ADD CONSTRAINT acc_guard_tour_log_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.acc_guard_tour_schedule(id) ON DELETE CASCADE;


--
-- Name: acc_guard_tour_schedule acc_guard_tour_schedule_tour_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_guard_tour_schedule
    ADD CONSTRAINT acc_guard_tour_schedule_tour_id_fkey FOREIGN KEY (tour_id) REFERENCES public.acc_guard_tour(id) ON DELETE CASCADE;


--
-- Name: acc_interlock_door acc_interlock_door_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_door
    ADD CONSTRAINT acc_interlock_door_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_interlock_door acc_interlock_door_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_interlock_door
    ADD CONSTRAINT acc_interlock_door_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.acc_interlock_group(id);


--
-- Name: acc_level_door acc_level_door_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level_door
    ADD CONSTRAINT acc_level_door_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_level_door acc_level_door_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level_door
    ADD CONSTRAINT acc_level_door_level_id_fkey FOREIGN KEY (level_id) REFERENCES public.acc_level(id);


--
-- Name: acc_level_door acc_level_door_timezone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_level_door
    ADD CONSTRAINT acc_level_door_timezone_id_fkey FOREIGN KEY (timezone_id) REFERENCES public.acc_timezone(id);


--
-- Name: acc_linkage acc_linkage_output_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_linkage
    ADD CONSTRAINT acc_linkage_output_door_id_fkey FOREIGN KEY (output_door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_multi_card acc_multi_card_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card
    ADD CONSTRAINT acc_multi_card_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id) ON DELETE CASCADE;


--
-- Name: acc_multi_card_user acc_multi_card_user_multi_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_multi_card_user
    ADD CONSTRAINT acc_multi_card_user_multi_card_id_fkey FOREIGN KEY (multi_card_id) REFERENCES public.acc_multi_card(id) ON DELETE CASCADE;


--
-- Name: acc_passback_rule acc_passback_rule_in_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_passback_rule
    ADD CONSTRAINT acc_passback_rule_in_door_id_fkey FOREIGN KEY (in_door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_passback_rule acc_passback_rule_out_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_passback_rule
    ADD CONSTRAINT acc_passback_rule_out_door_id_fkey FOREIGN KEY (out_door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_userauthorize acc_userauthorize_acc_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_userauthorize
    ADD CONSTRAINT acc_userauthorize_acc_level_id_fkey FOREIGN KEY (acc_level_id) REFERENCES public.acc_level(id);


--
-- Name: acc_visitor_access acc_visitor_access_acc_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_visitor_access
    ADD CONSTRAINT acc_visitor_access_acc_level_id_fkey FOREIGN KEY (acc_level_id) REFERENCES public.acc_level(id);


--
-- Name: acc_visitor_access acc_visitor_access_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_visitor_access
    ADD CONSTRAINT acc_visitor_access_level_id_fkey FOREIGN KEY (level_id) REFERENCES public.acc_level(id) ON DELETE SET NULL;


--
-- Name: acc_zone_door acc_zone_door_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone_door
    ADD CONSTRAINT acc_zone_door_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: acc_zone_door acc_zone_door_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acc_zone_door
    ADD CONSTRAINT acc_zone_door_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.acc_zone(id) ON DELETE CASCADE;


--
-- Name: access_logs access_logs_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(device_id);


--
-- Name: access_logs access_logs_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: access_logs access_logs_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- Name: acgroup acgroup_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acgroup
    ADD CONSTRAINT acgroup_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.acgroup(id);


--
-- Name: att_exception att_exception_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_exception
    ADD CONSTRAINT att_exception_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: att_leave att_leave_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave
    ADD CONSTRAINT att_leave_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: att_leave att_leave_leave_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_leave
    ADD CONSTRAINT att_leave_leave_type_id_fkey FOREIGN KEY (leave_type_id) REFERENCES public.att_leave_type(id);


--
-- Name: att_manual_log att_manual_log_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_manual_log
    ADD CONSTRAINT att_manual_log_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: att_overtime att_overtime_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_overtime
    ADD CONSTRAINT att_overtime_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: att_report att_report_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report
    ADD CONSTRAINT att_report_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: att_report att_report_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report
    ADD CONSTRAINT att_report_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.att_shift(id);


--
-- Name: att_report att_report_timetable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_report
    ADD CONSTRAINT att_report_timetable_id_fkey FOREIGN KEY (timetable_id) REFERENCES public.att_timetable(id);


--
-- Name: att_schedule att_schedule_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_schedule
    ADD CONSTRAINT att_schedule_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.att_shift(id);


--
-- Name: att_shift att_shift_timetable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift
    ADD CONSTRAINT att_shift_timetable_id_fkey FOREIGN KEY (timetable_id) REFERENCES public.att_timetable(id);


--
-- Name: att_shift_timetable att_shift_timetable_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift_timetable
    ADD CONSTRAINT att_shift_timetable_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.att_shift(id) ON DELETE CASCADE;


--
-- Name: att_shift_timetable att_shift_timetable_timetable_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.att_shift_timetable
    ADD CONSTRAINT att_shift_timetable_timetable_id_fkey FOREIGN KEY (timetable_id) REFERENCES public.att_timetable(id);


--
-- Name: attendance_logs attendance_logs_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_logs
    ADD CONSTRAINT attendance_logs_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: attribute_templates attribute_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_templates
    ADD CONSTRAINT attribute_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: attribute_validations attribute_validations_attribute_value_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attribute_validations
    ADD CONSTRAINT attribute_validations_attribute_value_id_fkey FOREIGN KEY (attribute_value_id) REFERENCES public.custom_attribute_values(id);


--
-- Name: auth_role_permission auth_role_permission_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role_permission
    ADD CONSTRAINT auth_role_permission_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) ON DELETE CASCADE;


--
-- Name: auth_role_permission auth_role_permission_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_role_permission
    ADD CONSTRAINT auth_role_permission_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.auth_role(id) ON DELETE CASCADE;


--
-- Name: auth_user_role auth_user_role_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_role
    ADD CONSTRAINT auth_user_role_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.auth_role(id) ON DELETE CASCADE;


--
-- Name: auth_user_role auth_user_role_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_role
    ADD CONSTRAINT auth_user_role_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE;


--
-- Name: base_company base_company_parent_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_company
    ADD CONSTRAINT base_company_parent_company_id_fkey FOREIGN KEY (parent_company_id) REFERENCES public.base_company(id);


--
-- Name: base_operationlog base_operationlog_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.base_operationlog
    ADD CONSTRAINT base_operationlog_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id);


--
-- Name: biometric_enrollment_sessions biometric_enrollment_sessions_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_enrollment_sessions
    ADD CONSTRAINT biometric_enrollment_sessions_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: biometric_templates biometric_templates_enrolled_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_templates
    ADD CONSTRAINT biometric_templates_enrolled_by_fkey FOREIGN KEY (enrolled_by) REFERENCES public.users(id);


--
-- Name: biometric_templates biometric_templates_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_templates
    ADD CONSTRAINT biometric_templates_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: biometric_verification_logs biometric_verification_logs_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_verification_logs
    ADD CONSTRAINT biometric_verification_logs_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: biometric_verification_logs biometric_verification_logs_template_used_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biometric_verification_logs
    ADD CONSTRAINT biometric_verification_logs_template_used_fkey FOREIGN KEY (template_used) REFERENCES public.biometric_templates(id);


--
-- Name: biotime_biometric_templates biotime_biometric_templates_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_biometric_templates
    ADD CONSTRAINT biotime_biometric_templates_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: biotime_conflict_resolutions biotime_conflict_resolutions_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_conflict_resolutions
    ADD CONSTRAINT biotime_conflict_resolutions_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id);


--
-- Name: biotime_device_groups biotime_device_groups_parent_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_device_groups
    ADD CONSTRAINT biotime_device_groups_parent_group_id_fkey FOREIGN KEY (parent_group_id) REFERENCES public.biotime_device_groups(id);


--
-- Name: biotime_devices biotime_devices_device_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.biotime_devices
    ADD CONSTRAINT biotime_devices_device_group_id_fkey FOREIGN KEY (device_group_id) REFERENCES public.biotime_device_groups(id);


--
-- Name: certification_audits certification_audits_certification_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_audits
    ADD CONSTRAINT certification_audits_certification_id_fkey FOREIGN KEY (certification_id) REFERENCES public.certifications(id);


--
-- Name: certification_audits certification_audits_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_audits
    ADD CONSTRAINT certification_audits_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.users(id);


--
-- Name: certification_audits certification_audits_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certification_audits
    ADD CONSTRAINT certification_audits_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: certifications certifications_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certifications
    ADD CONSTRAINT certifications_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: checkinout checkinout_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkinout
    ADD CONSTRAINT checkinout_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: checkinout checkinout_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checkinout
    ADD CONSTRAINT checkinout_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.personnel_employee(id);


--
-- Name: custom_attribute_values custom_attribute_values_attribute_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values
    ADD CONSTRAINT custom_attribute_values_attribute_id_fkey FOREIGN KEY (attribute_id) REFERENCES public.custom_attributes(id);


--
-- Name: custom_attribute_values custom_attribute_values_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values
    ADD CONSTRAINT custom_attribute_values_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: custom_attribute_values custom_attribute_values_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values
    ADD CONSTRAINT custom_attribute_values_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: custom_attribute_values custom_attribute_values_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attribute_values
    ADD CONSTRAINT custom_attribute_values_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: custom_attributes custom_attributes_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attributes
    ADD CONSTRAINT custom_attributes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: custom_attributes custom_attributes_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_attributes
    ADD CONSTRAINT custom_attributes_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: department_personnel department_personnel_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.department_personnel
    ADD CONSTRAINT department_personnel_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: department_personnel department_personnel_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.department_personnel
    ADD CONSTRAINT department_personnel_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: department_personnel department_personnel_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.department_personnel
    ADD CONSTRAINT department_personnel_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: departments departments_default_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_default_shift_id_fkey FOREIGN KEY (default_shift_id) REFERENCES public.att_shift(id) ON DELETE SET NULL;


--
-- Name: departments departments_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.departments(id);


--
-- Name: device_blacklist device_blacklist_blocked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_blacklist
    ADD CONSTRAINT device_blacklist_blocked_by_fkey FOREIGN KEY (blocked_by) REFERENCES public.users(id);


--
-- Name: device_events device_events_acknowledged_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_events
    ADD CONSTRAINT device_events_acknowledged_by_fkey FOREIGN KEY (acknowledged_by) REFERENCES public.users(id);


--
-- Name: device_events device_events_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_events
    ADD CONSTRAINT device_events_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(device_id);


--
-- Name: device_maintenance device_maintenance_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_maintenance
    ADD CONSTRAINT device_maintenance_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.users(id);


--
-- Name: device_maintenance device_maintenance_terminal_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_maintenance
    ADD CONSTRAINT device_maintenance_terminal_fkey FOREIGN KEY (device_id) REFERENCES public.iclock_terminal(sn) ON DELETE SET NULL;


--
-- Name: device_schedules device_schedules_terminal_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_schedules
    ADD CONSTRAINT device_schedules_terminal_fkey FOREIGN KEY (device_id) REFERENCES public.iclock_terminal(sn) ON DELETE SET NULL;


--
-- Name: devicemap devicemap_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devicemap
    ADD CONSTRAINT devicemap_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: devices devices_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- Name: emergency_device_command emergency_device_command_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command
    ADD CONSTRAINT emergency_device_command_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.emergency_device_enhanced(id);


--
-- Name: emergency_device_command emergency_device_command_emergency_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command
    ADD CONSTRAINT emergency_device_command_emergency_event_id_fkey FOREIGN KEY (emergency_event_id) REFERENCES public.emergency_event_enhanced(id);


--
-- Name: emergency_device_command emergency_device_command_operator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command
    ADD CONSTRAINT emergency_device_command_operator_id_fkey FOREIGN KEY (operator_id) REFERENCES public.auth_user(id);


--
-- Name: emergency_device_command emergency_device_command_parent_command_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_command
    ADD CONSTRAINT emergency_device_command_parent_command_fkey FOREIGN KEY (parent_command) REFERENCES public.emergency_device_command(id);


--
-- Name: emergency_device_enhanced emergency_device_enhanced_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_enhanced
    ADD CONSTRAINT emergency_device_enhanced_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: emergency_device_maintenance emergency_device_maintenance_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance
    ADD CONSTRAINT emergency_device_maintenance_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_device_maintenance emergency_device_maintenance_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance
    ADD CONSTRAINT emergency_device_maintenance_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.emergency_device_enhanced(id);


--
-- Name: emergency_device_maintenance emergency_device_maintenance_supervisor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance
    ADD CONSTRAINT emergency_device_maintenance_supervisor_id_fkey FOREIGN KEY (supervisor_id) REFERENCES public.personnel_employee(id);


--
-- Name: emergency_device_maintenance emergency_device_maintenance_technician_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_maintenance
    ADD CONSTRAINT emergency_device_maintenance_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES public.personnel_employee(id);


--
-- Name: emergency_device emergency_device_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device
    ADD CONSTRAINT emergency_device_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: emergency_device emergency_device_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device
    ADD CONSTRAINT emergency_device_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: emergency_event_enhanced emergency_event_enhanced_initiated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event_enhanced
    ADD CONSTRAINT emergency_event_enhanced_initiated_by_fkey FOREIGN KEY (initiated_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_event_enhanced emergency_event_enhanced_mustering_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event_enhanced
    ADD CONSTRAINT emergency_event_enhanced_mustering_event_id_fkey FOREIGN KEY (mustering_event_id) REFERENCES public.mustering_event(id);


--
-- Name: emergency_event emergency_event_initiated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event
    ADD CONSTRAINT emergency_event_initiated_by_fkey FOREIGN KEY (initiated_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_event emergency_event_mustering_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_event
    ADD CONSTRAINT emergency_event_mustering_event_id_fkey FOREIGN KEY (mustering_event_id) REFERENCES public.mustering_event(id);


--
-- Name: emergency_notification emergency_notification_emergency_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification
    ADD CONSTRAINT emergency_notification_emergency_event_id_fkey FOREIGN KEY (emergency_event_id) REFERENCES public.emergency_event(id);


--
-- Name: emergency_notification_enhanced emergency_notification_enhanced_emergency_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_notification_enhanced
    ADD CONSTRAINT emergency_notification_enhanced_emergency_event_id_fkey FOREIGN KEY (emergency_event_id) REFERENCES public.emergency_event_enhanced(id);


--
-- Name: emergency_panic_log emergency_panic_log_emergency_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log
    ADD CONSTRAINT emergency_panic_log_emergency_event_id_fkey FOREIGN KEY (emergency_event_id) REFERENCES public.emergency_event(id);


--
-- Name: emergency_panic_log_enhanced emergency_panic_log_enhanced_emergency_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log_enhanced
    ADD CONSTRAINT emergency_panic_log_enhanced_emergency_event_id_fkey FOREIGN KEY (emergency_event_id) REFERENCES public.emergency_event_enhanced(id);


--
-- Name: emergency_panic_log_enhanced emergency_panic_log_enhanced_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log_enhanced
    ADD CONSTRAINT emergency_panic_log_enhanced_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_panic_log_enhanced emergency_panic_log_enhanced_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log_enhanced
    ADD CONSTRAINT emergency_panic_log_enhanced_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_panic_log emergency_panic_log_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_panic_log
    ADD CONSTRAINT emergency_panic_log_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.auth_user(id);


--
-- Name: emergency_plan emergency_plan_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_plan
    ADD CONSTRAINT emergency_plan_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: emergency_device_enhanced emg_dev_enh_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_device_enhanced
    ADD CONSTRAINT emg_dev_enh_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: emergency_template emg_tmpl_muster_zone_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emergency_template
    ADD CONSTRAINT emg_tmpl_muster_zone_fkey FOREIGN KEY (auto_mustering_zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: events events_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: events events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: face face_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.face
    ADD CONSTRAINT face_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: fingerprint fingerprint_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fingerprint
    ADD CONSTRAINT fingerprint_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: flight_log flight_log_transport_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flight_log
    ADD CONSTRAINT flight_log_transport_id_fkey FOREIGN KEY (transport_id) REFERENCES public.transport(id);


--
-- Name: iclock_bio_template iclock_bio_template_source_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_bio_template
    ADD CONSTRAINT iclock_bio_template_source_sn_fkey FOREIGN KEY (source_sn) REFERENCES public.iclock_terminal(sn) ON DELETE SET NULL;


--
-- Name: iclock_devcmd iclock_devcmd_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_devcmd
    ADD CONSTRAINT iclock_devcmd_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: iclock_devcmd iclock_devcmd_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_devcmd
    ADD CONSTRAINT iclock_devcmd_sn_fkey FOREIGN KEY (sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: iclock_operlog iclock_operlog_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_operlog
    ADD CONSTRAINT iclock_operlog_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn) ON DELETE CASCADE;


--
-- Name: iclock_terminal iclock_terminal_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_terminal
    ADD CONSTRAINT iclock_terminal_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: iclock_terminal iclock_terminal_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_terminal
    ADD CONSTRAINT iclock_terminal_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- Name: iclock_transaction iclock_transaction_terminal_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iclock_transaction
    ADD CONSTRAINT iclock_transaction_terminal_sn_fkey FOREIGN KEY (terminal_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: manifest_entry manifest_entry_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manifest_entry
    ADD CONSTRAINT manifest_entry_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id) ON DELETE SET NULL;


--
-- Name: manifest_entry manifest_entry_schedule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manifest_entry
    ADD CONSTRAINT manifest_entry_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.transport_schedule(id) ON DELETE CASCADE;


--
-- Name: mtd_audit_log mtd_audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_audit_log
    ADD CONSTRAINT mtd_audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE SET NULL;


--
-- Name: mtd_certification mtd_certification_cert_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification
    ADD CONSTRAINT mtd_certification_cert_type_id_fkey FOREIGN KEY (cert_type_id) REFERENCES public.mtd_cert_type(id);


--
-- Name: mtd_certification mtd_certification_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification
    ADD CONSTRAINT mtd_certification_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: mtd_certification mtd_certification_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification
    ADD CONSTRAINT mtd_certification_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.auth_user(id);


--
-- Name: mtd_certification mtd_certification_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_certification
    ADD CONSTRAINT mtd_certification_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id) ON DELETE CASCADE;


--
-- Name: mtd_compliance_log mtd_compliance_log_cert_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_compliance_log
    ADD CONSTRAINT mtd_compliance_log_cert_type_id_fkey FOREIGN KEY (cert_type_id) REFERENCES public.mtd_cert_type(id) ON DELETE SET NULL;


--
-- Name: mtd_compliance_log mtd_compliance_log_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_compliance_log
    ADD CONSTRAINT mtd_compliance_log_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: mtd_compliance_log mtd_compliance_log_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_compliance_log
    ADD CONSTRAINT mtd_compliance_log_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: mtd_induction_record mtd_induction_record_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record
    ADD CONSTRAINT mtd_induction_record_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: mtd_induction_record mtd_induction_record_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record
    ADD CONSTRAINT mtd_induction_record_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.mtd_induction_template(id);


--
-- Name: mtd_induction_record mtd_induction_record_trainer_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record
    ADD CONSTRAINT mtd_induction_record_trainer_emp_id_fkey FOREIGN KEY (trainer_emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: mtd_induction_record mtd_induction_record_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_induction_record
    ADD CONSTRAINT mtd_induction_record_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id) ON DELETE CASCADE;


--
-- Name: mtd_medical_record mtd_medical_record_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_medical_record
    ADD CONSTRAINT mtd_medical_record_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: mtd_medical_record mtd_medical_record_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_medical_record
    ADD CONSTRAINT mtd_medical_record_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.auth_user(id);


--
-- Name: mtd_medical_record mtd_medical_record_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_medical_record
    ADD CONSTRAINT mtd_medical_record_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id) ON DELETE CASCADE;


--
-- Name: mtd_ppe_issue mtd_ppe_issue_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_issue
    ADD CONSTRAINT mtd_ppe_issue_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id) ON DELETE CASCADE;


--
-- Name: mtd_ppe_issue mtd_ppe_issue_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_issue
    ADD CONSTRAINT mtd_ppe_issue_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.auth_user(id);


--
-- Name: mtd_ppe_issue mtd_ppe_issue_ppe_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtd_ppe_issue
    ADD CONSTRAINT mtd_ppe_issue_ppe_type_id_fkey FOREIGN KEY (ppe_type_id) REFERENCES public.mtd_ppe_type(id);


--
-- Name: mtg_action_item mtg_action_item_assignee_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_action_item
    ADD CONSTRAINT mtg_action_item_assignee_emp_id_fkey FOREIGN KEY (assignee_emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_action_item mtg_action_item_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_action_item
    ADD CONSTRAINT mtg_action_item_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.mtg_booking(id);


--
-- Name: mtg_action_item mtg_action_item_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_action_item
    ADD CONSTRAINT mtg_action_item_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_attendance mtg_attendance_attendee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendance
    ADD CONSTRAINT mtg_attendance_attendee_id_fkey FOREIGN KEY (attendee_id) REFERENCES public.mtg_attendee(id);


--
-- Name: mtg_attendance mtg_attendance_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendance
    ADD CONSTRAINT mtg_attendance_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.mtg_booking(id);


--
-- Name: mtg_attendance mtg_attendance_device_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendance
    ADD CONSTRAINT mtg_attendance_device_sn_fkey FOREIGN KEY (device_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: mtg_attendee mtg_attendee_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee
    ADD CONSTRAINT mtg_attendee_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.mtg_booking(id);


--
-- Name: mtg_attendee mtg_attendee_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee
    ADD CONSTRAINT mtg_attendee_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_attendee mtg_attendee_pre_reg_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee
    ADD CONSTRAINT mtg_attendee_pre_reg_id_fkey FOREIGN KEY (pre_reg_id) REFERENCES public.vis_pre_registration(id);


--
-- Name: mtg_attendee mtg_attendee_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_attendee
    ADD CONSTRAINT mtg_attendee_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id);


--
-- Name: mtg_booking mtg_booking_approval_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking
    ADD CONSTRAINT mtg_booking_approval_by_fkey FOREIGN KEY (approval_by) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_booking mtg_booking_organizer_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking
    ADD CONSTRAINT mtg_booking_organizer_emp_id_fkey FOREIGN KEY (organizer_emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_booking mtg_booking_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_booking
    ADD CONSTRAINT mtg_booking_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.mtg_room(id);


--
-- Name: mtg_equipment mtg_equipment_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_equipment
    ADD CONSTRAINT mtg_equipment_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.mtg_room(id);


--
-- Name: mtg_minutes mtg_minutes_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_minutes
    ADD CONSTRAINT mtg_minutes_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.mtg_booking(id);


--
-- Name: mtg_minutes mtg_minutes_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_minutes
    ADD CONSTRAINT mtg_minutes_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.personnel_employee(id);


--
-- Name: mtg_room mtg_room_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_room
    ADD CONSTRAINT mtg_room_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: mtg_room mtg_room_door_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_room
    ADD CONSTRAINT mtg_room_door_id_fkey FOREIGN KEY (door_id) REFERENCES public.acc_door(id);


--
-- Name: mtg_room mtg_room_mustering_zone_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mtg_room
    ADD CONSTRAINT mtg_room_mustering_zone_fkey FOREIGN KEY (mustering_zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: mustering_drill_schedule mustering_drill_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_drill_schedule
    ADD CONSTRAINT mustering_drill_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: mustering_escalation_record mustering_escalation_record_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_escalation_record
    ADD CONSTRAINT mustering_escalation_record_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.mustering_event(id);


--
-- Name: mustering_event mustering_event_initiated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_event
    ADD CONSTRAINT mustering_event_initiated_by_fkey FOREIGN KEY (initiated_by) REFERENCES public.auth_user(id);


--
-- Name: mustering_event mustering_event_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_event
    ADD CONSTRAINT mustering_event_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: mustering_expected mustering_expected_dept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_expected
    ADD CONSTRAINT mustering_expected_dept_id_fkey FOREIGN KEY (dept_id) REFERENCES public.personnel_department(id);


--
-- Name: mustering_expected mustering_expected_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_expected
    ADD CONSTRAINT mustering_expected_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.mustering_event(id);


--
-- Name: mustering_expected mustering_expected_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_expected
    ADD CONSTRAINT mustering_expected_shift_id_fkey FOREIGN KEY (shift_id) REFERENCES public.att_shift(id);


--
-- Name: mustering_log mustering_log_device_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_log
    ADD CONSTRAINT mustering_log_device_sn_fkey FOREIGN KEY (device_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: mustering_log mustering_log_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_log
    ADD CONSTRAINT mustering_log_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.mustering_event(id);


--
-- Name: mustering_search_sweep mustering_search_sweep_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_search_sweep
    ADD CONSTRAINT mustering_search_sweep_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.mustering_event(id);


--
-- Name: mustering_search_sweep mustering_search_sweep_searcher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mustering_search_sweep
    ADD CONSTRAINT mustering_search_sweep_searcher_id_fkey FOREIGN KEY (searcher_id) REFERENCES public.auth_user(id);


--
-- Name: onboarding_checklists onboarding_checklists_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_checklists
    ADD CONSTRAINT onboarding_checklists_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.users(id);


--
-- Name: onboarding_checklists onboarding_checklists_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_checklists
    ADD CONSTRAINT onboarding_checklists_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: onboarding_checklists onboarding_checklists_onboarding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_checklists
    ADD CONSTRAINT onboarding_checklists_onboarding_id_fkey FOREIGN KEY (onboarding_id) REFERENCES public.onboardings(id);


--
-- Name: onboarding_documents onboarding_documents_onboarding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_documents
    ADD CONSTRAINT onboarding_documents_onboarding_id_fkey FOREIGN KEY (onboarding_id) REFERENCES public.onboardings(id);


--
-- Name: onboarding_documents onboarding_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_documents
    ADD CONSTRAINT onboarding_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: onboarding_documents onboarding_documents_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_documents
    ADD CONSTRAINT onboarding_documents_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- Name: onboarding_notifications onboarding_notifications_onboarding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_notifications
    ADD CONSTRAINT onboarding_notifications_onboarding_id_fkey FOREIGN KEY (onboarding_id) REFERENCES public.onboardings(id);


--
-- Name: onboarding_notifications onboarding_notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_notifications
    ADD CONSTRAINT onboarding_notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.users(id);


--
-- Name: onboarding_task onboarding_task_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_user(id);


--
-- Name: onboarding_task onboarding_task_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_task
    ADD CONSTRAINT onboarding_task_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: onboarding_tasks onboarding_tasks_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_tasks
    ADD CONSTRAINT onboarding_tasks_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.users(id);


--
-- Name: onboarding_tasks onboarding_tasks_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_tasks
    ADD CONSTRAINT onboarding_tasks_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: onboarding_tasks onboarding_tasks_onboarding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_tasks
    ADD CONSTRAINT onboarding_tasks_onboarding_id_fkey FOREIGN KEY (onboarding_id) REFERENCES public.onboardings(id);


--
-- Name: onboarding_templates onboarding_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboarding_templates
    ADD CONSTRAINT onboarding_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_buddy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_buddy_id_fkey FOREIGN KEY (buddy_id) REFERENCES public.personnel(id);


--
-- Name: onboardings onboardings_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: onboardings onboardings_exit_interview_conducted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_exit_interview_conducted_by_fkey FOREIGN KEY (exit_interview_conducted_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_manager_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_manager_id_fkey FOREIGN KEY (manager_id) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: onboardings onboardings_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id);


--
-- Name: onboardings onboardings_reporting_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_reporting_to_fkey FOREIGN KEY (reporting_to) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: onboardings onboardings_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.onboarding_templates(id);


--
-- Name: onboardings onboardings_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.onboardings
    ADD CONSTRAINT onboardings_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: overtime_record overtime_record_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_record
    ADD CONSTRAINT overtime_record_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_user(id);


--
-- Name: overtime_record overtime_record_emp_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_record
    ADD CONSTRAINT overtime_record_emp_code_fkey FOREIGN KEY (emp_code) REFERENCES public.personnel_employee(emp_code);


--
-- Name: overtime_record overtime_record_overtime_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_record
    ADD CONSTRAINT overtime_record_overtime_rule_id_fkey FOREIGN KEY (overtime_rule_id) REFERENCES public.overtime_rule(id);


--
-- Name: overtime_rule overtime_rule_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rule
    ADD CONSTRAINT overtime_rule_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: overtime_rule overtime_rule_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.overtime_rule
    ADD CONSTRAINT overtime_rule_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.personnel_department(id);


--
-- Name: pay_audit_log pay_audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_audit_log
    ADD CONSTRAINT pay_audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: pay_calculation_log pay_calculation_log_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_calculation_log
    ADD CONSTRAINT pay_calculation_log_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: pay_calculation_log pay_calculation_log_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_calculation_log
    ADD CONSTRAINT pay_calculation_log_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel(id);


--
-- Name: pay_calculation_log pay_calculation_log_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_calculation_log
    ADD CONSTRAINT pay_calculation_log_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.pay_period(id);


--
-- Name: pay_contractor_rate pay_contractor_rate_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_contractor_rate
    ADD CONSTRAINT pay_contractor_rate_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id);


--
-- Name: pay_contractor_rate pay_contractor_rate_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_contractor_rate
    ADD CONSTRAINT pay_contractor_rate_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendors(id);


--
-- Name: pay_item pay_item_structure_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_item
    ADD CONSTRAINT pay_item_structure_id_fkey FOREIGN KEY (structure_id) REFERENCES public.pay_structure(id);


--
-- Name: pay_loan pay_loan_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan
    ADD CONSTRAINT pay_loan_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: pay_loan_deduction pay_loan_deduction_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction
    ADD CONSTRAINT pay_loan_deduction_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel(id);


--
-- Name: pay_loan_deduction pay_loan_deduction_loan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction
    ADD CONSTRAINT pay_loan_deduction_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.pay_loan(id);


--
-- Name: pay_loan_deduction pay_loan_deduction_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction
    ADD CONSTRAINT pay_loan_deduction_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.pay_period(id);


--
-- Name: pay_loan_deduction pay_loan_deduction_salary_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan_deduction
    ADD CONSTRAINT pay_loan_deduction_salary_id_fkey FOREIGN KEY (salary_id) REFERENCES public.pay_salary(id);


--
-- Name: pay_loan pay_loan_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_loan
    ADD CONSTRAINT pay_loan_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel(id);


--
-- Name: pay_payslip_template pay_payslip_template_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_payslip_template
    ADD CONSTRAINT pay_payslip_template_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: pay_period pay_period_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_period
    ADD CONSTRAINT pay_period_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.users(id);


--
-- Name: pay_period pay_period_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_period
    ADD CONSTRAINT pay_period_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: pay_salary pay_salary_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: pay_salary pay_salary_calc_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_calc_by_fkey FOREIGN KEY (calc_by) REFERENCES public.users(id);


--
-- Name: pay_salary pay_salary_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_emp_id_fkey FOREIGN KEY (emp_id) REFERENCES public.personnel(id);


--
-- Name: pay_salary_item pay_salary_item_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary_item
    ADD CONSTRAINT pay_salary_item_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.pay_item(id);


--
-- Name: pay_salary_item pay_salary_item_salary_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary_item
    ADD CONSTRAINT pay_salary_item_salary_id_fkey FOREIGN KEY (salary_id) REFERENCES public.pay_salary(id);


--
-- Name: pay_salary pay_salary_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.pay_period(id);


--
-- Name: pay_salary pay_salary_structure_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_structure_id_fkey FOREIGN KEY (structure_id) REFERENCES public.pay_structure(id);


--
-- Name: pay_salary pay_salary_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_salary
    ADD CONSTRAINT pay_salary_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- Name: pay_structure_assign pay_structure_assign_structure_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure_assign
    ADD CONSTRAINT pay_structure_assign_structure_id_fkey FOREIGN KEY (structure_id) REFERENCES public.pay_structure(id);


--
-- Name: pay_structure pay_structure_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_structure
    ADD CONSTRAINT pay_structure_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: pay_zone_allowance pay_zone_allowance_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_zone_allowance
    ADD CONSTRAINT pay_zone_allowance_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.zones(id);


--
-- Name: pay_zone_allowance pay_zone_allowance_structure_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_zone_allowance
    ADD CONSTRAINT pay_zone_allowance_structure_id_fkey FOREIGN KEY (structure_id) REFERENCES public.pay_structure(id);


--
-- Name: personnel_assignments personnel_assignments_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_assignments
    ADD CONSTRAINT personnel_assignments_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: personnel personnel_current_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_current_zone_id_fkey FOREIGN KEY (current_zone_id) REFERENCES public.zones(id);


--
-- Name: personnel_department personnel_department_default_shift_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_department
    ADD CONSTRAINT personnel_department_default_shift_id_fkey FOREIGN KEY (default_shift_id) REFERENCES public.att_shift(id) ON DELETE SET NULL;


--
-- Name: personnel personnel_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: personnel_department personnel_department_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_department
    ADD CONSTRAINT personnel_department_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.personnel_department(id);


--
-- Name: personnel_employee personnel_employee_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_employee
    ADD CONSTRAINT personnel_employee_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: personnel_employee personnel_employee_dept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel_employee
    ADD CONSTRAINT personnel_employee_dept_id_fkey FOREIGN KEY (dept_id) REFERENCES public.departments(id);


--
-- Name: personnel personnel_primary_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_primary_role_id_fkey FOREIGN KEY (primary_role_id) REFERENCES public.roles(id);


--
-- Name: personnel personnel_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personnel
    ADD CONSTRAINT personnel_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: pob_status pob_status_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pob_status
    ADD CONSTRAINT pob_status_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: resignation_documents resignation_documents_resignation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_documents
    ADD CONSTRAINT resignation_documents_resignation_id_fkey FOREIGN KEY (resignation_id) REFERENCES public.resignations(id);


--
-- Name: resignation_documents resignation_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_documents
    ADD CONSTRAINT resignation_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: resignation_documents resignation_documents_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_documents
    ADD CONSTRAINT resignation_documents_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id);


--
-- Name: resignation_notifications resignation_notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_notifications
    ADD CONSTRAINT resignation_notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.users(id);


--
-- Name: resignation_notifications resignation_notifications_resignation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_notifications
    ADD CONSTRAINT resignation_notifications_resignation_id_fkey FOREIGN KEY (resignation_id) REFERENCES public.resignations(id);


--
-- Name: resignation_tasks resignation_tasks_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_tasks
    ADD CONSTRAINT resignation_tasks_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.users(id);


--
-- Name: resignation_tasks resignation_tasks_resignation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_tasks
    ADD CONSTRAINT resignation_tasks_resignation_id_fkey FOREIGN KEY (resignation_id) REFERENCES public.resignations(id);


--
-- Name: resignation_templates resignation_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignation_templates
    ADD CONSTRAINT resignation_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_assets_return_conducted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_assets_return_conducted_by_fkey FOREIGN KEY (assets_return_conducted_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_completed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_completed_by_fkey FOREIGN KEY (completed_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_exit_interview_conducted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_exit_interview_conducted_by_fkey FOREIGN KEY (exit_interview_conducted_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_financial_clearance_conducted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_financial_clearance_conducted_by_fkey FOREIGN KEY (financial_clearance_conducted_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_handover_conducted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_handover_conducted_by_fkey FOREIGN KEY (handover_conducted_by) REFERENCES public.users(id);


--
-- Name: resignations resignations_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: resignations resignations_system_access_revoked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resignations
    ADD CONSTRAINT resignations_system_access_revoked_by_fkey FOREIGN KEY (system_access_revoked_by) REFERENCES public.users(id);


--
-- Name: role_assignments role_assignments_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_assignments
    ADD CONSTRAINT role_assignments_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id) ON DELETE CASCADE;


--
-- Name: role_assignments role_assignments_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_assignments
    ADD CONSTRAINT role_assignments_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_permission_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_code_fkey FOREIGN KEY (permission_code) REFERENCES public.permissions(code) ON DELETE CASCADE;


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: rpt_export_log rpt_export_log_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_export_log
    ADD CONSTRAINT rpt_export_log_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.rpt_template(id);


--
-- Name: rpt_export_log rpt_export_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_export_log
    ADD CONSTRAINT rpt_export_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id);


--
-- Name: rpt_favorite rpt_favorite_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_favorite
    ADD CONSTRAINT rpt_favorite_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.rpt_template(id);


--
-- Name: rpt_favorite rpt_favorite_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_favorite
    ADD CONSTRAINT rpt_favorite_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id);


--
-- Name: rpt_schedule rpt_schedule_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_schedule
    ADD CONSTRAINT rpt_schedule_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: rpt_schedule rpt_schedule_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_schedule
    ADD CONSTRAINT rpt_schedule_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.rpt_template(id);


--
-- Name: rpt_template rpt_template_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_template
    ADD CONSTRAINT rpt_template_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: rpt_user_preset rpt_user_preset_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_user_preset
    ADD CONSTRAINT rpt_user_preset_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.rpt_template(id);


--
-- Name: rpt_user_preset rpt_user_preset_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rpt_user_preset
    ADD CONSTRAINT rpt_user_preset_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id);


--
-- Name: ssr ssr_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssr
    ADD CONSTRAINT ssr_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.auth_user(id);


--
-- Name: ssr ssr_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ssr
    ADD CONSTRAINT ssr_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.personnel_employee(id);


--
-- Name: sys_renewal_log sys_renewal_log_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_renewal_log
    ADD CONSTRAINT sys_renewal_log_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.sys_subscription(id) ON DELETE CASCADE;


--
-- Name: sys_role_permissions sys_role_permissions_permission_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_role_permissions
    ADD CONSTRAINT sys_role_permissions_permission_code_fkey FOREIGN KEY (permission_code) REFERENCES public.sys_permissions(code) ON DELETE CASCADE;


--
-- Name: sys_role_permissions sys_role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_role_permissions
    ADD CONSTRAINT sys_role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.sys_roles(id) ON DELETE CASCADE;


--
-- Name: sys_user_roles sys_user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sys_user_roles
    ADD CONSTRAINT sys_user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.sys_roles(id) ON DELETE CASCADE;


--
-- Name: transport_assignments transport_assignments_booked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_assignments
    ADD CONSTRAINT transport_assignments_booked_by_fkey FOREIGN KEY (booked_by) REFERENCES public.users(id);


--
-- Name: transport_assignments transport_assignments_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_assignments
    ADD CONSTRAINT transport_assignments_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: transport_crew transport_crew_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_crew
    ADD CONSTRAINT transport_crew_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel_employee(id);


--
-- Name: transport_crew transport_crew_transport_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_crew
    ADD CONSTRAINT transport_crew_transport_id_fkey FOREIGN KEY (transport_id) REFERENCES public.transport(id);


--
-- Name: transport_inventory transport_inventory_transport_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_inventory
    ADD CONSTRAINT transport_inventory_transport_id_fkey FOREIGN KEY (transport_id) REFERENCES public.transport(id);


--
-- Name: transport_maintenance transport_maintenance_transport_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_maintenance
    ADD CONSTRAINT transport_maintenance_transport_id_fkey FOREIGN KEY (transport_id) REFERENCES public.transport(id);


--
-- Name: transport_schedule transport_schedule_transport_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transport_schedule
    ADD CONSTRAINT transport_schedule_transport_id_fkey FOREIGN KEY (transport_id) REFERENCES public.transport(id);


--
-- Name: user_extensions user_extensions_default_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_extensions
    ADD CONSTRAINT user_extensions_default_role_id_fkey FOREIGN KEY (default_role_id) REFERENCES public.sys_roles(id);


--
-- Name: user_roles user_roles_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.users(id);


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: vis_blacklist vis_blacklist_added_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_blacklist
    ADD CONSTRAINT vis_blacklist_added_by_fkey FOREIGN KEY (added_by) REFERENCES public.auth_user(id);


--
-- Name: vis_pre_registration vis_pre_registration_approval_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_approval_by_fkey FOREIGN KEY (approval_by) REFERENCES public.auth_user(id);


--
-- Name: vis_pre_registration vis_pre_registration_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: vis_pre_registration vis_pre_registration_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: vis_pre_registration vis_pre_registration_host_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_host_emp_id_fkey FOREIGN KEY (host_emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: vis_pre_registration vis_pre_registration_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_pre_registration
    ADD CONSTRAINT vis_pre_registration_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id);


--
-- Name: vis_type vis_type_access_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_type
    ADD CONSTRAINT vis_type_access_level_id_fkey FOREIGN KEY (access_level_id) REFERENCES public.acc_level(id);


--
-- Name: vis_type vis_type_mustering_zone_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_type
    ADD CONSTRAINT vis_type_mustering_zone_fkey FOREIGN KEY (mustering_zone_id) REFERENCES public.zones(id) ON DELETE SET NULL;


--
-- Name: vis_visit_log vis_visit_log_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.personnel_area(id);


--
-- Name: vis_visit_log vis_visit_log_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.auth_user(id);


--
-- Name: vis_visit_log vis_visit_log_device_sn_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_device_sn_fkey FOREIGN KEY (device_sn) REFERENCES public.iclock_terminal(sn);


--
-- Name: vis_visit_log vis_visit_log_host_emp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_host_emp_id_fkey FOREIGN KEY (host_emp_id) REFERENCES public.personnel_employee(id);


--
-- Name: vis_visit_log vis_visit_log_pre_reg_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_pre_reg_id_fkey FOREIGN KEY (pre_reg_id) REFERENCES public.vis_pre_registration(id);


--
-- Name: vis_visit_log vis_visit_log_visitor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visit_log
    ADD CONSTRAINT vis_visit_log_visitor_id_fkey FOREIGN KEY (visitor_id) REFERENCES public.vis_visitor(id);


--
-- Name: vis_visitor vis_visitor_visitor_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vis_visitor
    ADD CONSTRAINT vis_visitor_visitor_type_id_fkey FOREIGN KEY (visitor_type_id) REFERENCES public.vis_type(id);


--
-- Name: zone_personnel_assignments zone_personnel_assignments_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_assignments
    ADD CONSTRAINT zone_personnel_assignments_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: zone_personnel_assignments zone_personnel_assignments_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_assignments
    ADD CONSTRAINT zone_personnel_assignments_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: zone_personnel_assignments zone_personnel_assignments_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_assignments
    ADD CONSTRAINT zone_personnel_assignments_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- Name: zone_personnel_tracking zone_personnel_tracking_personnel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_tracking
    ADD CONSTRAINT zone_personnel_tracking_personnel_id_fkey FOREIGN KEY (personnel_id) REFERENCES public.personnel(id);


--
-- Name: zone_personnel_tracking zone_personnel_tracking_previous_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_tracking
    ADD CONSTRAINT zone_personnel_tracking_previous_zone_id_fkey FOREIGN KEY (previous_zone_id) REFERENCES public.zones(id);


--
-- Name: zone_personnel_tracking zone_personnel_tracking_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_personnel_tracking
    ADD CONSTRAINT zone_personnel_tracking_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- Name: zone_reader_assignments zone_reader_assignments_reader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_reader_assignments
    ADD CONSTRAINT zone_reader_assignments_reader_id_fkey FOREIGN KEY (reader_id) REFERENCES public.devices(id);


--
-- Name: zone_reader_assignments zone_reader_assignments_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zone_reader_assignments
    ADD CONSTRAINT zone_reader_assignments_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 8sJI45dH4qooY6FT7uA37453EhKUo2n9tN01iotzWdjYJSMq8eRDNbNat367Mv5



--
-- Access-Control Controllers (LAN inBio/C3 panels) and their reader ports.
-- Separate from iclock_terminal (ADMS/Horus readers): one controller = one IP,
-- driving many door readers identified by (door_no, direction). See
-- backend/app/models/access_controller.py.
--

CREATE TABLE IF NOT EXISTS public.access_controllers (
    id                integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name              varchar(100) NOT NULL,
    serial_number     varchar(64),
    model             varchar(64),
    manufacturer      varchar(64) DEFAULT 'ZKTeco',
    ip_address        varchar(45) NOT NULL,
    port              integer NOT NULL DEFAULT 4370,
    comm_password     varchar(64),
    door_count        integer NOT NULL DEFAULT 1,
    status            varchar(20) NOT NULL DEFAULT 'offline',
    last_seen         timestamptz,
    last_error        varchar(255),
    poll_enabled      boolean NOT NULL DEFAULT false,
    poll_interval_sec integer NOT NULL DEFAULT 5,
    notes             text,
    created_at        timestamptz DEFAULT now(),
    updated_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_access_controllers_ip_address ON public.access_controllers (ip_address);
CREATE INDEX IF NOT EXISTS ix_access_controllers_serial_number ON public.access_controllers (serial_number);

CREATE TABLE IF NOT EXISTS public.access_readers (
    id            integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    controller_id integer NOT NULL REFERENCES public.access_controllers(id) ON DELETE CASCADE,
    door_no       integer NOT NULL,
    direction     varchar(5) NOT NULL,
    name          varchar(100),
    zone_id       integer REFERENCES public.zones(id),
    status        varchar(20) NOT NULL DEFAULT 'active',
    last_event_at timestamptz,
    created_at    timestamptz DEFAULT now(),
    updated_at    timestamptz DEFAULT now(),
    CONSTRAINT uq_reader_controller_door_dir UNIQUE (controller_id, door_no, direction)
);

CREATE INDEX IF NOT EXISTS ix_access_readers_controller_id ON public.access_readers (controller_id);
CREATE INDEX IF NOT EXISTS ix_access_readers_zone_id ON public.access_readers (zone_id);


--
-- Per-employee compensation + statutory identifiers (Phase-1 NG payroll).
-- Replaces structure-level/hardcoded basic pay with individual salary components
-- and the IDs needed to remit PAYE/pension. See backend/app/models/payroll.py.
--
CREATE TABLE IF NOT EXISTS public.pay_employee_compensation (
    id               integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    emp_id           integer NOT NULL REFERENCES public.personnel(id),
    basic            numeric(14,2) NOT NULL DEFAULT 0,
    housing          numeric(14,2) NOT NULL DEFAULT 0,
    transport        numeric(14,2) NOT NULL DEFAULT 0,
    other_allowances numeric(14,2) NOT NULL DEFAULT 0,
    nhis             numeric(14,2) NOT NULL DEFAULT 0,
    life_assurance   numeric(14,2) NOT NULL DEFAULT 0,
    currency         varchar(3) NOT NULL DEFAULT 'NGN',
    grade            varchar(50),
    nhf_enabled      boolean DEFAULT true,
    tin              varchar(30),
    rsa_pin          varchar(30),
    pfa_name         varchar(100),
    nhf_number       varchar(30),
    tax_state        varchar(50),
    bank_name        varchar(100),
    bank_account_no  varchar(20),
    effective_date   date,
    end_date         date,
    is_active        boolean DEFAULT true,
    created_at       timestamptz DEFAULT now(),
    updated_at       timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pay_emp_comp_emp_id ON public.pay_employee_compensation (emp_id);


-- Payroll approval actor columns are soft references (auth is auth_user, not users).
ALTER TABLE public.pay_salary DROP CONSTRAINT IF EXISTS pay_salary_calc_by_fkey;
ALTER TABLE public.pay_salary DROP CONSTRAINT IF EXISTS pay_salary_verified_by_fkey;
ALTER TABLE public.pay_salary DROP CONSTRAINT IF EXISTS pay_salary_approved_by_fkey;


-- Off-cycle pay adjustments (arrears / bonus / one-off deductions).
CREATE TABLE IF NOT EXISTS public.pay_adjustment (
    id         integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    emp_id     integer NOT NULL REFERENCES public.personnel(id),
    period_id  integer NOT NULL REFERENCES public.pay_period(id),
    name       varchar(80) NOT NULL,
    amount     numeric(14,2) NOT NULL,
    adj_type   varchar(10) NOT NULL DEFAULT 'earning',
    is_taxable boolean DEFAULT true,
    reason     text,
    is_active  boolean DEFAULT true,
    created_by integer,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pay_adjustment_period ON public.pay_adjustment (period_id, emp_id);


-- HR-integration connector is fully config-driven (auth/payload/field mapping in JSONB).
ALTER TABLE public.hr_integration_config ADD COLUMN IF NOT EXISTS options jsonb;


-- Business Central connector is config-driven (api route / company path / entity / field map).
ALTER TABLE public.bc_integration_config ADD COLUMN IF NOT EXISTS options jsonb;

-- access controller physical location
ALTER TABLE public.access_controllers ADD COLUMN IF NOT EXISTS location varchar(255);

--
-- Land Journey Management (JMP) — added 2026-07-11
--
CREATE TABLE IF NOT EXISTS public.journey_plan (
    id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    reference varchar(30) UNIQUE,
    origin varchar(150) NOT NULL,
    destination varchar(150) NOT NULL,
    route_description text,
    distance_km double precision,
    purpose varchar(200),
    driver_name varchar(150),
    driver_license varchar(60),
    driver_personnel_id integer REFERENCES public.personnel(id) ON DELETE SET NULL,
    vehicle_reg varchar(60),
    vehicle_type varchar(60),
    passengers jsonb,
    passenger_count integer DEFAULT 0,
    planned_departure timestamptz NOT NULL,
    planned_arrival timestamptz,
    actual_departure timestamptz,
    actual_arrival timestamptz,
    checkin_interval_min integer DEFAULT 60,
    last_checkin_at timestamptz,
    next_checkin_due timestamptz,
    risk_level varchar(10) DEFAULT 'LOW',
    risk_factors jsonb,
    risk_notes text,
    vehicle_check jsonb,
    vehicle_check_ok boolean DEFAULT false,
    status varchar(20) DEFAULT 'DRAFT',
    approved_by_id integer,
    approved_at timestamptz,
    rejection_reason text,
    created_by_id integer,
    notes text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_journey_plan_status ON public.journey_plan(status);
CREATE TABLE IF NOT EXISTS public.journey_checkin (
    id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    journey_id integer NOT NULL REFERENCES public.journey_plan(id) ON DELETE CASCADE,
    checkin_time timestamptz DEFAULT now(),
    location varchar(150),
    status varchar(20) DEFAULT 'OK',
    reported_by varchar(150),
    notes text,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_journey_checkin_journey ON public.journey_checkin(journey_id);

-- Site mobilisation (replaces the generic HR onboarding, which duplicated SeamlessHR):
-- one row per person being readied for site. Most checklist items are read live from
-- the records; `checks` holds the ones HSE confirms by hand (induction, PPE, accommodation).
CREATE TABLE IF NOT EXISTS site_mobilisation (
    id              SERIAL PRIMARY KEY,
    personnel_id    INTEGER NOT NULL REFERENCES personnel(id) ON DELETE CASCADE,
    mobilise_date   DATE NOT NULL,
    status          VARCHAR(12) NOT NULL DEFAULT 'PREPARING',   -- PREPARING | MOBILISED | CANCELLED
    checks          JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes           TEXT,
    override_reason TEXT,                                      -- mobilised with items outstanding
    outstanding     JSONB,                                     -- what was outstanding at that moment
    created_by      VARCHAR(150),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mobilised_at    TIMESTAMPTZ,
    mobilised_by    VARCHAR(150)
);
CREATE INDEX IF NOT EXISTS ix_site_mobilisation_person ON site_mobilisation (personnel_id, status);
