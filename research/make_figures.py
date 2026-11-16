"""Render reproducible research figures from generated CSV outputs."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent;F=R/'figures';F.mkdir(exist_ok=True)
S=pd.read_csv(R/'outputs/scenario_comparison.csv')
S=S[S.scenario.isin(['insurance_capacity_wait_odds','capacity_plus_20pct','uninsured_accepted_all','capacity_and_uninsured'])]
labels=['Baseline','+20% capacity','Uninsured eligibility','Both']
fig,ax=plt.subplots(figsize=(9,4.5));ax.bar(labels,S.assigned);ax.set_ylabel('Modeled annual new-patient assignments');ax.set_title('Interventions: expected assignments (synthetic network)');ax.tick_params(axis='x',rotation=12);fig.tight_layout();fig.savefig(F/'intervention_assignments.png',dpi=170);plt.close(fig)
A=pd.read_csv(R/'outputs/baseline_coverage_by_group.csv');B=pd.read_csv(R/'outputs/equity_coverage_by_group.csv')
A['label']=A.insurance_type+' / '+A.transport_access.str.replace('No household vehicle','No vehicle proxy').str.replace('Vehicle access','Vehicle proxy')
B['label']=B.insurance_type+' / '+B.transport_access.str.replace('No household vehicle','No vehicle proxy').str.replace('Vehicle access','Vehicle proxy')
fig,ax=plt.subplots(figsize=(9,5.2));y=range(len(A));ax.barh([i-.18 for i in y],A.coverage*100,height=.34,label='Completion-optimized baseline');ax.barh([i+.18 for i in y],B.coverage*100,height=.34,label='Max-min coverage');ax.set_yticks(list(y),A.label);ax.set_xlabel('Share of modeled demand assigned (%)');ax.set_title('Assignment objective changes synthetic group coverage');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(F/'equity_comparison.png',dpi=170);plt.close(fig)
M=pd.read_csv(R/'outputs/provider_availability_summary.csv');fig,ax=plt.subplots(figsize=(7,4.5));x=M.availability_probability_scenario*100;ax.plot(x,M.mean_assigned,marker='o');ax.fill_between(x,M.p05_assigned,M.p95_assigned,alpha=.2);ax.set_xlabel('Assumed provider-record availability (%)');ax.set_ylabel('Modeled annual assignments');ax.set_title('Provider-availability uncertainty (synthetic scenarios)');fig.tight_layout();fig.savefig(F/'availability_uncertainty.png',dpi=170);plt.close(fig)
print('Saved three figures to',F)
