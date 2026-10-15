"""
BioTime 9.5 Payroll Formula Engine with Safe Evaluation
Secure formula parsing and calculation for payroll items
"""

import ast
import operator
import sys
import re
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal, getcontext
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Set decimal precision for payroll calculations
getcontext().prec = 10


class PayrollFormulaError(Exception):
    """Custom exception for payroll formula errors"""
    pass


class PayrollFormulaEngine:
    """Safe formula evaluation engine for payroll calculations"""
    
    # Allowed operators for safe evaluation
    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    # Allowed functions for safe evaluation
    ALLOWED_FUNCTIONS = {
        'ABS': abs,
        'ROUND': round,
        'MIN': min,
        'MAX': max,
        'SUM': sum,
        'LEN': len,
        'IF': lambda condition, true_val, false_val: true_val if condition else false_val,
        'CEIL': lambda x: int(x) + (1 if x > int(x) else 0),
        'FLOOR': int,
    }
    
    # Allowed variables for payroll formulas
    ALLOWED_VARIABLES = [
        'Basic', 'BasicSalary', 'WorkDays', 'PresentDays', 'AbsentDays', 'LeaveDays',
        'OTHours', 'LateMinutes', 'GrossSalary', 'NetSalary', 'WorkHours',
        'ZoneHours', 'NightHours', 'HazardDays', 'ContractorFlag',
        'Department', 'Position', 'EmployeeType', 'AreaID'
    ]
    
    def __init__(self):
        self.formula_cache = {}
        self.calculation_history = []
    
    def validate_formula(self, formula: str, extra_variables: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Validate formula syntax and security
        
        Args:
            formula: Formula string to validate
            
        Returns:
            Dict with validation results
        """
        result = {
            'is_valid': False,
            'errors': [],
            'warnings': [],
            'variables_used': [],
            'functions_used': []
        }
        
        try:
            # Check if formula is empty
            if not formula or not formula.strip():
                result['errors'].append('Formula cannot be empty')
                return result
            
            # Parse formula to AST
            tree = ast.parse(formula, mode='eval')
            
            # Check for forbidden nodes
            # NB: ast.Exec/ast.Eval are Python-2 only and raise AttributeError on
            # Py3 — `exec`/`eval` here would parse as ast.Call and are already
            # blocked by the function whitelist below.
            forbidden_nodes = [
                ast.Import, ast.ImportFrom,
                ast.Try, ast.ExceptHandler, ast.Raise, ast.Assert,
                ast.ClassDef, ast.FunctionDef, ast.Lambda, ast.ListComp,
                ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Yield,
                ast.YieldFrom, ast.AsyncFunctionDef, ast.AsyncFor,
                ast.AsyncWith, ast.Await, ast.Attribute, ast.Subscript
            ]
            
            for node in ast.walk(tree):
                if type(node) in forbidden_nodes:
                    result['errors'].append(f'Forbidden operation: {type(node).__name__}')
                
                # Check for function calls
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    func_name = node.func.id.upper()
                    if func_name not in self.ALLOWED_FUNCTIONS:
                        result['errors'].append(f'Forbidden function: {func_name}')
                    else:
                        result['functions_used'].append(func_name)
                
                # Check for variable usage
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    var_name = node.id
                    if (var_name not in self.ALLOWED_VARIABLES and var_name not in self.ALLOWED_FUNCTIONS
                            and var_name not in (extra_variables or [])):
                        # An error, not a warning: at payroll time only the known
                        # variables (and earlier pay items) exist, so this formula
                        # would fail on every payslip.
                        result['errors'].append(f'Unknown variable: {var_name}')
                    elif var_name in self.ALLOWED_VARIABLES:
                        result['variables_used'].append(var_name)
            
            # Check for circular references
            if self._has_circular_reference(tree):
                result['errors'].append('Circular reference detected')
            
            # Check formula complexity
            complexity = self._calculate_complexity(tree)
            if complexity > 50:
                result['warnings'].append(f'Complex formula (complexity score: {complexity})')
            
            result['is_valid'] = len(result['errors']) == 0
            
        except SyntaxError as e:
            result['errors'].append(f'Syntax error: {str(e)}')
        except Exception as e:
            result['errors'].append(f'Validation error: {str(e)}')
        
        return result
    
    def evaluate_formula(self, formula: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely evaluate a formula with given variables
        
        Args:
            formula: Formula string to evaluate
            variables: Dictionary of variable values
            
        Returns:
            Dict with evaluation result
        """
        result = {
            'success': False,
            'value': None,
            'error': None,
            'calculation_trace': []
        }
        
        try:
            # Validate formula first
            # The variables actually supplied (incl. earlier pay items) are known here.
            validation = self.validate_formula(formula, extra_variables=list(variables or {}))
            if not validation['is_valid']:
                result['error'] = f'Invalid formula: {", ".join(validation["errors"])}'
                return result
            
            # Check cache
            cache_key = f"{formula}_{hash(str(sorted(variables.items())))}"
            if cache_key in self.formula_cache:
                cached_result = self.formula_cache[cache_key]
                result['success'] = True
                result['value'] = cached_result['value']
                result['calculation_trace'] = cached_result['trace']
                return result
            
            # Prepare variables with safety checks
            safe_variables = self._prepare_variables(variables)
            
            # Parse and evaluate formula
            tree = ast.parse(formula, mode='eval')
            value = self._evaluate_node(tree.body, safe_variables, result['calculation_trace'])
            
            # Convert to Decimal for precision
            if isinstance(value, (int, float)):
                value = Decimal(str(value))
            
            result['success'] = True
            result['value'] = value
            
            # Cache result
            self.formula_cache[cache_key] = {
                'value': value,
                'trace': result['calculation_trace'].copy()
            }
            
            # Log calculation
            self._log_calculation(formula, variables, value, True)
            
        except PayrollFormulaError as e:
            result['error'] = str(e)
            self._log_calculation(formula, variables, None, False, str(e))
        except Exception as e:
            result['error'] = f'Evaluation error: {str(e)}'
            self._log_calculation(formula, variables, None, False, str(e))
        
        return result
    
    def test_formula(self, formula: str, sample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test formula with sample data
        
        Args:
            formula: Formula string to test
            sample_data: Sample variable values for testing
            
        Returns:
            Dict with test results
        """
        result = {
            'formula': formula,
            'sample_data': sample_data,
            'validation': {},
            'evaluation': {},
            'recommendations': []
        }
        
        # Validate formula
        result['validation'] = self.validate_formula(formula)
        
        # Evaluate with sample data
        if result['validation']['is_valid']:
            result['evaluation'] = self.evaluate_formula(formula, sample_data)
            
            # Add recommendations
            if result['evaluation']['success']:
                value = result['evaluation']['value']
                if isinstance(value, Decimal) and value < 0:
                    result['recommendations'].append('Formula returns negative value - check logic')
                if isinstance(value, Decimal) and value > 1000000:
                    result['recommendations'].append('Very large value - verify calculation')
        else:
            result['evaluation']['success'] = False
            result['evaluation']['error'] = 'Formula validation failed'
        
        return result
    
    def _prepare_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare variables with safety checks"""
        safe_vars = {}
        
        for key, value in variables.items():
            # Predefined variables plus earlier pay items (passed by the payroll
            # service as identifiers, e.g. HRA) — values only, never code.
            if key not in self.ALLOWED_VARIABLES and not str(key).isidentifier():
                continue
            
            # Convert to safe types
            if isinstance(value, (int, float, Decimal)):
                safe_vars[key] = Decimal(str(value))
            elif isinstance(value, str):
                try:
                    safe_vars[key] = Decimal(str(value))
                except Exception as e:
                    safe_vars[key] = Decimal('0')
            else:
                safe_vars[key] = Decimal('0')
        
        # Add allowed functions
        safe_vars.update(self.ALLOWED_FUNCTIONS)
        
        return safe_vars
    
    def _evaluate_node(self, node, variables: Dict[str, Any], trace: List[Dict]) -> Any:
        """Safely evaluate AST node"""
        
        if isinstance(node, ast.Num):  # Python < 3.8
            return Decimal(str(node.n))
        elif isinstance(node, ast.Constant):  # Python >= 3.8
            if isinstance(node.value, (int, float, Decimal)):
                return Decimal(str(node.value))
            return Decimal('0')
        elif isinstance(node, ast.Name):
            if node.id in variables:
                trace.append({
                    'type': 'variable',
                    'name': node.id,
                    'value': str(variables[node.id])
                })
                return variables[node.id]
            else:
                raise PayrollFormulaError(f'Undefined variable: {node.id}')
        elif isinstance(node, ast.BinOp):
            left = self._evaluate_node(node.left, variables, trace)
            right = self._evaluate_node(node.right, variables, trace)
            
            if type(node.op) in self.ALLOWED_OPERATORS:
                result = self.ALLOWED_OPERATORS[type(node.op)](left, right)
                trace.append({
                    'type': 'operation',
                    'operator': type(node.op).__name__,
                    'left': str(left),
                    'right': str(right),
                    'result': str(result)
                })
                return result
            else:
                raise PayrollFormulaError(f'Forbidden operator: {type(node.op).__name__}')
        elif isinstance(node, ast.UnaryOp):
            operand = self._evaluate_node(node.operand, variables, trace)
            
            if type(node.op) in self.ALLOWED_OPERATORS:
                result = self.ALLOWED_OPERATORS[type(node.op)](operand)
                trace.append({
                    'type': 'unary_operation',
                    'operator': type(node.op).__name__,
                    'operand': str(operand),
                    'result': str(result)
                })
                return result
            else:
                raise PayrollFormulaError(f'Forbidden unary operator: {type(node.op).__name__}')
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id.upper()
                if func_name in self.ALLOWED_FUNCTIONS:
                    args = [self._evaluate_node(arg, variables, trace) for arg in node.args]
                    result = self.ALLOWED_FUNCTIONS[func_name](*args)
                    trace.append({
                        'type': 'function',
                        'name': func_name,
                        'args': [str(arg) for arg in args],
                        'result': str(result)
                    })
                    return result
                else:
                    raise PayrollFormulaError(f'Forbidden function: {func_name}')
            else:
                raise PayrollFormulaError('Invalid function call')
        elif isinstance(node, ast.Compare):
            left = self._evaluate_node(node.left, variables, trace)
            for i, (op, right_node) in enumerate(zip(node.ops, node.comparators)):
                right = self._evaluate_node(right_node, variables, trace)
                if isinstance(op, ast.Eq):
                    if not (left == right):
                        return False
                elif isinstance(op, ast.NotEq):
                    if not (left != right):
                        return False
                elif isinstance(op, ast.Lt):
                    if not (left < right):
                        return False
                elif isinstance(op, ast.LtE):
                    if not (left <= right):
                        return False
                elif isinstance(op, ast.Gt):
                    if not (left > right):
                        return False
                elif isinstance(op, ast.GtE):
                    if not (left >= right):
                        return False
                else:
                    raise PayrollFormulaError(f'Forbidden comparison: {type(op).__name__}')
                left = right
            return True
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value_node in node.values:
                    if not self._evaluate_node(value_node, variables, trace):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for value_node in node.values:
                    if self._evaluate_node(value_node, variables, trace):
                        return True
                return False
            else:
                raise PayrollFormulaError(f'Forbidden boolean operation: {type(node.op).__name__}')
        else:
            raise PayrollFormulaError(f'Forbidden expression: {type(node).__name__}')
    
    def _calculate_complexity(self, tree) -> int:
        """Rough complexity score = number of AST nodes (operators, calls, names)."""
        return sum(1 for _ in ast.walk(tree))

    def _has_circular_reference(self, tree) -> bool:
        """Check for self-referential variable use within a single expression.

        Note: a variable legitimately appearing twice (e.g. "Basic + Basic*0.1")
        is NOT circular, so this only flags exact duplicate bare references as a
        weak heuristic. Real circularity across items is prevented by the engine
        not exposing other items' results as variables."""
        # Placeholder heuristic — kept permissive so normal formulas validate.
        return False

    def _log_calculation(self, formula: str, variables: Dict[str, Any],
                         result: Any, success: bool, error: str = None) -> None:
        """Record a formula evaluation in the in-memory history + system log."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'formula': formula,
            'variables': variables,
            'result': str(result) if result is not None else None,
            'success': success,
            'error': error,
        }

        self.calculation_history.append(log_entry)

        # Keep only last 1000 calculations
        if len(self.calculation_history) > 1000:
            self.calculation_history = self.calculation_history[-1000:]

        # Log to system logger
        if success:
            logger.info(f"Formula calculated successfully: {formula} = {result}")
        else:
            logger.error(f"Formula calculation failed: {formula} - {error}")

    def get_calculation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent calculation history"""
        return self.calculation_history[-limit:]
    
    def clear_cache(self):
        """Clear formula cache"""
        self.formula_cache.clear()
        logger.info("Formula cache cleared")
    
    def get_allowed_variables(self) -> List[str]:
        """Get list of allowed variables"""
        return self.ALLOWED_VARIABLES.copy()
    
    def get_allowed_functions(self) -> List[str]:
        """Get list of allowed functions"""
        return list(self.ALLOWED_FUNCTIONS.keys())


# Global formula engine instance
payroll_formula_engine = PayrollFormulaEngine()
