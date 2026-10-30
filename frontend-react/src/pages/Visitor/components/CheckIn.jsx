import React, { useState, useRef } from 'react';
import {
  Card, Form, Input, Select, Button, message, Alert, Descriptions, Tag, Divider,
  Row, Col, Tabs, Space, Typography, Checkbox,
} from 'antd';
import {
  LoginOutlined, QrcodeOutlined, UserAddOutlined, SearchOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import visitorAPI from '../../../services/visitorAPI';
import usePersonnel from '../../../hooks/usePersonnel';

const { Text } = Typography;

const ID_TYPE_LABELS = { 0: 'National ID', 1: 'Passport', 2: "Driver's Licence" };

const CheckIn = () => {
  const [preReg, setPreReg]               = useState(null);
  const [returnVisitor, setReturnVisitor] = useState(null); // existing visitor found by lookup
  const [walkInMode, setWalkInMode]       = useState('new'); // 'new' | 'returning'
  const [walkInForm]                      = Form.useForm();
  const [preRegForm]                      = Form.useForm();
  const [lookupForm]                      = Form.useForm();
  const qc                                = useQueryClient();

  const { empOptions } = usePersonnel();

  const { data: typesData } = useQuery({
    queryKey: ['visitor-types'],
    queryFn: () => visitorAPI.getVisitorTypes(),
    staleTime: 60000,
  });
  const typeOptions = (typesData?.data ?? []).map(t => ({ value: t.id, label: t.type_name }));

  // Gate details for every check-in: the physical visitor card handed over (loaded onto
  // the door panels — none = escorted, no door access) and the safety induction.
  const [gate, setGateState] = useState({ card_no: '', induction_done: false });
  // The submit reads the CURRENT card / induction (a ref) — reading state captured in an
  // earlier render sent the old values (induction still 'off' after ticking it).
  const gateRef = useRef(gate);
  const setGate = (fn) => setGateState(g => { const n = typeof fn === 'function' ? fn(g) : fn; gateRef.current = n; return n; });
  const gateFields = (
    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, margin: '12px 0' }}>
      <Input placeholder="Visitor card number (leave empty if escorted, no card)" value={gate.card_no}
        onChange={e => setGate(g => ({ ...g, card_no: e.target.value }))} style={{ marginBottom: 8 }} />
      <Checkbox checked={gate.induction_done} onChange={e => setGate(g => ({ ...g, induction_done: e.target.checked }))}>
        Safety induction done (required for contractor / site visitor types)
      </Checkbox>
    </div>
  );
  const STATUS = { 0: ['gold', 'Waiting for host approval'], 1: ['green', 'Approved'], 2: ['red', 'Rejected'],
                   3: ['blue', 'Already checked in'], 4: ['default', 'Used (checked out)'], 5: ['default', 'Expired'] };

  const checkInMut = useMutation({
    mutationFn: (d) => visitorAPI.checkInVisitor({ ...d, card_no: gateRef.current.card_no.trim() || null, induction_done: gateRef.current.induction_done }),
    onSuccess: () => {
      const card = gateRef.current.card_no.trim();
      message.success(card ? `Visitor checked in — card ${card} is being loaded onto the doors` : 'Visitor checked in (no card — escort only)');
      setGate({ card_no: '', induction_done: false });
      preRegForm.resetFields();
      walkInForm.resetFields();
      lookupForm.resetFields();
      setPreReg(null);
      setReturnVisitor(null);
      setWalkInMode('new');
      qc.invalidateQueries(['visitor-stats']);
      qc.invalidateQueries(['visitor-records']);
      qc.invalidateQueries(['visitor-on-site']);
    },
    onError: (e) => message.error(e.response?.data?.detail || e.message),
  });

  const qrLookupMut = useMutation({
    mutationFn: (qr) => visitorAPI.getQRData(qr),
    onSuccess: (d) => {
      if (d?.data) setPreReg(d.data);
      else message.warning('QR code not found');
    },
    onError: () => message.error('Invalid QR code'),
  });

  const visitorLookupMut = useMutation({
    mutationFn: (params) => visitorAPI.lookupVisitor(params),
    onSuccess: (d) => {
      const visitors = d?.data ?? [];
      if (visitors.length === 0) {
        message.warning('No existing visitor found. Fill in the form below as a new visitor.');
        setReturnVisitor(null);
        setWalkInMode('new');
      } else if (visitors.length === 1) {
        setReturnVisitor(visitors[0]);
        setWalkInMode('returning');
        message.success(`Found: ${visitors[0].full_name}`);
      } else {
        // Multiple matches – take the first (best match)
        setReturnVisitor(visitors[0]);
        setWalkInMode('returning');
        message.info(`${visitors.length} matches found; using first match. Verify below.`);
      }
    },
    onError: () => message.error('Lookup failed'),
  });

  // Pre-registered check-in
  const handlePreRegCheckIn = () => {
    if (!preReg) { message.warning('Scan QR code first'); return; }
    checkInMut.mutate({ qr_code: preReg.qr_code });
  };

  // Walk-in with new visitor
  const handleNewWalkIn = (v) => {
    checkInMut.mutate({
      visitor_data: {
        full_name:       v.full_name,
        phone:           v.phone,
        email:           v.email,
        company:         v.company,
        id_type:         v.id_type ?? 0,
        id_no:           v.id_no,
        visitor_type_id: v.visitor_type_id ?? null,
      },
      host_emp_id: v.host_emp_id,
      area_id:     v.area_id ?? null,
    });
  };

  // Walk-in with existing/returning visitor
  const handleReturningCheckIn = (v) => {
    checkInMut.mutate({
      visitor_id:  returnVisitor.id,
      host_emp_id: v.host_emp_id,
      area_id:     v.area_id ?? null,
    });
  };

  // ── PRE-REGISTERED TAB ───────────────────────────────────────────────────────
  const preRegTabContent = (
    <div style={{ maxWidth: 500 }}>
      <Form form={preRegForm} name="preRegQr" layout="vertical">
        <Form.Item name="qr_code" label="QR Code / Pre-Registration Code" rules={[{ required: true }]}>
          <Input.Search
            placeholder="Scan or type QR code…"
            enterButton={<><QrcodeOutlined /> Lookup</>}
            onSearch={(v) => qrLookupMut.mutate(v)}
            loading={qrLookupMut.isPending}
          />
        </Form.Item>
      </Form>

      {preReg && (
        <>
          <Alert type="success" message="Pre-registration found" style={{ marginBottom: 12 }} />
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="Visitor">{preReg.visitor_name}</Descriptions.Item>
            <Descriptions.Item label="Company">{preReg.company || '—'}</Descriptions.Item>
            <Descriptions.Item label="Host">{preReg.host_name || '—'}</Descriptions.Item>
            <Descriptions.Item label="Date">{preReg.visit_date ? dayjs(preReg.visit_date).format('DD MMM YYYY') : '—'}</Descriptions.Item>
            <Descriptions.Item label="Time">{preReg.visit_time_start} – {preReg.visit_time_end}</Descriptions.Item>
            <Descriptions.Item label="Purpose">{preReg.purpose || '—'}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={(STATUS[preReg.status] || ['default'])[0]}>{(STATUS[preReg.status] || [, `Status ${preReg.status}`])[1]}</Tag>
            </Descriptions.Item>
          </Descriptions>
          {preReg.status === 1 && gateFields}
          <Button
            type="primary"
            icon={<LoginOutlined />}
            style={{ marginTop: 16 }}
            loading={checkInMut.isPending}
            onClick={handlePreRegCheckIn}
            disabled={preReg.status !== 1}
            block
          >
            Confirm Check-In
          </Button>
        </>
      )}
    </div>
  );

  // ── WALK-IN TAB ──────────────────────────────────────────────────────────────
  const walkInTabContent = (
    <div style={{ maxWidth: 560 }}>

      {/* Step 1: Returning visitor lookup */}
      <Card
        size="small"
        title="Step 1 — Check if visitor is already registered"
        style={{ marginBottom: 16 }}
        extra={
          returnVisitor && (
            <Button
              size="small"
              icon={<CloseCircleOutlined />}
              onClick={() => { setReturnVisitor(null); setWalkInMode('new'); }}
            >
              Clear
            </Button>
          )
        }
      >
        <Form form={lookupForm} name="visitorLookup" layout="inline">
          <Form.Item name="phone" style={{ marginBottom: 8 }}>
            <Input placeholder="Phone number" prefix={<SearchOutlined />} style={{ width: 160 }} allowClear />
          </Form.Item>
          <Form.Item name="id_no" style={{ marginBottom: 8 }}>
            <Input placeholder="ID / Passport No" style={{ width: 160 }} allowClear />
          </Form.Item>
          <Form.Item style={{ marginBottom: 8 }}>
            <Button
              icon={<SearchOutlined />}
              loading={visitorLookupMut.isPending}
              onClick={() => {
                const vals = lookupForm.getFieldsValue();
                if (!vals.phone && !vals.id_no) { message.warning('Enter phone or ID to search'); return; }
                visitorLookupMut.mutate({ phone: vals.phone || undefined, id_no: vals.id_no || undefined });
              }}
            >
              Find Visitor
            </Button>
          </Form.Item>
        </Form>

        {returnVisitor && (
          <Alert
            type="success"
            icon={<CheckCircleOutlined />}
            showIcon
            message={
              <Space>
                <Text strong>{returnVisitor.full_name}</Text>
                {returnVisitor.company && <Text type="secondary">· {returnVisitor.company}</Text>}
                <Tag>{returnVisitor.visitor_type?.type_name || 'Visitor'}</Tag>
                <Tag color="blue">{returnVisitor.visitor_code}</Tag>
                <Text type="secondary">{ID_TYPE_LABELS[returnVisitor.id_type]} · {returnVisitor.id_no}</Text>
              </Space>
            }
            style={{ marginTop: 8 }}
          />
        )}
      </Card>

      {/* Step 2: returning visitor – just assign host */}
      {walkInMode === 'returning' && returnVisitor && (
        <Card size="small" title="Step 2 — Assign Host &amp; Check In">
          <Form name="walkInReturning" layout="vertical" onFinish={handleReturningCheckIn}>
            <Form.Item name="host_emp_id" label="Host Employee" rules={[{ required: true }]}>
              <Select
                options={empOptions}
                showSearch
                filterOption={(i, o) => o.label?.toLowerCase().includes(i.toLowerCase())}
                placeholder="Select host…"
              />
            </Form.Item>
            {gateFields}
            <Button type="primary" icon={<LoginOutlined />} htmlType="submit" loading={checkInMut.isPending} block>
              Check In {returnVisitor.full_name}
            </Button>
          </Form>
        </Card>
      )}

      {/* Step 2: new visitor – full form */}
      {walkInMode === 'new' && (
        <Card size="small" title={returnVisitor ? 'New Visitor Form' : 'Step 2 — New Visitor Details'}>
          <Form form={walkInForm} name="walkInNew" layout="vertical" onFinish={handleNewWalkIn} initialValues={{ id_type: 0 }}>
            <Row gutter={12}>
              <Col span={12}><Form.Item name="full_name" label="Full Name" rules={[{ required: true }]}><Input /></Form.Item></Col>
              <Col span={12}><Form.Item name="phone" label="Phone"><Input /></Form.Item></Col>
              <Col span={12}><Form.Item name="email" label="Email"><Input /></Form.Item></Col>
              <Col span={12}><Form.Item name="company" label="Company"><Input /></Form.Item></Col>
              <Col span={12}>
                <Form.Item name="id_type" label="ID Type">
                  <Select options={[
                    { value: 0, label: 'National ID' },
                    { value: 1, label: 'Passport' },
                    { value: 2, label: "Driver's Licence" },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={12}><Form.Item name="id_no" label="ID Number"><Input /></Form.Item></Col>
              <Col span={12}>
                <Form.Item name="visitor_type_id" label="Visitor Type">
                  <Select options={typeOptions} allowClear placeholder="Select type…" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="host_emp_id" label="Host Employee" rules={[{ required: true }]}>
                  <Select
                    options={empOptions}
                    showSearch
                    filterOption={(i, o) => o.label?.toLowerCase().includes(i.toLowerCase())}
                    placeholder="Select host…"
                  />
                </Form.Item>
              </Col>
            </Row>
            {gateFields}
            <Button type="primary" icon={<LoginOutlined />} htmlType="submit" loading={checkInMut.isPending} block>
              Check In (New Visitor)
            </Button>
          </Form>
        </Card>
      )}
    </div>
  );

  return (
    <Card>
      <Tabs
        items={[
          { key: 'pre-reg', label: <span><QrcodeOutlined /> Pre-Registered Visitor</span>, children: preRegTabContent },
          { key: 'walk-in', label: <span><UserAddOutlined /> Walk-in Visitor</span>,       children: walkInTabContent },
        ]}
      />
    </Card>
  );
};

export default CheckIn;
