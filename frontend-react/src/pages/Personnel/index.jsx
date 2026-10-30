import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

import PersonnelList          from './PersonnelList';
import DepartmentTree         from './Department/DepartmentTree';
import PositionList           from './Position/PositionList';
import ResignationList        from './Resignation/ResignationList';
import CustomAttributes       from './CustomAttributes/CustomAttributes';
import SiteMobilisation       from './Mobilisation/SiteMobilisation';
import VendorManagement       from './Vendor/VendorManagement';
import PersonnelDetail        from './PersonnelDetail';
import LeaveManagement        from './LeaveManagement/LeaveManagement';
import TrainingManagement     from './TrainingManagement/TrainingManagement';
import PerformanceManagement  from './PerformanceManagement/PerformanceManagement';
import DisciplinaryManagement from './DisciplinaryManagement/DisciplinaryManagement';
import PromotionTransfer      from './PromotionTransfer/PromotionTransfer';
import EmploymentContract     from './EmploymentContract/EmploymentContract';
import BenefitsManagement     from './BenefitsManagement/BenefitsManagement';
import ShiftManagement        from './ShiftManagement/ShiftManagement';
import OvertimeManagement     from './OvertimeManagement/OvertimeManagement';

const Personnel = () => (
  <Routes>
    <Route index                          element={<PersonnelList />} />
    <Route path="leave-management"        element={<LeaveManagement />} />
    <Route path="training-management"     element={<TrainingManagement />} />
    <Route path="performance-management"  element={<PerformanceManagement />} />
    <Route path="disciplinary-management" element={<DisciplinaryManagement />} />
    <Route path="promotion-transfer"      element={<PromotionTransfer />} />
    <Route path="employment-contract"     element={<EmploymentContract />} />
    <Route path="benefits-management"     element={<BenefitsManagement />} />
    <Route path="departments"             element={<DepartmentTree />} />
    <Route path="positions"               element={<PositionList />} />
    <Route path="resignation"             element={<ResignationList />} />
    <Route path="custom-attributes"       element={<CustomAttributes />} />
    <Route path="mobilisation"            element={<SiteMobilisation />} />
    <Route path="onboarding"              element={<Navigate to="/personnel/mobilisation" replace />} />
    <Route path="vendors"                 element={<VendorManagement />} />
    <Route path="shift-management"        element={<ShiftManagement />} />
    <Route path="overtime-management"     element={<OvertimeManagement />} />
    <Route path="employee/:id"            element={<PersonnelDetail />} />
    <Route path="*"                       element={<Navigate to="/personnel" replace />} />
  </Routes>
);

export default Personnel;
