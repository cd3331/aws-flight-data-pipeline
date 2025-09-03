#!/usr/bin/env python3

import json
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CostProjection:
    period: str
    current_cost: float
    optimized_cost: float
    savings: float
    cumulative_savings: float
    confidence_interval: Tuple[float, float]

@dataclass
class OptimizationInvestment:
    optimization_type: str
    implementation_cost: float
    ongoing_maintenance_cost: float
    time_to_implement_days: int
    resource_requirements: Dict[str, int]
    risk_factors: List[str]

@dataclass
class ROIAnalysis:
    optimization_name: str
    investment: OptimizationInvestment
    monthly_savings: float
    annual_savings: float
    payback_period_months: float
    roi_percent: float
    npv_5_year: float
    irr_percent: float
    break_even_point: str
    risk_adjusted_roi: float

@dataclass
class BusinessImpactMetrics:
    cost_avoidance_annual: float
    efficiency_improvement_percent: float
    resource_capacity_freed: Dict[str, float]
    performance_improvements: Dict[str, float]
    compliance_benefits: List[str]
    scalability_benefits: List[str]

@dataclass
class ROIReport:
    report_id: str
    timestamp: str
    analysis_period: str
    optimizations_analyzed: List[ROIAnalysis]
    portfolio_summary: Dict[str, Any]
    cost_projections: List[CostProjection]
    business_impact: BusinessImpactMetrics
    recommendations: List[Dict[str, Any]]

class ROICalculator:
    def __init__(self, discount_rate: float = 0.08, risk_free_rate: float = 0.03):
        """
        Initialize ROI Calculator with financial parameters.
        
        Args:
            discount_rate: Annual discount rate for NPV calculations (default 8%)
            risk_free_rate: Risk-free rate for risk adjustments (default 3%)
        """
        self.discount_rate = discount_rate
        self.risk_free_rate = risk_free_rate
        
        # Standard optimization types and their typical characteristics
        self.optimization_templates = {
            's3_lifecycle': {
                'implementation_cost': 5000,
                'maintenance_cost_monthly': 200,
                'time_to_implement': 14,
                'risk_factors': ['Data access pattern changes', 'Retrieval time impact'],
                'confidence_multiplier': 0.85
            },
            'lambda_optimization': {
                'implementation_cost': 3000,
                'maintenance_cost_monthly': 150,
                'time_to_implement': 7,
                'risk_factors': ['Performance impact', 'Cold start increases'],
                'confidence_multiplier': 0.90
            },
            'query_optimization': {
                'implementation_cost': 8000,
                'maintenance_cost_monthly': 300,
                'time_to_implement': 21,
                'risk_factors': ['Query performance changes', 'Schema evolution'],
                'confidence_multiplier': 0.80
            },
            'monitoring_dashboard': {
                'implementation_cost': 4000,
                'maintenance_cost_monthly': 100,
                'time_to_implement': 10,
                'risk_factors': ['Alert fatigue', 'Dashboard maintenance'],
                'confidence_multiplier': 0.95
            }
        }

    def calculate_optimization_roi(self, optimization_type: str, monthly_savings: float,
                                 custom_investment: Optional[OptimizationInvestment] = None) -> ROIAnalysis:
        """Calculate ROI for a specific optimization."""
        
        # Get or create investment details
        if custom_investment:
            investment = custom_investment
        else:
            investment = self._create_standard_investment(optimization_type)
        
        # Calculate financial metrics
        annual_savings = monthly_savings * 12
        
        # Total investment (implementation + first year maintenance)
        total_first_year_investment = (
            investment.implementation_cost + 
            (investment.ongoing_maintenance_cost * 12)
        )
        
        # Payback period
        if monthly_savings > 0:
            payback_months = total_first_year_investment / monthly_savings
        else:
            payback_months = float('inf')
        
        # ROI calculation (5-year horizon)
        five_year_savings = annual_savings * 5
        five_year_maintenance = investment.ongoing_maintenance_cost * 12 * 5
        total_investment = investment.implementation_cost + five_year_maintenance
        
        roi_percent = ((five_year_savings - total_investment) / total_investment * 100) if total_investment > 0 else 0
        
        # NPV calculation (5-year)
        npv_5_year = self._calculate_npv(annual_savings, investment, 5)
        
        # IRR calculation
        irr_percent = self._calculate_irr(annual_savings, investment, 5)
        
        # Risk-adjusted ROI
        confidence_multiplier = self.optimization_templates.get(
            optimization_type, {'confidence_multiplier': 0.85}
        )['confidence_multiplier']
        risk_adjusted_roi = roi_percent * confidence_multiplier
        
        # Break-even point
        break_even_point = self._calculate_break_even_point(monthly_savings, investment)
        
        return ROIAnalysis(
            optimization_name=optimization_type,
            investment=investment,
            monthly_savings=monthly_savings,
            annual_savings=annual_savings,
            payback_period_months=payback_months,
            roi_percent=roi_percent,
            npv_5_year=npv_5_year,
            irr_percent=irr_percent,
            break_even_point=break_even_point,
            risk_adjusted_roi=risk_adjusted_roi
        )

    def _create_standard_investment(self, optimization_type: str) -> OptimizationInvestment:
        """Create standard investment profile for optimization type."""
        template = self.optimization_templates.get(optimization_type, {
            'implementation_cost': 5000,
            'maintenance_cost_monthly': 200,
            'time_to_implement': 14,
            'risk_factors': ['Implementation risk', 'Ongoing maintenance'],
        })
        
        return OptimizationInvestment(
            optimization_type=optimization_type,
            implementation_cost=template['implementation_cost'],
            ongoing_maintenance_cost=template['maintenance_cost_monthly'],
            time_to_implement_days=template['time_to_implement'],
            resource_requirements={
                'engineer_hours': template['time_to_implement'] * 6,
                'architect_hours': template['time_to_implement'] * 2,
                'testing_hours': template['time_to_implement'] * 4
            },
            risk_factors=template['risk_factors']
        )

    def _calculate_npv(self, annual_savings: float, investment: OptimizationInvestment, years: int) -> float:
        """Calculate Net Present Value over specified years."""
        npv = -investment.implementation_cost  # Initial investment
        
        for year in range(1, years + 1):
            # Annual cash flow (savings - maintenance)
            annual_cash_flow = annual_savings - (investment.ongoing_maintenance_cost * 12)
            
            # Discount to present value
            discounted_cash_flow = annual_cash_flow / ((1 + self.discount_rate) ** year)
            npv += discounted_cash_flow
        
        return npv

    def _calculate_irr(self, annual_savings: float, investment: OptimizationInvestment, years: int) -> float:
        """Calculate Internal Rate of Return using Newton-Raphson method."""
        
        def npv_at_rate(rate: float) -> float:
            npv = -investment.implementation_cost
            for year in range(1, years + 1):
                annual_cash_flow = annual_savings - (investment.ongoing_maintenance_cost * 12)
                npv += annual_cash_flow / ((1 + rate) ** year)
            return npv
        
        def npv_derivative(rate: float) -> float:
            derivative = 0
            for year in range(1, years + 1):
                annual_cash_flow = annual_savings - (investment.ongoing_maintenance_cost * 12)
                derivative -= year * annual_cash_flow / ((1 + rate) ** (year + 1))
            return derivative
        
        # Newton-Raphson method to find IRR
        rate = 0.1  # Initial guess (10%)
        tolerance = 1e-6
        max_iterations = 100
        
        for _ in range(max_iterations):
            npv_value = npv_at_rate(rate)
            if abs(npv_value) < tolerance:
                break
            
            derivative = npv_derivative(rate)
            if abs(derivative) < tolerance:
                break  # Avoid division by zero
            
            rate = rate - npv_value / derivative
        
        return rate * 100  # Return as percentage

    def _calculate_break_even_point(self, monthly_savings: float, investment: OptimizationInvestment) -> str:
        """Calculate when the optimization breaks even."""
        if monthly_savings <= investment.ongoing_maintenance_cost:
            return "Never (maintenance costs exceed savings)"
        
        net_monthly_savings = monthly_savings - investment.ongoing_maintenance_cost
        break_even_months = investment.implementation_cost / net_monthly_savings
        
        break_even_date = datetime.now() + timedelta(days=break_even_months * 30)
        
        return f"{break_even_months:.1f} months ({break_even_date.strftime('%Y-%m-%d')})"

    def generate_cost_projections(self, current_monthly_cost: float, optimizations: List[ROIAnalysis],
                                months_ahead: int = 36) -> List[CostProjection]:
        """Generate cost projections with and without optimizations."""
        projections = []
        
        # Calculate total monthly savings from all optimizations
        total_monthly_savings = sum(opt.monthly_savings for opt in optimizations)
        
        # Generate monthly projections
        cumulative_savings = 0.0
        
        for month in range(1, months_ahead + 1):
            # Current trajectory (with inflation)
            inflation_rate = 0.02 / 12  # 2% annual inflation, monthly
            current_cost = current_monthly_cost * ((1 + inflation_rate) ** month)
            
            # Optimized cost (assume optimizations take effect gradually)
            implementation_factor = min(1.0, month / 6)  # Full effect after 6 months
            effective_savings = total_monthly_savings * implementation_factor
            optimized_cost = current_cost - effective_savings
            
            monthly_savings = current_cost - optimized_cost
            cumulative_savings += monthly_savings
            
            # Confidence interval (±20% for projections beyond 12 months)
            uncertainty_factor = 0.1 + (month / 12 * 0.1)  # Increases over time
            confidence_low = optimized_cost * (1 - uncertainty_factor)
            confidence_high = optimized_cost * (1 + uncertainty_factor)
            
            projections.append(CostProjection(
                period=f"Month {month}",
                current_cost=current_cost,
                optimized_cost=optimized_cost,
                savings=monthly_savings,
                cumulative_savings=cumulative_savings,
                confidence_interval=(confidence_low, confidence_high)
            ))
        
        return projections

    def calculate_business_impact(self, optimizations: List[ROIAnalysis]) -> BusinessImpactMetrics:
        """Calculate broader business impact metrics."""
        
        total_annual_savings = sum(opt.annual_savings for opt in optimizations)
        
        # Estimate efficiency improvements
        efficiency_improvement = 0.0
        for opt in optimizations:
            if 'lambda' in opt.optimization_name.lower():
                efficiency_improvement += 15  # Lambda optimizations improve execution efficiency
            elif 'query' in opt.optimization_name.lower():
                efficiency_improvement += 25  # Query optimizations have high efficiency impact
            elif 's3' in opt.optimization_name.lower():
                efficiency_improvement += 10  # Storage optimizations improve data access
        
        # Resource capacity freed (engineering hours)
        freed_capacity = {
            'engineering_hours_monthly': total_annual_savings / 100,  # $100/hour assumption
            'infrastructure_management_hours': total_annual_savings / 150,
            'data_processing_capacity_gb': total_annual_savings * 2  # Rough estimate
        }
        
        # Performance improvements
        performance_improvements = {
            'query_response_time_improvement_percent': 0,
            'data_processing_throughput_improvement_percent': 0,
            'system_reliability_improvement_percent': 0
        }
        
        for opt in optimizations:
            if 'query' in opt.optimization_name.lower():
                performance_improvements['query_response_time_improvement_percent'] += 40
            elif 'lambda' in opt.optimization_name.lower():
                performance_improvements['data_processing_throughput_improvement_percent'] += 20
            elif 'monitoring' in opt.optimization_name.lower():
                performance_improvements['system_reliability_improvement_percent'] += 15
        
        # Compliance and scalability benefits
        compliance_benefits = [
            "Improved cost governance and visibility",
            "Better resource utilization tracking",
            "Enhanced budget compliance",
            "Automated optimization reduces manual errors"
        ]
        
        scalability_benefits = [
            "Optimized architecture supports higher data volumes",
            "Reduced per-unit processing costs enable growth",
            "Automated optimization scales with usage",
            "Improved monitoring enables proactive capacity planning"
        ]
        
        return BusinessImpactMetrics(
            cost_avoidance_annual=total_annual_savings,
            efficiency_improvement_percent=min(efficiency_improvement, 60),  # Cap at 60%
            resource_capacity_freed=freed_capacity,
            performance_improvements=performance_improvements,
            compliance_benefits=compliance_benefits,
            scalability_benefits=scalability_benefits
        )

    def prioritize_optimizations(self, optimizations: List[ROIAnalysis]) -> List[Dict[str, Any]]:
        """Prioritize optimizations based on ROI and risk factors."""
        
        # Score each optimization
        scored_optimizations = []
        
        for opt in optimizations:
            # Base score from risk-adjusted ROI
            base_score = opt.risk_adjusted_roi
            
            # Adjust for payback period (shorter is better)
            if opt.payback_period_months < 6:
                payback_bonus = 20
            elif opt.payback_period_months < 12:
                payback_bonus = 10
            elif opt.payback_period_months < 24:
                payback_bonus = 0
            else:
                payback_bonus = -20
            
            # Adjust for implementation complexity
            if opt.investment.time_to_implement_days < 7:
                complexity_bonus = 10
            elif opt.investment.time_to_implement_days < 14:
                complexity_bonus = 5
            elif opt.investment.time_to_implement_days < 30:
                complexity_bonus = 0
            else:
                complexity_bonus = -10
            
            # Adjust for absolute savings amount
            if opt.annual_savings > 50000:
                savings_bonus = 15
            elif opt.annual_savings > 20000:
                savings_bonus = 10
            elif opt.annual_savings > 10000:
                savings_bonus = 5
            else:
                savings_bonus = 0
            
            total_score = base_score + payback_bonus + complexity_bonus + savings_bonus
            
            # Determine priority level
            if total_score >= 60:
                priority = "Critical"
            elif total_score >= 40:
                priority = "High"
            elif total_score >= 20:
                priority = "Medium"
            else:
                priority = "Low"
            
            scored_optimizations.append({
                'optimization': opt.optimization_name,
                'priority': priority,
                'score': total_score,
                'annual_savings': opt.annual_savings,
                'payback_months': opt.payback_period_months,
                'risk_adjusted_roi': opt.risk_adjusted_roi,
                'implementation_days': opt.investment.time_to_implement_days,
                'recommendation': self._generate_implementation_recommendation(opt, priority)
            })
        
        # Sort by score (highest first)
        scored_optimizations.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_optimizations

    def _generate_implementation_recommendation(self, opt: ROIAnalysis, priority: str) -> str:
        """Generate implementation recommendation based on analysis."""
        
        if priority == "Critical":
            return f"Implement immediately. High ROI ({opt.risk_adjusted_roi:.1f}%) with {opt.payback_period_months:.1f} month payback."
        elif priority == "High":
            return f"Implement within next quarter. Strong ROI with manageable risk."
        elif priority == "Medium":
            return f"Consider for next planning cycle. Positive ROI but monitor implementation complexity."
        else:
            return f"Low priority. Consider only if resources are abundant or if supports strategic initiatives."

    def generate_portfolio_summary(self, optimizations: List[ROIAnalysis]) -> Dict[str, Any]:
        """Generate summary metrics for the optimization portfolio."""
        
        if not optimizations:
            return {}
        
        total_investment = sum(opt.investment.implementation_cost + 
                             (opt.investment.ongoing_maintenance_cost * 12) for opt in optimizations)
        total_annual_savings = sum(opt.annual_savings for opt in optimizations)
        
        # Portfolio-level metrics
        portfolio_roi = ((total_annual_savings * 5 - total_investment) / total_investment * 100) if total_investment > 0 else 0
        portfolio_payback = (total_investment / (total_annual_savings / 12)) if total_annual_savings > 0 else float('inf')
        
        # Risk assessment
        high_risk_count = len([opt for opt in optimizations if len(opt.investment.risk_factors) > 2])
        risk_level = "High" if high_risk_count > len(optimizations) * 0.5 else "Medium" if high_risk_count > 0 else "Low"
        
        return {
            'total_implementation_investment': total_investment,
            'total_annual_savings': total_annual_savings,
            'portfolio_roi_percent': portfolio_roi,
            'portfolio_payback_months': portfolio_payback,
            'total_optimizations': len(optimizations),
            'high_priority_count': len([opt for opt in optimizations if opt.risk_adjusted_roi >= 40]),
            'average_roi': sum(opt.risk_adjusted_roi for opt in optimizations) / len(optimizations),
            'portfolio_risk_level': risk_level,
            'implementation_timeline_days': max(opt.investment.time_to_implement_days for opt in optimizations),
            'net_5_year_value': sum(opt.npv_5_year for opt in optimizations)
        }

    def generate_comprehensive_roi_report(self, optimizations_config: List[Dict[str, Any]], 
                                        current_monthly_cost: float) -> ROIReport:
        """Generate a comprehensive ROI report for all optimizations."""
        
        logger.info("Generating comprehensive ROI analysis...")
        
        # Calculate ROI for each optimization
        roi_analyses = []
        for config in optimizations_config:
            optimization_type = config['type']
            monthly_savings = config['monthly_savings']
            custom_investment = config.get('custom_investment')
            
            roi_analysis = self.calculate_optimization_roi(
                optimization_type, monthly_savings, custom_investment
            )
            roi_analyses.append(roi_analysis)
        
        # Generate projections
        cost_projections = self.generate_cost_projections(current_monthly_cost, roi_analyses)
        
        # Calculate business impact
        business_impact = self.calculate_business_impact(roi_analyses)
        
        # Generate portfolio summary
        portfolio_summary = self.generate_portfolio_summary(roi_analyses)
        
        # Prioritize optimizations
        recommendations = self.prioritize_optimizations(roi_analyses)
        
        report = ROIReport(
            report_id=f"roi-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            analysis_period="5 years",
            optimizations_analyzed=roi_analyses,
            portfolio_summary=portfolio_summary,
            cost_projections=cost_projections,
            business_impact=business_impact,
            recommendations=recommendations
        )
        
        logger.info("ROI analysis completed")
        return report

def main():
    parser = argparse.ArgumentParser(description='Cost Optimization ROI Calculator')
    parser.add_argument('--config', required=True, help='JSON config file with optimization scenarios')
    parser.add_argument('--current-monthly-cost', type=float, required=True, help='Current monthly cost baseline')
    parser.add_argument('--output', help='Output file for ROI report')
    parser.add_argument('--discount-rate', type=float, default=0.08, help='Discount rate for NPV calculation')
    parser.add_argument('--summary', action='store_true', help='Show summary output instead of full JSON')
    
    args = parser.parse_args()
    
    # Load optimization configuration
    try:
        with open(args.config, 'r') as f:
            optimizations_config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file {args.config} not found")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing configuration file: {e}")
        return
    
    # Initialize calculator
    calculator = ROICalculator(discount_rate=args.discount_rate)
    
    # Generate ROI report
    report = calculator.generate_comprehensive_roi_report(
        optimizations_config, args.current_monthly_cost
    )
    
    if args.summary:
        # Print summary
        print(f"\n=== ROI ANALYSIS SUMMARY ===")
        print(f"Total Investment Required: ${report.portfolio_summary.get('total_implementation_investment', 0):,.2f}")
        print(f"Total Annual Savings: ${report.portfolio_summary.get('total_annual_savings', 0):,.2f}")
        print(f"Portfolio ROI: {report.portfolio_summary.get('portfolio_roi_percent', 0):.1f}%")
        print(f"Payback Period: {report.portfolio_summary.get('portfolio_payback_months', 0):.1f} months")
        print(f"5-Year NPV: ${report.portfolio_summary.get('net_5_year_value', 0):,.2f}")
        
        print(f"\nTop Recommendations:")
        for i, rec in enumerate(report.recommendations[:5], 1):
            print(f"{i}. {rec['optimization']} ({rec['priority']} Priority)")
            print(f"   Annual Savings: ${rec['annual_savings']:,.2f} | ROI: {rec['risk_adjusted_roi']:.1f}%")
        
    else:
        # Output full report
        report_dict = asdict(report)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report_dict, f, indent=2)
            logger.info(f"ROI report written to {args.output}")
        else:
            print(json.dumps(report_dict, indent=2))

if __name__ == '__main__':
    main()